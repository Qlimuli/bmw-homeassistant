"""Diagnostics support for BMW CarData."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_ACCESS_TOKEN,
    CONF_ID_TOKEN,
    CONF_GCID,
)

# Keys to redact from diagnostics
TO_REDACT = {
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_ACCESS_TOKEN,
    CONF_ID_TOKEN,
    CONF_GCID,
    "vin",
    "latitude",
    "longitude",
    "gcid",
    "client_id",
    "access_token",
    "refresh_token",
    "id_token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    mqtt_client = hass.data[DOMAIN][entry.entry_id].get("mqtt_client")
    
    # Get vehicle data
    vehicles = coordinator.get_all_vehicles()
    vehicle_data = {}
    
    for vin, info in vehicles.items():
        data = coordinator.get_vehicle_data(vin)
        vehicle_data[vin[-4:]] = {  # Only show last 4 chars of VIN
            "vehicle_info": async_redact_data(info, TO_REDACT),
            "data": async_redact_data(data, TO_REDACT),
        }
    
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "mqtt_connected": mqtt_client.is_connected if mqtt_client else False,
        "vehicles_count": len(vehicles),
        "vehicles": vehicle_data,
    }
