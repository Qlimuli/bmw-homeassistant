"""Constants for the BMW CarData integration."""
from typing import Final

DOMAIN: Final = "bmw_cardata"
MANUFACTURER: Final = "BMW"

# Configuration
CONF_CLIENT_ID: Final = "client_id"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_ID_TOKEN: Final = "id_token"
CONF_GCID: Final = "gcid"
CONF_TOKEN_EXPIRY: Final = "token_expiry"
CONF_VEHICLES: Final = "vehicles"

# API Endpoints
BMW_AUTH_URL: Final = "https://customer.bmwgroup.com/gcdm/oauth"
BMW_API_URL: Final = "https://api-cardata.bmwgroup.com"
BMW_MQTT_HOST: Final = "customer.streaming-cardata.bmwgroup.com"
BMW_MQTT_PORT: Final = 9000

# OAuth2 Settings
OAUTH_SCOPES: Final = "authenticate_user openid cardata:streaming:read cardata:api:read"
OAUTH_RESPONSE_TYPE: Final = "device_code"
OAUTH_GRANT_TYPE_DEVICE: Final = "urn:ietf:params:oauth:grant-type:device_code"
OAUTH_GRANT_TYPE_REFRESH: Final = "refresh_token"
OAUTH_CODE_CHALLENGE_METHOD: Final = "S256"

# Timeouts (seconds)
TOKEN_REFRESH_MARGIN: Final = 300  # Refresh 5 minutes before expiry
API_TIMEOUT: Final = 30
MQTT_KEEPALIVE: Final = 60
POLL_INTERVAL: Final = 1800  # 30 minutes fallback polling

# API Rate Limit
# BMW CarData API has a daily limit of ~50 requests
API_RATE_LIMIT_DAILY: Final = 50
# After hitting the limit, wait 24 hours before retrying
API_RATE_LIMIT_RESET_HOURS: Final = 24

# Platforms
PLATFORMS: Final = ["sensor", "binary_sensor", "device_tracker", "button"]

# Debug Mode
# Set to True to enable verbose logging for troubleshooting
# WARNING: This will log sensitive data like tokens - only enable for debugging
DEBUG_LOG: Final = False

# Sensor Categories
SENSOR_CATEGORIES: Final = {
    "battery": {
        "icon": "mdi:car-battery",
        "device_class": "battery",
    },
    "range": {
        "icon": "mdi:map-marker-distance",
        "device_class": None,
    },
    "fuel": {
        "icon": "mdi:gas-station",
        "device_class": None,
    },
    "mileage": {
        "icon": "mdi:counter",
        "device_class": None,
    },
    "location": {
        "icon": "mdi:map-marker",
        "device_class": None,
    },
    "door": {
        "icon": "mdi:car-door",
        "device_class": "door",
    },
    "window": {
        "icon": "mdi:car-door",
        "device_class": "window",
    },
    "lock": {
        "icon": "mdi:car-key",
        "device_class": "lock",
    },
    "charging": {
        "icon": "mdi:ev-station",
        "device_class": None,
    },
    "climate": {
        "icon": "mdi:thermometer",
        "device_class": "temperature",
    },
    "tire": {
        "icon": "mdi:tire",
        "device_class": None,
    },
    "service": {
        "icon": "mdi:wrench",
        "device_class": None,
    },
}

