"""Diagnostics support for Hargassner Nano-PK integration.

Created by @Django1982 with Claude Code
"""
from __future__ import annotations

from typing import Any

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_FORMAT,
    CONF_NAME,
    CONF_PARAMS,
    CONF_LANG,
    CONF_UNIQUE_ID,
)


async def async_get_integration_diagnostics(hass) -> dict[str, Any]:
    """Return diagnostics for the entire integration (YAML-based)."""
    data = hass.data.get(DOMAIN, {})

    diagnostics = {
        "integration": {
            "domain": DOMAIN,
            "version": "0.2",
            "config_type": "yaml",
        },
        "configuration": {
            "host": data.get(CONF_HOST, "not_configured"),
            "msgformat": data.get(CONF_FORMAT, "not_configured"),
            "devicename": data.get(CONF_NAME, "not_configured"),
            "parameters": data.get(CONF_PARAMS, "not_configured"),
            "language": data.get(CONF_LANG, "not_configured"),
            "unique_id": data.get(CONF_UNIQUE_ID, "not_configured"),
        },
        "entities": {},
    }

    # Get all states for nano_pk entities
    for state in hass.states.async_all():
        # Check if entity belongs to this integration
        if not state.entity_id.startswith("sensor."):
            continue

        # Simple check: if entity has our domain's unique attributes
        if state.entity_id.startswith(f"sensor.{data.get(CONF_NAME, 'hargassner').lower()}"):
            entity_data = {
                "entity_id": state.entity_id,
                "state": state.state,
                "attributes": dict(state.attributes),
            }

            # Add connection-specific diagnostics for bridge entities
            if "connection" in state.entity_id.lower():
                entity_data["connection_stats"] = {
                    "host": state.attributes.get("host"),
                    "total_reconnects": state.attributes.get("total_reconnects"),
                    "connection_attempts": state.attributes.get("connection_attempts"),
                    "last_update": state.attributes.get("last_update"),
                    "last_error": state.attributes.get("last_error"),
                    "next_retry_delay_seconds": state.attributes.get("next_retry_delay_seconds"),
                }

            # Add error sensor specific diagnostics
            if "operation" in state.entity_id.lower():
                # Try to get DE.CSV diagnostics from the HargassnerErrorSensor class
                try:
                    from .sensor import HargassnerErrorSensor
                    csv_diag = HargassnerErrorSensor.get_csv_diagnostics()
                    entity_data["de_csv_info"] = csv_diag
                except Exception as e:
                    entity_data["de_csv_error"] = str(e)

            diagnostics["entities"][state.entity_id] = entity_data

    return diagnostics
