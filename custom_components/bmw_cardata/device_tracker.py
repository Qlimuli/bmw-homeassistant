"""BMW CarData Device Tracker Platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BMWCarDataConfigEntry, BMWCarDataCoordinator
from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

# Location descriptors
LATITUDE_DESCRIPTOR = "vehicle.cabin.infotainment.navigation.currentLocation.latitude"
LONGITUDE_DESCRIPTOR = "vehicle.cabin.infotainment.navigation.currentLocation.longitude"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BMWCarDataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BMW CarData device trackers."""
    coordinator = entry.runtime_data.coordinator

    entities: list[BMWCarDataDeviceTracker] = []

    # Get all vehicles - may be empty if rate limited on startup
    vehicles = coordinator.get_all_vehicles()

    if not vehicles:
        _LOGGER.debug(
            "BMW CarData: No vehicles found during device tracker setup. "
            "Trackers will be created when vehicle data becomes available."
        )
        # Register a listener to add entities when vehicles become available
        async def async_add_device_trackers_when_available() -> None:
            """Add device tracker entities when vehicle data becomes available."""
            vehicles = coordinator.get_all_vehicles()
            if vehicles:
                new_entities: list[BMWCarDataDeviceTracker] = []
                for vin, vehicle_info in vehicles.items():
                    basic_data = coordinator.get_vehicle_data(vin).get("basic_data", {})
                    new_entities.append(
                        BMWCarDataDeviceTracker(
                            coordinator=coordinator,
                            vin=vin,
                            vehicle_info=vehicle_info,
                            basic_data=basic_data,
                        )
                    )
                if new_entities:
                    async_add_entities(new_entities)
                    _LOGGER.info("BMW CarData: Added %d device tracker entities", len(new_entities))
        
        entry.async_on_unload(
            coordinator.async_add_listener(async_add_device_trackers_when_available)
        )
        return

    for vin, vehicle_info in vehicles.items():
        # Get basic data for device info
        basic_data = coordinator.get_vehicle_data(vin).get("basic_data", {})

        entities.append(
            BMWCarDataDeviceTracker(
                coordinator=coordinator,
                vin=vin,
                vehicle_info=vehicle_info,
                basic_data=basic_data,
            )
        )

    async_add_entities(entities)
    _LOGGER.debug("BMW CarData: Set up %d device tracker entities", len(entities))


class BMWCarDataDeviceTracker(CoordinatorEntity[BMWCarDataCoordinator], TrackerEntity):
    """BMW CarData Device Tracker Entity."""

    _attr_has_entity_name = True
    _attr_name = "Location"

    def __init__(
        self,
        coordinator: BMWCarDataCoordinator,
        vin: str,
        vehicle_info: dict[str, Any],
        basic_data: dict[str, Any],
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)

        self._vin = vin
        self._vehicle_info = vehicle_info
        self._basic_data = basic_data

        # Generate unique ID
        self._attr_unique_id = f"{vin}_location"

        # Set device info
        model = basic_data.get("model", basic_data.get("bodyType", "BMW"))
        brand = basic_data.get("brand", "BMW")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=f"{brand} {model}",
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=basic_data.get("softwareVersion"),
            hw_version=basic_data.get("driveTrain"),
        )

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        value = self.coordinator.get_sensor_value(self._vin, LATITUDE_DESCRIPTOR)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        value = self.coordinator.get_sensor_value(self._vin, LONGITUDE_DESCRIPTOR)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return None

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy in meters."""
        # GPS accuracy is typically around 10-20 meters
        return 15

    @property
    def icon(self) -> str:
        """Return the icon."""
        # Check if moving
        is_moving = self.coordinator.get_sensor_value(
            self._vin, "vehicle.powertrain.isMoving"
        )
        if is_moving:
            return "mdi:car-side"
        return "mdi:car"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs: dict[str, Any] = {
            "vin": self._vin,
        }

        # Add heading if available
        heading = self.coordinator.get_sensor_value(
            self._vin,
            "vehicle.cabin.infotainment.navigation.currentLocation.heading",
        )
        if heading is not None:
            attrs["heading"] = heading

        # Add altitude if available
        altitude = self.coordinator.get_sensor_value(
            self._vin,
            "vehicle.cabin.infotainment.navigation.currentLocation.altitude",
        )
        if altitude is not None:
            attrs["altitude"] = altitude

        # Add speed if available
        speed = self.coordinator.get_sensor_value(
            self._vin, "vehicle.powertrain.speed"
        )
        if speed is not None:
            attrs["speed"] = speed

        # Add timestamp if available
        mqtt_data = self.coordinator._mqtt_data.get(self._vin, {})
        if LATITUDE_DESCRIPTOR in mqtt_data:
            data = mqtt_data[LATITUDE_DESCRIPTOR]
            if isinstance(data, dict) and "timestamp" in data:
                attrs["last_updated"] = data["timestamp"]

        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