# Telematic Descriptors - Most common ones
TELEMATIC_DESCRIPTORS: Final = {
    # Battery & Charging
    "vehicle.drivetrain.batteryManagement.header": "Battery SOC",
    "vehicle.drivetrain.batteryManagement.maxEnergy": "Battery Max Energy",
    "vehicle.drivetrain.electricEngine.kombiRemainingElectricRange": "Electric Range",
    "vehicle.drivetrain.electricEngine.charging.status": "Charging Status",
    "vehicle.powertrain.electric.battery.charging.power": "Charging Power",
    "vehicle.powertrain.electric.battery.charging.level": "Charging Level",
    "vehicle.powertrain.electric.battery.charging.remainingTime": "Charging Remaining Time",
    "vehicle.powertrain.electric.battery.charging.targetSoc": "Charging Target SOC",
    
    # Fuel (for PHEVs and ICE)
    "vehicle.drivetrain.fuelSystem.remainingFuel": "Remaining Fuel",
    "vehicle.drivetrain.fuelSystem.level": "Fuel Level",
    "vehicle.drivetrain.fuelSystem.range": "Fuel Range",
    
    # Mileage
    "vehicle.powertrain.mileage": "Mileage",
    "vehicle.powertrain.odometer": "Odometer",
    
    # Location
    "vehicle.cabin.infotainment.navigation.currentLocation.latitude": "Latitude",
    "vehicle.cabin.infotainment.navigation.currentLocation.longitude": "Longitude",
    "vehicle.cabin.infotainment.navigation.currentLocation.altitude": "Altitude",
    "vehicle.cabin.infotainment.navigation.currentLocation.heading": "Heading",
    
    # Doors
    "vehicle.cabin.door.row1.driver.isOpen": "Driver Door",
    "vehicle.cabin.door.row1.passenger.isOpen": "Passenger Door",
    "vehicle.cabin.door.row2.driver.isOpen": "Rear Left Door",
    "vehicle.cabin.door.row2.passenger.isOpen": "Rear Right Door",
    "vehicle.body.trunk.door.isOpen": "Trunk",
    "vehicle.body.hood.isOpen": "Hood",
    
    # Windows
    "vehicle.cabin.window.row1.driver.position": "Driver Window",
    "vehicle.cabin.window.row1.passenger.position": "Passenger Window",
    "vehicle.cabin.window.row2.driver.position": "Rear Left Window",
    "vehicle.cabin.window.row2.passenger.position": "Rear Right Window",
    "vehicle.cabin.sunroof.position": "Sunroof",
    
    # Locks
    "vehicle.body.door.lockState": "Lock State",
    "vehicle.cabin.door.row1.driver.isLocked": "Driver Door Lock",
    "vehicle.cabin.door.row1.passenger.isLocked": "Passenger Door Lock",
    
    # Climate
    "vehicle.cabin.hvac.temperature.interior": "Interior Temperature",
    "vehicle.cabin.hvac.temperature.exterior": "Exterior Temperature",
    
    # Motion
    "vehicle.powertrain.isMoving": "Is Moving",
    "vehicle.powertrain.speed": "Speed",
    
    # Tire Pressure
    "vehicle.chassis.axle.row1.wheel.left.tire.pressure": "Front Left Tire Pressure",
    "vehicle.chassis.axle.row1.wheel.right.tire.pressure": "Front Right Tire Pressure",
    "vehicle.chassis.axle.row2.wheel.left.tire.pressure": "Rear Left Tire Pressure",
    "vehicle.chassis.axle.row2.wheel.right.tire.pressure": "Rear Right Tire Pressure",
    
    # Service
    "vehicle.service.serviceStatus": "Service Status",
    "vehicle.service.nextServiceDate": "Next Service Date",
    "vehicle.service.nextServiceMileage": "Next Service Mileage",
}

# Binary Sensor Descriptors (return boolean values)
BINARY_DESCRIPTORS: Final = [
    "vehicle.cabin.door.row1.driver.isOpen",
    "vehicle.cabin.door.row1.passenger.isOpen",
    "vehicle.cabin.door.row2.driver.isOpen",
    "vehicle.cabin.door.row2.passenger.isOpen",
    "vehicle.body.trunk.door.isOpen",
    "vehicle.body.hood.isOpen",
    "vehicle.cabin.door.row1.driver.isLocked",
    "vehicle.cabin.door.row1.passenger.isLocked",
    "vehicle.powertrain.isMoving",
]

# Device Tracker Descriptors
LOCATION_DESCRIPTORS: Final = [
    "vehicle.cabin.infotainment.navigation.currentLocation.latitude",
    "vehicle.cabin.infotainment.navigation.currentLocation.longitude",
]
