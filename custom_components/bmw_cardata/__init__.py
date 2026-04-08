"""BMW CarData Integration for Home Assistant."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    PLATFORMS,
    POLL_INTERVAL,
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_ACCESS_TOKEN,
    CONF_ID_TOKEN,
    CONF_GCID,
    DEBUG_LOG,
)
from .api import BMWCarDataAPI, BMWCarDataAuthError, BMWCarDataAPIError
from .mqtt_client import BMWMQTTClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class BMWCarDataRuntimeData:
    """Runtime data for BMW CarData integration."""

    api: BMWCarDataAPI
    coordinator: "BMWCarDataCoordinator"
    mqtt_client: BMWMQTTClient


type BMWCarDataConfigEntry = ConfigEntry[BMWCarDataRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BMWCarDataConfigEntry) -> bool:
    """Set up BMW CarData from a config entry."""
    session = async_get_clientsession(hass)

    # Initialize API client
    api = BMWCarDataAPI(
        session=session,
        client_id=entry.data[CONF_CLIENT_ID],
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
        id_token=entry.data.get(CONF_ID_TOKEN),
        gcid=entry.data.get(CONF_GCID),
    )

    # Validate credentials by refreshing tokens
    try:
        await api.async_refresh_tokens()
    except BMWCarDataAuthError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except BMWCarDataAPIError as err:
        raise ConfigEntryNotReady(f"Could not connect to BMW API: {err}") from err

    # Update stored tokens if they changed
    new_data = {
        **entry.data,
        CONF_ACCESS_TOKEN: api.access_token,
        CONF_REFRESH_TOKEN: api.refresh_token,
        CONF_ID_TOKEN: api.id_token,
        CONF_GCID: api.gcid,
    }
    if new_data != entry.data:
        hass.config_entries.async_update_entry(entry, data=new_data)

    # Initialize coordinator
    coordinator = BMWCarDataCoordinator(hass, api, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Initialize MQTT client for streaming
    # Use freshly-refreshed tokens from the API (not the potentially-stale ones stored in entry.data)
    mqtt_client = BMWMQTTClient(
        hass=hass,
        coordinator=coordinator,
        gcid=api.gcid or entry.data.get(CONF_GCID, ""),
        id_token=api.id_token or entry.data.get(CONF_ID_TOKEN, ""),
    )

    # Store runtime data using the new pattern
    entry.runtime_data = BMWCarDataRuntimeData(
        api=api,
        coordinator=coordinator,
        mqtt_client=mqtt_client,
    )

    # Start MQTT streaming
    await mqtt_client.async_start()

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await async_register_services(hass)

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(
    hass: HomeAssistant, entry: BMWCarDataConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: BMWCarDataConfigEntry
) -> bool:
    """Unload a config entry."""
    # Stop MQTT client
    if entry.runtime_data:
        await entry.runtime_data.mqtt_client.async_stop()

    # Unload platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    if hass.services.has_service(DOMAIN, "refresh_tokens"):
        return

    async def handle_refresh_tokens(call: ServiceCall) -> None:
        """Handle token refresh service."""
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                api = entry.runtime_data.api
                try:
                    await api.async_refresh_tokens()
                    _LOGGER.info("Tokens refreshed for entry %s", entry.entry_id)
                except BMWCarDataAuthError as err:
                    _LOGGER.error("Token refresh failed: %s", err)

    async def handle_fetch_telematic_data(call: ServiceCall) -> None:
        """Handle telematic data fetch service."""
        vin = call.data.get("vin")
        container_id = call.data.get("container_id")

        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                api = entry.runtime_data.api
                try:
                    result = await api.async_get_telematic_data(vin, container_id)
                    _LOGGER.info("Telematic data for VIN %s: %s", vin, result)
                except BMWCarDataAPIError as err:
                    _LOGGER.error("Failed to fetch telematic data: %s", err)

    hass.services.async_register(DOMAIN, "refresh_tokens", handle_refresh_tokens)
    hass.services.async_register(
        DOMAIN, "fetch_telematic_data", handle_fetch_telematic_data
    )


class BMWCarDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for BMW CarData updates."""

    config_entry: BMWCarDataConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: BMWCarDataAPI,
        entry: BMWCarDataConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
            config_entry=entry,
        )
        self.api = api
        self.vehicles: dict[str, dict[str, Any]] = {}
        self.vehicle_data: dict[str, dict[str, Any]] = {}
        self._mqtt_data: dict[str, dict[str, Any]] = {}

    def update_mqtt_data(self, vin: str, data: dict[str, Any]) -> None:
        """Update data received from MQTT stream."""
        if vin not in self._mqtt_data:
            self._mqtt_data[vin] = {}

        self._mqtt_data[vin].update(data)

        # Merge into vehicle_data
        if vin not in self.vehicle_data:
            self.vehicle_data[vin] = {}
        self.vehicle_data[vin].update(data)

        # Notify listeners
        self.async_set_updated_data(self.vehicle_data)

        if DEBUG_LOG:
            _LOGGER.debug("MQTT data updated for VIN %s: %s", vin, data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API (fallback polling)."""
        try:
            # Refresh tokens if needed
            await self.api.async_refresh_tokens()

            # Update stored tokens
            if self.config_entry:
                new_data = {
                    **self.config_entry.data,
                    CONF_ACCESS_TOKEN: self.api.access_token,
                    CONF_REFRESH_TOKEN: self.api.refresh_token,
                    CONF_ID_TOKEN: self.api.id_token,
                    CONF_GCID: self.api.gcid,
                }
                if new_data != self.config_entry.data:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=new_data
                    )

            # Get vehicle mappings
            mappings = await self.api.async_get_vehicle_mappings()

            for mapping in mappings:
                vin = mapping.get("vin")
                if not vin:
                    continue

                # Store vehicle info
                self.vehicles[vin] = mapping

                # Get basic vehicle data
                basic_data = await self.api.async_get_basic_data(vin)
                if basic_data:
                    if vin not in self.vehicle_data:
                        self.vehicle_data[vin] = {}
                    self.vehicle_data[vin]["basic_data"] = basic_data

                # Get telematic data if container exists
                containers = await self.api.async_get_containers()
                for container in containers:
                    if container.get("state") == "ACTIVE":
                        container_id = container.get("containerId")
                        telematic_data = await self.api.async_get_telematic_data(
                            vin, container_id
                        )
                        if telematic_data:
                            if vin not in self.vehicle_data:
                                self.vehicle_data[vin] = {}
                            self.vehicle_data[vin]["telematic"] = telematic_data

            return self.vehicle_data

        except BMWCarDataAuthError as err:
            _LOGGER.error("Authentication error: %s", err)
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except BMWCarDataAPIError as err:
            _LOGGER.error("Error fetching BMW CarData: %s", err)
            raise UpdateFailed(f"Error communicating with BMW API: {err}") from err

    def get_vehicle_data(self, vin: str) -> dict[str, Any]:
        """Get data for a specific vehicle."""
        return self.vehicle_data.get(vin, {})

    def get_sensor_value(self, vin: str, descriptor: str) -> Any:
        """Get a specific sensor value for a vehicle."""
        vehicle_data = self.vehicle_data.get(vin, {})

        # Check MQTT data first (most recent)
        mqtt_data = self._mqtt_data.get(vin, {})
        if descriptor in mqtt_data:
            return mqtt_data[descriptor].get("value")

        # Check telematic data
        telematic = vehicle_data.get("telematic", {})
        for item in telematic if isinstance(telematic, list) else []:
            if item.get("name") == descriptor:
                return item.get("value")

        return None

    def get_all_vehicles(self) -> dict[str, dict[str, Any]]:
        """Get all vehicles."""
        return self.vehicles
