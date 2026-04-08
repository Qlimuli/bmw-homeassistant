"""BMW CarData Button Platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BMWCarDataCoordinator
from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


BUTTON_DESCRIPTIONS = [
    ButtonEntityDescription(
        key="refresh_data",
        name="Refresh Data",
        icon="mdi:refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ButtonEntityDescription(
        key="refresh_tokens",
        name="Refresh Tokens",
        icon="mdi:key-change",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BMW CarData buttons."""
    coordinator: BMWCarDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    
    entities: list[BMWCarDataButton] = []
    
    # Get all vehicles
    vehicles = coordinator.get_all_vehicles()
    
    for vin, vehicle_info in vehicles.items():
        basic_data = coordinator.get_vehicle_data(vin).get("basic_data", {})
        
        for description in BUTTON_DESCRIPTIONS:
            entities.append(
                BMWCarDataButton(
                    coordinator=coordinator,
                    api=api,
                    vin=vin,
                    basic_data=basic_data,
                    description=description,
                )
            )
    
    async_add_entities(entities)


class BMWCarDataButton(CoordinatorEntity[BMWCarDataCoordinator], ButtonEntity):
    """BMW CarData Button Entity."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self,
        coordinator: BMWCarDataCoordinator,
        api: Any,
        vin: str,
        basic_data: dict[str, Any],
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        
        self._api = api
        self._vin = vin
        self._basic_data = basic_data
        
        self.entity_description = description
        
        # Generate unique ID
        self._attr_unique_id = f"{vin}_{description.key}"
        
        # Set device info
        model = basic_data.get("model", basic_data.get("bodyType", "BMW"))
        brand = basic_data.get("brand", "BMW")
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=f"{brand} {model}",
            manufacturer=MANUFACTURER,
            model=model,
        )
    
    async def async_press(self) -> None:
        """Handle button press."""
        if self.entity_description.key == "refresh_data":
            _LOGGER.info("Refreshing data for VIN %s", self._vin[-4:])
            await self.coordinator.async_request_refresh()
        
        elif self.entity_description.key == "refresh_tokens":
            _LOGGER.info("Refreshing tokens")
            await self._api.async_refresh_tokens()
            
            # Update MQTT client with new token
            mqtt_client = self.hass.data[DOMAIN][self.coordinator.entry.entry_id].get(
                "mqtt_client"
            )
            if mqtt_client:
                await mqtt_client.async_refresh_connection()
