"""The Hargassner Nano-PK boiler temperature sensor integration.

Original code by @TheRealKillaruna
Major improvements and config flow by @Django1982 with Claude Code
"""
import json
import logging

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import discovery
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_FORMAT,
    CONF_FORMAT_CONTENT,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_PARAMS,
    CONF_PARAMS_STANDARD,
    CONF_PARAMS_FULL,
    CONF_LANG,
    CONF_LANG_EN,
    CONF_LANG_DE
)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_FORMAT): cv.string,
        vol.Optional(CONF_NAME, default="Hargassner"): cv.string,
        vol.Optional(CONF_UNIQUE_ID, default="1"): cv.string,
        vol.Optional(CONF_PARAMS, default=CONF_PARAMS_STANDARD): vol.In([CONF_PARAMS_STANDARD, CONF_PARAMS_FULL]),
        vol.Optional(CONF_LANG, default=CONF_LANG_EN): vol.In([CONF_LANG_EN, CONF_LANG_DE]),
    })
}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Hargassner Nano-PK integration via YAML."""
    if DOMAIN not in config:
        return True

    # Initialize domain data if not exists
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Prepare import data
    yaml_config = {
        CONF_HOST: config[DOMAIN].get(CONF_HOST),
        CONF_NAME: config[DOMAIN].get(CONF_NAME, "Hargassner"),
        CONF_FORMAT: config[DOMAIN].get(CONF_FORMAT),
        CONF_FORMAT_CONTENT: config[DOMAIN].get(CONF_FORMAT_CONTENT),
        CONF_PARAMS: config[DOMAIN].get(CONF_PARAMS, CONF_PARAMS_STANDARD),
        CONF_LANG: config[DOMAIN].get(CONF_LANG, CONF_LANG_EN),
        CONF_UNIQUE_ID: config[DOMAIN].get(CONF_UNIQUE_ID, "1"),
    }

    # Trigger import flow to create config entry
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=yaml_config,
        )
    )

    # Store YAML config temporarily for sensor platform (backward compatibility during transition)
    hass.data[DOMAIN]["yaml_config"] = yaml_config
    hass.data[DOMAIN][CONF_HOST] = yaml_config[CONF_HOST]
    hass.data[DOMAIN][CONF_NAME] = yaml_config[CONF_NAME]
    hass.data[DOMAIN][CONF_FORMAT] = yaml_config[CONF_FORMAT]
    hass.data[DOMAIN][CONF_FORMAT_CONTENT] = yaml_config.get(CONF_FORMAT_CONTENT)
    hass.data[DOMAIN][CONF_PARAMS] = yaml_config[CONF_PARAMS]
    hass.data[DOMAIN][CONF_LANG] = yaml_config[CONF_LANG]
    hass.data[DOMAIN][CONF_UNIQUE_ID] = yaml_config[CONF_UNIQUE_ID]

    # Keep legacy sensor platform setup for now (will be handled by config entry after import)
    # This ensures no downtime during migration
    hass.async_create_task(
        discovery.async_load_platform(hass, 'sensor', DOMAIN, {}, config)
    )

    # Register diagnostics service (only once)
    if not hass.services.has_service(DOMAIN, "get_diagnostics"):
        async def handle_get_diagnostics(call: ServiceCall) -> None:
            """Handle the get_diagnostics service call."""
            from .diagnostics import async_get_integration_diagnostics
            from pathlib import Path

            diag_data = await async_get_integration_diagnostics(hass)

            # Write to both log and file
            diag_json = json.dumps(diag_data, indent=2, ensure_ascii=False)
            _LOGGER.info("Hargassner Nano-PK Diagnostics:\n%s", diag_json)

            # Also write to /config/nano_pk_diagnostics.json
            diag_file = Path("/config/nano_pk_diagnostics.json")
            await hass.async_add_executor_job(diag_file.write_text, diag_json, "utf-8")
            _LOGGER.info(
                "Diagnostics also saved to: %s",
                str(diag_file)
            )

        hass.services.async_register(DOMAIN, "get_diagnostics", handle_get_diagnostics)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hargassner Nano-PK from a config entry (UI setup)."""
    # Initialize domain data if not exists
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Store config entry data with unique identifier
    entry_id = entry.entry_id
    hass.data[DOMAIN][entry_id] = entry.data

    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    # Register diagnostics service (only once)
    if not hass.services.has_service(DOMAIN, "get_diagnostics"):
        async def handle_get_diagnostics(call: ServiceCall) -> None:
            """Handle the get_diagnostics service call."""
            from .diagnostics import async_get_integration_diagnostics
            from pathlib import Path

            diag_data = await async_get_integration_diagnostics(hass)

            # Write to both log and file
            diag_json = json.dumps(diag_data, indent=2, ensure_ascii=False)
            _LOGGER.info("Hargassner Nano-PK Diagnostics:\n%s", diag_json)

            # Also write to /config/nano_pk_diagnostics.json
            diag_file = Path("/config/nano_pk_diagnostics.json")
            await hass.async_add_executor_job(diag_file.write_text, diag_json, "utf-8")
            _LOGGER.info(
                "Diagnostics also saved to: %s",
                str(diag_file)
            )

        hass.services.async_register(DOMAIN, "get_diagnostics", handle_get_diagnostics)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
