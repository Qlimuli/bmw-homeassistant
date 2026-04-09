"""BMW CarData Sensor Platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfPressure,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BMWCarDataConfigEntry, BMWCarDataCoordinator
from .const import (
    DOMAIN,
    MANUFACTURER,
    BINARY_DESCRIPTORS,
    LOCATION_DESCRIPTORS,
)

_LOGGER = logging.getLogger(__name__)

# Define sensor descriptions
SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    # Battery & Charging
    "vehicle.drivetrain.batteryManagement.header": SensorEntityDescription(
        key="battery_soc",
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-battery",
    ),
    "vehicle.drivetrain.batteryManagement.maxEnergy": SensorEntityDescription(
        key="battery_max_energy",
        name="Battery Max Energy",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-high",
    ),
    "vehicle.drivetrain.electricEngine.kombiRemainingElectricRange": SensorEntityDescription(
        key="electric_range",
        name="Electric Range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
    ),
    "vehicle.powertrain.electric.battery.charging.power": SensorEntityDescription(
        key="charging_power",
        name="Charging Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ev-station",
    ),
    "vehicle.powertrain.electric.battery.charging.level": SensorEntityDescription(
        key="charging_level",
        name="Charging Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-charging",
    ),
    "vehicle.powertrain.electric.battery.charging.remainingTime": SensorEntityDescription(
        key="charging_remaining_time",
        name="Charging Remaining Time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-outline",
    ),
    "vehicle.powertrain.electric.battery.charging.targetSoc": SensorEntityDescription(
        key="charging_target_soc",
        name="Charging Target",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-charging-high",
    ),
    "vehicle.drivetrain.electricEngine.charging.status": SensorEntityDescription(
        key="charging_status",
        name="Charging Status",
        icon="mdi:ev-plug-type2",
    ),

    # Fuel
    "vehicle.drivetrain.fuelSystem.remainingFuel": SensorEntityDescription(
        key="remaining_fuel",
        name="Remaining Fuel",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gas-station",
    ),
    "vehicle.drivetrain.fuelSystem.level": SensorEntityDescription(
        key="fuel_level",
        name="Fuel Level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gas-station",
    ),
    "vehicle.drivetrain.fuelSystem.range": SensorEntityDescription(
        key="fuel_range",
        name="Fuel Range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gas-station-outline",
    ),

    # Mileage
    "vehicle.powertrain.mileage": SensorEntityDescription(
        key="mileage",
        name="Mileage",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
    ),
    "vehicle.powertrain.odometer": SensorEntityDescription(
        key="odometer",
        name="Odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
    ),

    # Location
    "vehicle.cabin.infotainment.navigation.currentLocation.altitude": SensorEntityDescription(
        key="altitude",
        name="Altitude",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:altimeter",
    ),
    "vehicle.cabin.infotainment.navigation.currentLocation.heading": SensorEntityDescription(
        key="heading",
        name="Heading",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:compass",
    ),

    # Climate
    "vehicle.cabin.hvac.temperature.interior": SensorEntityDescription(
        key="interior_temperature",
        name="Interior Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    "vehicle.cabin.hvac.temperature.exterior": SensorEntityDescription(
        key="exterior_temperature",
        name="Exterior Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),

    # Speed
    "vehicle.powertrain.speed": SensorEntityDescription(
        key="speed",
        name="Speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
    ),

    # Tire Pressure
    "vehicle.chassis.axle.row1.wheel.left.tire.pressure": SensorEntityDescription(
        key="tire_pressure_fl",
        name="Front Left Tire Pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:tire",
    ),
    "vehicle.chassis.axle.row1.wheel.right.tire.pressure": SensorEntityDescription(
        key="tire_pressure_fr",
        name="Front Right Tire Pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:tire",
    ),
    "vehicle.chassis.axle.row2.wheel.left.tire.pressure": SensorEntityDescription(
        key="tire_pressure_rl",
        name="Rear Left Tire Pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:tire",
    ),
    "vehicle.chassis.axle.row2.wheel.right.tire.pressure": SensorEntityDescription(
        key="tire_pressure_rr",
        name="Rear Right Tire Pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:tire",
    ),

    # Window positions
    "vehicle.cabin.window.row1.driver.position": SensorEntityDescription(
        key="window_driver",
        name="Driver Window Position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.window.row1.passenger.position": SensorEntityDescription(
        key="window_passenger",
        name="Passenger Window Position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.window.row2.driver.position": SensorEntityDescription(
        key="window_rear_left",
        name="Rear Left Window Position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.window.row2.passenger.position": SensorEntityDescription(
        key="window_rear_right",
        name="Rear Right Window Position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-door",
    ),
    "vehicle.cabin.sunroof.position": SensorEntityDescription(
        key="sunroof_position",
        name="Sunroof Position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-select",
    ),

    # Service
    "vehicle.service.serviceStatus": SensorEntityDescription(
        key="service_status",
        name="Service Status",
        icon="mdi:wrench",
    ),
    "vehicle.service.nextServiceDate": SensorEntityDescription(
        key="next_service_date",
        name="Next Service Date",
        icon="mdi:calendar-check",
    ),
    "vehicle.service.nextServiceMileage": SensorEntityDescription(
        key="next_service_mileage",
        name="Next Service Mileage",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:road-variant",
    ),

    # Lock state
    "vehicle.body.door.lockState": SensorEntityDescription(
        key="lock_state",
        name="Lock State",
        icon="mdi:car-key",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BMWCarDataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BMW CarData sensors."""
    coordinator = entry.runtime_data.coordinator

    entities: list[BMWCarDataSensor] = []

    # Get vehicles - may be empty if rate limited on startup
    vehicles = coordinator.get_all_vehicles()

    if not vehicles:
        _LOGGER.warning(
            "BMW CarData: No vehicles found during sensor setup. "
            "Sensors will be created when vehicle data becomes available."
        )
        # Register a listener to add entities when vehicles become available
        async def async_add_sensors_when_available() -> None:
            """Add sensor entities when vehicle data becomes available."""
            vehicles = coordinator.get_all_vehicles()
            if vehicles:
                new_entities: list[BMWCarDataSensor] = []
                for vin, vehicle_info in vehicles.items():
                    basic_data = coordinator.get_vehicle_data(vin).get("basic_data", {})
                    for descriptor, description in SENSOR_DESCRIPTIONS.items():
                        if descriptor in BINARY_DESCRIPTORS or descriptor in LOCATION_DESCRIPTORS:
                            continue
                        new_entities.append(
                            BMWCarDataSensor(
                                coordinator=coordinator,
                                vin=vin,
                                vehicle_info=vehicle_info,
                                basic_data=basic_data,
                                descriptor=descriptor,
                                description=description,
                            )
                        )
                if new_entities:
                    async_add_entities(new_entities)
                    _LOGGER.info("BMW CarData: Added %d sensor entities", len(new_entities))
        
        # Schedule check after first successful update
        entry.async_on_unload(
            coordinator.async_add_listener(async_add_sensors_when_available)
        )
        return

    for vin, vehicle_info in vehicles.items():
        # Get basic data for device info
        basic_data = coordinator.get_vehicle_data(vin).get("basic_data", {})

        # Create sensors for all known descriptors
        for descriptor, description in SENSOR_DESCRIPTIONS.items():
            # Skip binary sensors and location sensors
            if descriptor in BINARY_DESCRIPTORS or descriptor in LOCATION_DESCRIPTORS:
                continue

            entities.append(
                BMWCarDataSensor(
                    coordinator=coordinator,
                    vin=vin,
                    vehicle_info=vehicle_info,
                    basic_data=basic_data,
                    descriptor=descriptor,
                    description=description,
                )
            )

    async_add_entities(entities)
    _LOGGER.debug("BMW CarData: Set up %d sensor entities", len(entities))


class BMWCarDataSensor(CoordinatorEntity[BMWCarDataCoordinator], SensorEntity):
    """BMW CarData Sensor Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BMWCarDataCoordinator,
        vin: str,
        vehicle_info: dict[str, Any],
        basic_data: dict[str, Any],
        descriptor: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
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
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        value = self.coordinator.get_sensor_value(self._vin, self._descriptor)

        if value is None:
            return None

        # Convert values if needed
        if isinstance(value, (int, float)):
            # Round to reasonable precision
            if self.entity_description.native_unit_of_measurement == PERCENTAGE:
                return round(value, 1)
            if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE:
                return round(value, 1)
            if self.entity_description.device_class == SensorDeviceClass.PRESSURE:
                return round(value, 2)
            return round(value, 2) if isinstance(value, float) else value

        return value

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
            if isinstance(data, dict):
                if "timestamp" in data:
                    attrs["last_updated"] = data["timestamp"]
                if "unit" in data:
                    attrs["source_unit"] = data["unit"]

        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
