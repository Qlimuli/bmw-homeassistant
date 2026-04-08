"""BMW CarData Integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
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
    CONF_VEHICLES,
    DEBUG_LOG,
)
from .api import BMWCarDataAPI
from .mqtt_client import BMWMQTTClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BMW CarData from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
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
    
    # Initialize coordinator
    coordinator = BMWCarDataCoordinator(hass, api, entry)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Initialize MQTT client for streaming
    mqtt_client = BMWMQTTClient(
        hass=hass,
        coordinator=coordinator,
        gcid=entry.data.get(CONF_GCID, ""),
        id_token=entry.data.get(CONF_ID_TOKEN, ""),
    )
    
    # Store instances
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "mqtt_client": mqtt_client,
    }
    
    # Start MQTT streaming
    await mqtt_client.async_start()
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await async_register_services(hass)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Stop MQTT client
    mqtt_client = hass.data[DOMAIN][entry.entry_id].get("mqtt_client")
    if mqtt_client:
        await mqtt_client.async_stop()
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    
    async def handle_refresh_tokens(call) -> None:
        """Handle token refresh service."""
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and "api" in data:
                api = data["api"]
                await api.async_refresh_tokens()
                _LOGGER.info("Tokens refreshed for entry %s", entry_id)
    
    async def handle_fetch_telematic_data(call) -> None:
        """Handle telematic data fetch service."""
        vin = call.data.get("vin")
        container_id = call.data.get("container_id")
        
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and "api" in data:
                api = data["api"]
                result = await api.async_get_telematic_data(vin, container_id)
                _LOGGER.info("Telematic data for VIN %s: %s", vin, result)
    
    hass.services.async_register(DOMAIN, "refresh_tokens", handle_refresh_tokens)
    hass.services.async_register(DOMAIN, "fetch_telematic_data", handle_fetch_telematic_data)


class BMWCarDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for BMW CarData updates."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        api: BMWCarDataAPI,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.api = api
        self.entry = entry
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
            
        except Exception as err:
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
