"""BMW CarData Integration for Home Assistant."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    API_RATE_LIMIT_RESET_HOURS,
)
from .api import BMWCarDataAPI, BMWCarDataAuthError, BMWCarDataAPIError, BMWCarDataRateLimitError
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
    except BMWCarDataRateLimitError as err:
        # Rate limit is temporary — raise NotReady so HA backs off instead of
        # treating this as an auth failure and immediately retrying.
        raise ConfigEntryNotReady(f"BMW API rate limit reached, will retry later: {err}") from err
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

    # Fetch initial data.
    # We intentionally use async_refresh() instead of async_config_entry_first_refresh()
    # here. The latter converts UpdateFailed → ConfigEntryNotReady, which makes HA
    # retry the entire setup — burning another API call on every attempt and causing a
    # retry storm when the daily rate limit (CU-429) is active. async_refresh() absorbs
    # the failure gracefully: entities start as unavailable and populate on the next
    # scheduled poll (POLL_INTERVAL = 30 min).
    try:
        await coordinator.async_refresh()
    except Exception as err:
        # Log but don't fail setup - MQTT might still work
        _LOGGER.warning(
            "Initial data fetch failed (rate limit or network issue): %s. "
            "Entities will populate when API becomes available. MQTT streaming will still be attempted.",
            err,
        )

    # Initialize MQTT client for streaming
    # Use freshly-refreshed tokens from the API (not the potentially-stale ones stored in entry.data)
    gcid = api.gcid or entry.data.get(CONF_GCID, "")
    id_token = api.id_token or entry.data.get(CONF_ID_TOKEN, "")
    
    if not gcid or not id_token:
        _LOGGER.warning(
            "BMW MQTT: Missing GCID or ID token. MQTT streaming will not be available "
            "until tokens are refreshed."
        )
    
    mqtt_client = BMWMQTTClient(
        hass=hass,
        coordinator=coordinator,
        gcid=gcid,
        id_token=id_token,
    )

    # Store runtime data using the new pattern
    entry.runtime_data = BMWCarDataRuntimeData(
        api=api,
        coordinator=coordinator,
        mqtt_client=mqtt_client,
    )

    # Start MQTT streaming (will handle missing credentials gracefully)
    if gcid and id_token:
        await mqtt_client.async_start()
    else:
        _LOGGER.info("BMW MQTT: Skipping start due to missing credentials")

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
        # Rate-limit circuit breaker: when set, all API calls are skipped until
        # this timestamp has passed (daily limit resets after API_RATE_LIMIT_RESET_HOURS).
        self._rate_limit_until: datetime | None = None

    @property
    def vins(self) -> list[str]:
        """Return list of VINs for MQTT subscription."""
        return list(self.vehicles.keys())

    def update_mqtt_data(self, vin: str, data: dict[str, Any]) -> None:
        """Update data received from MQTT stream (sync version)."""
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

    async def async_handle_mqtt_data(
        self, vin: str, data: dict[str, Any], timestamp: str | None = None
    ) -> None:
        """Handle MQTT data asynchronously (called from MQTT client)."""
        if vin not in self._mqtt_data:
            self._mqtt_data[vin] = {}

        # Add timestamp to each data point if provided
        if timestamp:
            for key, value in data.items():
                if isinstance(value, dict) and "timestamp" not in value:
                    value["timestamp"] = timestamp

        self._mqtt_data[vin].update(data)

        # Merge into vehicle_data
        if vin not in self.vehicle_data:
            self.vehicle_data[vin] = {}
        
        # Store MQTT data under 'mqtt' key to distinguish from API data
        if "mqtt" not in self.vehicle_data[vin]:
            self.vehicle_data[vin]["mqtt"] = {}
        self.vehicle_data[vin]["mqtt"].update(data)

        # Notify listeners that data has updated
        self.async_set_updated_data(self.vehicle_data)

        if DEBUG_LOG:
            _LOGGER.debug(
                "MQTT data received for VIN %s: %d data points",
                vin[-4:] if len(vin) > 4 else vin,
                len(data),
            )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API (fallback polling)."""
        # Rate-limit circuit breaker: skip all API calls until the block expires.
        if self._rate_limit_until is not None:
            now = datetime.now(tz=timezone.utc)
            if now < self._rate_limit_until:
                remaining = int((self._rate_limit_until - now).total_seconds() / 60)
                if DEBUG_LOG:
                    _LOGGER.debug(
                        "BMW API rate limit active, skipping poll (%d min remaining). "
                        "MQTT streaming still active.",
                        remaining,
                    )
                # Return cached data — no UpdateFailed, no retry storm.
                return self.vehicle_data
            else:
                _LOGGER.info("BMW API rate limit window expired, resuming polling.")
                self._rate_limit_until = None

        try:
            # Refresh tokens if needed
            await self.api.async_refresh_tokens()

            # Update stored tokens and notify MQTT client
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
                    # Update MQTT client with new tokens
                    if (
                        hasattr(self.config_entry, "runtime_data")
                        and self.config_entry.runtime_data
                    ):
                        mqtt_client = self.config_entry.runtime_data.mqtt_client
                        if mqtt_client and self.api.id_token:
                            mqtt_client.update_tokens(
                                self.api.id_token, self.api.gcid
                            )

            # Get vehicle mappings (1 API call)
            mappings = await self.api.async_get_vehicle_mappings()
            
            if not mappings:
                _LOGGER.debug("BMW API: No vehicle mappings found")
                return self.vehicle_data

            # Get containers once (1 API call) - not per vehicle
            containers = []
            try:
                containers = await self.api.async_get_containers()
            except BMWCarDataRateLimitError:
                raise  # Re-raise rate limit errors
            except BMWCarDataAPIError as err:
                _LOGGER.warning("Failed to fetch containers: %s", err)

            # Find active container
            active_container_id = None
            for container in containers:
                if container.get("state") == "ACTIVE":
                    active_container_id = container.get("containerId")
                    break

            for mapping in mappings:
                vin = mapping.get("vin")
                if not vin:
                    continue

                # Check if this is a new VIN
                is_new_vin = vin not in self.vehicles
                
                # Store vehicle info
                self.vehicles[vin] = mapping

                if vin not in self.vehicle_data:
                    self.vehicle_data[vin] = {}
                
                # Subscribe MQTT client to new VINs
                if is_new_vin and hasattr(self.config_entry, "runtime_data") and self.config_entry.runtime_data:
                    mqtt_client = self.config_entry.runtime_data.mqtt_client
                    if mqtt_client and mqtt_client.is_connected:
                        mqtt_client.subscribe_vin(vin)

                # Get basic vehicle data (1 API call per vehicle)
                try:
                    basic_data = await self.api.async_get_basic_data(vin)
                    if basic_data:
                        self.vehicle_data[vin]["basic_data"] = basic_data
                except BMWCarDataRateLimitError:
                    raise  # Re-raise rate limit errors
                except BMWCarDataAPIError as err:
                    _LOGGER.warning("Failed to fetch basic data for %s: %s", vin[-4:], err)

                # Get telematic data if we have an active container (1 API call per vehicle)
                if active_container_id:
                    try:
                        telematic_data = await self.api.async_get_telematic_data(
                            vin, active_container_id
                        )
                        if telematic_data:
                            self.vehicle_data[vin]["telematic"] = telematic_data
                    except BMWCarDataRateLimitError:
                        raise  # Re-raise rate limit errors
                    except BMWCarDataAPIError as err:
                        _LOGGER.warning(
                            "Failed to fetch telematic data for %s: %s", vin[-4:], err
                        )

            _LOGGER.debug(
                "BMW API poll complete: %d vehicles updated", len(self.vehicles)
            )
            return self.vehicle_data

        except BMWCarDataRateLimitError as err:
            # Set the circuit breaker: skip API calls for the full daily reset window.
            self._rate_limit_until = datetime.now(tz=timezone.utc) + timedelta(
                hours=API_RATE_LIMIT_RESET_HOURS
            )
            _LOGGER.warning(
                "BMW API daily rate limit reached. Polling suspended for %d hours "
                "until %s. MQTT streaming remains active.",
                API_RATE_LIMIT_RESET_HOURS,
                self._rate_limit_until.strftime("%H:%M UTC"),
            )
            # Return cached data so HA keeps the last-known values visible and
            # the coordinator does NOT reschedule with a shortened retry interval.
            return self.vehicle_data
        except BMWCarDataAuthError as err:
            _LOGGER.error("BMW API authentication error: %s", err)
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except BMWCarDataAPIError as err:
            _LOGGER.error("BMW API error: %s", err)
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
