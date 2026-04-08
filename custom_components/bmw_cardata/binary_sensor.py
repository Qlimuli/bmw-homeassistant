"""BMW CarData Binary Sensor Platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BMWCarDataConfigEntry, BMWCarDataCoordinator
from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

# Define binary sensor descriptions
BINARY_SENSOR_DESCRIPTIONS: dict[str, BinarySensorEntityDescription] = {
    # Doors
    "vehicle.cabin.door.row1.driver.isOpen": BinarySensorEntityDescription(
        key="door_driver",
        name="Driver Door",
        device_class=BinarySensorDeviceClass.DOOR,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.door.row1.passenger.isOpen": BinarySensorEntityDescription(
        key="door_passenger",
        name="Passenger Door",
        device_class=BinarySensorDeviceClass.DOOR,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.door.row2.driver.isOpen": BinarySensorEntityDescription(
        key="door_rear_left",
        name="Rear Left Door",
        device_class=BinarySensorDeviceClass.DOOR,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.door.row2.passenger.isOpen": BinarySensorEntityDescription(
        key="door_rear_right",
        name="Rear Right Door",
        device_class=BinarySensorDeviceClass.DOOR,
        icon="mdi:car-door",
    ),
    "vehicle.body.trunk.door.isOpen": BinarySensorEntityDescription(
        key="trunk",
        name="Trunk",
        device_class=BinarySensorDeviceClass.DOOR,
        icon="mdi:car-back",
    ),
    "vehicle.body.hood.isOpen": BinarySensorEntityDescription(
        key="hood",
        name="Hood",
        device_class=BinarySensorDeviceClass.DOOR,
        icon="mdi:car-lifted-pickup",
    ),

    # Locks
    "vehicle.cabin.door.row1.driver.isLocked": BinarySensorEntityDescription(
        key="lock_driver",
        name="Driver Door Lock",
        device_class=BinarySensorDeviceClass.LOCK,
        icon="mdi:car-key",
    ),
    "vehicle.cabin.door.row1.passenger.isLocked": BinarySensorEntityDescription(
        key="lock_passenger",
        name="Passenger Door Lock",
        device_class=BinarySensorDeviceClass.LOCK,
        icon="mdi:car-key",
    ),

    # Motion
    "vehicle.powertrain.isMoving": BinarySensorEntityDescription(
        key="is_moving",
        name="Moving",
        device_class=BinarySensorDeviceClass.MOVING,
        icon="mdi:car-side",
    ),

    # Charging
    "vehicle.powertrain.electric.battery.charging.isCharging": BinarySensorEntityDescription(
        key="is_charging",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        icon="mdi:ev-station",
    ),
    "vehicle.powertrain.electric.battery.charging.isPluggedIn": BinarySensorEntityDescription(
        key="is_plugged_in",
        name="Plugged In",
        device_class=BinarySensorDeviceClass.PLUG,
        icon="mdi:ev-plug-type2",
    ),

    # Windows
    "vehicle.cabin.window.row1.driver.isOpen": BinarySensorEntityDescription(
        key="window_driver_open",
        name="Driver Window Open",
        device_class=BinarySensorDeviceClass.WINDOW,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.window.row1.passenger.isOpen": BinarySensorEntityDescription(
        key="window_passenger_open",
        name="Passenger Window Open",
        device_class=BinarySensorDeviceClass.WINDOW,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.window.row2.driver.isOpen": BinarySensorEntityDescription(
        key="window_rear_left_open",
        name="Rear Left Window Open",
        device_class=BinarySensorDeviceClass.WINDOW,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.window.row2.passenger.isOpen": BinarySensorEntityDescription(
        key="window_rear_right_open",
        name="Rear Right Window Open",
        device_class=BinarySensorDeviceClass.WINDOW,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.sunroof.isOpen": BinarySensorEntityDescription(
        key="sunroof_open",
        name="Sunroof Open",
        device_class=BinarySensorDeviceClass.WINDOW,
        icon="mdi:car-select",
    ),

    # Lights
    "vehicle.exterior.lights.fog.front.isOn": BinarySensorEntityDescription(
        key="fog_lights_front",
        name="Front Fog Lights",
        device_class=BinarySensorDeviceClass.LIGHT,
        icon="mdi:car-light-fog",
    ),
    "vehicle.exterior.lights.fog.rear.isOn": BinarySensorEntityDescription(
        key="fog_lights_rear",
        name="Rear Fog Lights",
        device_class=BinarySensorDeviceClass.LIGHT,
        icon="mdi:car-light-fog",
    ),
    "vehicle.exterior.lights.headlights.isOn": BinarySensorEntityDescription(
        key="headlights",
        name="Headlights",
        device_class=BinarySensorDeviceClass.LIGHT,
        icon="mdi:car-light-high",
    ),

    # Safety
    "vehicle.safety.alarm.isArmed": BinarySensorEntityDescription(
        key="alarm_armed",
        name="Alarm Armed",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:shield-car",
    ),
    "vehicle.safety.alarm.isTriggered": BinarySensorEntityDescription(
        key="alarm_triggered",
        name="Alarm Triggered",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:alarm-light",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BMWCarDataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BMW CarData binary sensors."""
    coordinator = entry.runtime_data.coordinator

    entities: list[BMWCarDataBinarySensor] = []

    # Get all vehicles
    vehicles = coordinator.get_all_vehicles()

    for vin, vehicle_info in vehicles.items():
        # Get basic data for device info
        basic_data = coordinator.get_vehicle_data(vin).get("basic_data", {})

        # Create binary sensors for all known descriptors
        for descriptor, description in BINARY_SENSOR_DESCRIPTIONS.items():
            entities.append(
                BMWCarDataBinarySensor(
                    coordinator=coordinator,
                    vin=vin,
                    vehicle_info=vehicle_info,
                    basic_data=basic_data,
                    descriptor=descriptor,
                    description=description,
                )
            )

    async_add_entities(entities)


class BMWCarDataBinarySensor(CoordinatorEntity[BMWCarDataCoordinator], BinarySensorEntity):
    """BMW CarData Binary Sensor Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BMWCarDataCoordinator,
        vin: str,
        vehicle_info: dict[str, Any],
        basic_data: dict[str, Any],
        descriptor: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)

        self._vin = vin
        self._descriptor = descriptor
        self._vehicle_info = vehicle_info
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
            sw_version=basic_data.get("softwareVersion"),
            hw_version=basic_data.get("driveTrain"),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.coordinator.get_sensor_value(self._vin, self._descriptor)

        if value is None:
            return None

        # Handle different value formats
        if isinstance(value, bool):
            # For lock sensors, inverted logic (locked = False means locked)
            if self.entity_description.device_class == BinarySensorDeviceClass.LOCK:
                return not value
            return value

        if isinstance(value, str):
            # Handle string values
            value_lower = value.lower()
            if value_lower in ("true", "open", "on", "yes", "1", "unlocked"):
                return True
            if value_lower in ("false", "closed", "off", "no", "0", "locked"):
                return False

        if isinstance(value, (int, float)):
            # For position values (windows), consider > 0 as open
            if "position" in self._descriptor.lower():
                return value > 0
            return value > 0

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        mqtt_data = self.coordinator._mqtt_data.get(self._vin, {})

        attrs: dict[str, Any] = {
            "vin": self._vin,
            "descriptor": self._descriptor,
        }

        # Add timestamp if available
        if self._descriptor in mqtt_data:
            data = mqtt_data[self._descriptor]
            if isinstance(data, dict) and "timestamp" in data:
                attrs["last_updated"] = data["timestamp"]

        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
