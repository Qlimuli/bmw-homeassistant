"""Diagnostics support for BMW CarData."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BMWCarDataConfigEntry

# Keys to redact from diagnostics
TO_REDACT = {
    "client_id",
    "refresh_token",
    "access_token",
    "id_token",
    "gcid",
    "vin",
    "latitude",
    "longitude",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: BMWCarDataConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    if not entry.runtime_data:
        return {"error": "No runtime data available"}

    coordinator = entry.runtime_data.coordinator
    mqtt_client = entry.runtime_data.mqtt_client

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
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "minor_version": entry.minor_version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "mqtt_connected": mqtt_client.is_connected if mqtt_client else False,
        "mqtt_subscribed_vins_count": (
            len(mqtt_client._subscribed_vins) if mqtt_client else 0
        ),
        "vehicles_count": len(vehicles),
        "vehicles": vehicle_data,
    }
