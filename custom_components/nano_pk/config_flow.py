"""Config flow for Hargassner Nano-PK integration.

Created by @Django1982 with Claude Code
Special thanks to @TheRealKillaruna for the original integration
"""
from __future__ import annotations

import logging
import socket
import telnetlib
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_FORMAT,
    CONF_FORMAT_CONTENT,
    CONF_NAME,
    CONF_PARAMS,
    CONF_PARAMS_STANDARD,
    CONF_PARAMS_FULL,
    CONF_LANG,
    CONF_LANG_EN,
    CONF_LANG_DE,
    CONF_UNIQUE_ID,
)
from .daq_fetcher import async_fetch_daq_template, DaqFetchError

_LOGGER = logging.getLogger(__name__)

# Template selection constants
TEMPLATE_AUTO_FETCH = "auto_fetch"
TEMPLATE_CUSTOM = "custom"
TEMPLATE_NANO_PK_FULL = "NANO_PK_FULL"

# Available templates
AVAILABLE_TEMPLATES = {
    TEMPLATE_AUTO_FETCH: "Fetch from boiler via telnet ($DAQ DESC)",
    TEMPLATE_NANO_PK_FULL: "Hargassner Nano-PK (Full - 97 channels)",
    TEMPLATE_CUSTOM: "Custom XML (paste your own)",
}


class HargassnerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hargassner Nano-PK."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._name: str | None = None
        self._template: str | None = None
        self._custom_xml: str | None = None
        self._de_csv: str | None = None
        self._params: str = CONF_PARAMS_STANDARD
        self._lang: str = CONF_LANG_EN

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Import a config entry from YAML configuration."""
        # Check if already configured
        await self.async_set_unique_id(import_data.get(CONF_UNIQUE_ID))
        self._abort_if_unique_id_configured()

        _LOGGER.info("Importing Hargassner Nano-PK configuration from YAML")

        # Use the existing YAML configuration directly
        return self.async_create_entry(
            title=import_data.get(CONF_NAME, "Hargassner"),
            data={
                CONF_HOST: import_data[CONF_HOST],
                CONF_NAME: import_data.get(CONF_NAME, "Hargassner"),
                CONF_FORMAT: import_data[CONF_FORMAT],
                CONF_FORMAT_CONTENT: import_data.get(CONF_FORMAT_CONTENT),
                CONF_PARAMS: import_data.get(CONF_PARAMS, CONF_PARAMS_STANDARD),
                CONF_LANG: import_data.get(CONF_LANG, CONF_LANG_EN),
                CONF_UNIQUE_ID: import_data.get(CONF_UNIQUE_ID, "1"),
            },
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reconfiguration of the integration (e.g., after firmware update)."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            # Update the config entry with new data
            self.hass.config_entries.async_update_entry(
                entry,
                data={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_NAME: entry.data[CONF_NAME],  # Keep existing name
                    CONF_FORMAT: entry.data[CONF_FORMAT],  # Will be updated in XML step
                    CONF_FORMAT_CONTENT: entry.data.get(CONF_FORMAT_CONTENT),
                    CONF_PARAMS: entry.data[CONF_PARAMS],
                    CONF_LANG: entry.data[CONF_LANG],
                    CONF_UNIQUE_ID: entry.data[CONF_UNIQUE_ID],
                },
            )

            # Store host for next steps
            self._host = user_input[CONF_HOST]

            # Test connection
            try:
                await self._test_connection(self._host)
            except ConnectionError:
                return self.async_abort(reason="cannot_connect")

            # Move to template selection
            return await self.async_step_reconfigure_template()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): cv.string,
                }
            ),
            description_placeholders={
                "current_config": f"Current: {entry.data[CONF_HOST]}"
            },
        )

    async def async_step_reconfigure_template(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle template selection during reconfiguration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._custom_xml = entry.data.get(CONF_FORMAT_CONTENT)
        errors: dict[str, str] = {}

        if user_input is not None:
            self._template = user_input["template"]

            if self._template == TEMPLATE_CUSTOM:
                return await self.async_step_reconfigure_custom_xml()
            if self._template == TEMPLATE_AUTO_FETCH:
                try:
                    xml_content = await async_fetch_daq_template(self._host)
                except DaqFetchError as err:
                    _LOGGER.error("Failed to fetch DAQ template: %s", err)
                    errors["base"] = "fetch_failed"
                else:
                    self._custom_xml = xml_content
                    return await self.async_step_reconfigure_custom_xml()
            else:
                try:
                    xml_content = await self._load_template(self._template)
                    await self._validate_xml(xml_content)
                    self._custom_xml = xml_content
                    return await self.async_step_reconfigure_de_csv()
                except ValueError:
                    errors["base"] = "invalid_xml"

        return self.async_show_form(
            step_id="reconfigure_template",
            data_schema=vol.Schema(
                {
                    vol.Required("template", default=TEMPLATE_NANO_PK_FULL): vol.In(
                        AVAILABLE_TEMPLATES
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_custom_xml(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle custom XML during reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            xml_content = user_input["xml_content"]

            try:
                await self._validate_xml(xml_content)
                self._custom_xml = xml_content
                return await self.async_step_reconfigure_de_csv()
            except ValueError:
                errors["base"] = "invalid_xml"

        return self.async_show_form(
            step_id="reconfigure_custom_xml",
            data_schema=vol.Schema(
                {
                    vol.Required("xml_content", default=self._custom_xml or ""): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_de_csv(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle DE.CSV during reconfiguration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}

        if user_input is not None:
            de_csv_content = user_input.get("de_csv_content", "").strip()

            if de_csv_content:
                try:
                    await self._validate_de_csv(de_csv_content)
                    self._de_csv = de_csv_content
                except ValueError:
                    errors["base"] = "invalid_csv"

            if not errors:
                # Save XML file
                xml_filename = f"{entry.data[CONF_NAME].lower().replace(' ', '_')}.xml"
                xml_path = Path(__file__).parent / "msgformats" / xml_filename

                try:
                    await self.hass.async_add_executor_job(
                        xml_path.write_text, self._custom_xml, "utf-8"
                    )
                except Exception:
                    return self.async_abort(reason="cannot_save_xml")

                # Save DE.CSV if provided
                if self._de_csv:
                    csv_path = Path(__file__).parent / "DE.CSV"
                    try:
                        await self.hass.async_add_executor_job(
                            csv_path.write_text, self._de_csv, "latin-1"
                        )
                    except Exception as err:
                        _LOGGER.warning("Failed to save DE.CSV: %s", err)

                # Update config entry
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_HOST: self._host,
                        CONF_NAME: entry.data[CONF_NAME],
                        CONF_FORMAT: xml_filename,
                        CONF_FORMAT_CONTENT: self._custom_xml,
                        CONF_PARAMS: entry.data[CONF_PARAMS],
                        CONF_LANG: entry.data[CONF_LANG],
                        CONF_UNIQUE_ID: entry.data[CONF_UNIQUE_ID],
                    },
                )

                # Reload the integration
                await self.hass.config_entries.async_reload(entry.entry_id)

                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure_de_csv",
            data_schema=vol.Schema(
                {
                    vol.Optional("de_csv_content", default=""): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - basic configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._name = user_input[CONF_NAME]
            self._params = user_input[CONF_PARAMS]
            self._lang = user_input[CONF_LANG]

            # Test connection
            try:
                await self._test_connection(self._host)
            except ConnectionError as err:
                _LOGGER.error("Connection test failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during connection test")
                errors["base"] = "unknown"
            else:
                # Connection successful, move to template selection
                return await self.async_step_template()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_NAME, default="Hargassner"): cv.string,
                    vol.Required(CONF_PARAMS, default=CONF_PARAMS_STANDARD): vol.In(
                        [CONF_PARAMS_STANDARD, CONF_PARAMS_FULL]
                    ),
                    vol.Required(CONF_LANG, default=CONF_LANG_EN): vol.In(
                        [CONF_LANG_EN, CONF_LANG_DE]
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_template(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle template selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._template = user_input["template"]

            if self._template == TEMPLATE_CUSTOM:
                # User wants to provide custom XML
                return await self.async_step_custom_xml()
            if self._template == TEMPLATE_AUTO_FETCH:
                try:
                    xml_content = await async_fetch_daq_template(self._host)
                except DaqFetchError as err:
                    _LOGGER.error("Failed to fetch DAQ template: %s", err)
                    errors["base"] = "fetch_failed"
                else:
                    self._custom_xml = xml_content
                    return await self.async_step_custom_xml()
            else:
                # Load selected template
                try:
                    xml_content = await self._load_template(self._template)
                    # Validate XML
                    await self._validate_xml(xml_content)
                    # Save as msgformat
                    self._custom_xml = xml_content
                    # Move to DE.CSV step
                    return await self.async_step_de_csv()
                except ValueError as err:
                    _LOGGER.error("Template validation failed: %s", err)
                    errors["base"] = "invalid_xml"
                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.exception("Failed to load template")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="template",
            data_schema=vol.Schema(
                {
                    vol.Required("template", default=TEMPLATE_NANO_PK_FULL): vol.In(
                        AVAILABLE_TEMPLATES
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "templates_info": "Fetch the DAQPRJ XML directly from your boiler, select a built-in template, or choose 'Custom' to paste your own."
            },
        )

    async def async_step_custom_xml(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle custom XML input step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            xml_content = user_input["xml_content"]

            try:
                # Validate XML
                await self._validate_xml(xml_content)
                self._custom_xml = xml_content
                # Move to DE.CSV step
                return await self.async_step_de_csv()
            except ValueError as err:
                _LOGGER.error("XML validation failed: %s", err)
                errors["base"] = "invalid_xml"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error validating XML")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="custom_xml",
            data_schema=vol.Schema(
                {
                    vol.Required("xml_content", default=self._custom_xml or ""): cv.string,
                }
            ),
            errors=errors,
            description_placeholders={
                "xml_help": "Paste your DAQPRJ XML content here. You can export this from your Hargassner boiler's web interface."
            },
        )

    async def async_step_de_csv(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle DE.CSV file input step (optional)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            de_csv_content = user_input.get("de_csv_content", "").strip()

            if de_csv_content:
                # Validate CSV format (basic check)
                try:
                    await self._validate_de_csv(de_csv_content)
                    self._de_csv = de_csv_content
                except ValueError as err:
                    _LOGGER.error("DE.CSV validation failed: %s", err)
                    errors["base"] = "invalid_csv"

            if not errors:
                # Create the entry
                return await self._create_entry()

        return self.async_show_form(
            step_id="de_csv",
            data_schema=vol.Schema(
                {
                    vol.Optional("de_csv_content", default=""): cv.string,
                }
            ),
            errors=errors,
            description_placeholders={
                "csv_help": "Optional: Paste your DE.CSV content for extended error code translations. You can skip this step and add it later."
            },
        )

    async def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        # Generate unique ID based on host
        await self.async_set_unique_id(f"{self._host}_{self._name}")
        self._abort_if_unique_id_configured()

        # Save XML file to integration directory
        xml_filename = f"{self._name.lower().replace(' ', '_')}.xml"
        xml_path = Path(__file__).parent / "msgformats" / xml_filename

        try:
            await self.hass.async_add_executor_job(
                xml_path.write_text, self._custom_xml, "utf-8"
            )
        except Exception as err:
            _LOGGER.exception("Failed to save XML file")
            return self.async_abort(reason="cannot_save_xml")

        # Save DE.CSV if provided
        if self._de_csv:
            csv_path = Path(__file__).parent / "DE.CSV"
            try:
                await self.hass.async_add_executor_job(
                    csv_path.write_text, self._de_csv, "latin-1"
                )
            except Exception as err:
                _LOGGER.warning("Failed to save DE.CSV file: %s", err)
                # Non-fatal, continue anyway

        return self.async_create_entry(
            title=self._name,
            data={
                CONF_HOST: self._host,
                CONF_NAME: self._name,
                CONF_FORMAT: xml_filename,
                CONF_FORMAT_CONTENT: self._custom_xml,
                CONF_PARAMS: self._params,
                CONF_LANG: self._lang,
                CONF_UNIQUE_ID: f"{self._host}_{self._name}",
            },
        )

    async def _test_connection(self, host: str) -> None:
        """Test connection to the boiler."""

        def _sync_test() -> None:
            """Synchronous connection test."""
            try:
                # Test TCP connection on port 23
                with socket.create_connection((host, 23), timeout=5):
                    pass
            except (socket.timeout, OSError) as err:
                raise ConnectionError(f"Cannot connect to {host}:23") from err

        await self.hass.async_add_executor_job(_sync_test)

    async def _load_template(self, template_name: str) -> str:
        """Load a template XML file."""
        template_path = Path(__file__).parent / "msgformats" / f"{template_name}.xml"

        if not template_path.exists():
            raise ValueError(f"Template {template_name} not found")

        return await self.hass.async_add_executor_job(
            template_path.read_text, "utf-8"
        )

    async def _validate_xml(self, xml_content: str) -> None:
        """Validate DAQPRJ XML structure."""

        def _sync_validate() -> None:
            """Synchronous XML validation."""
            try:
                root = ET.fromstring(xml_content)
                if root.tag != "DAQPRJ":
                    raise ValueError("Root element must be <DAQPRJ>")

                # Check for ANALOG or DIGITAL sections
                analog = root.find("ANALOG")
                digital = root.find("DIGITAL")

                if analog is None and digital is None:
                    raise ValueError(
                        "XML must contain at least one <ANALOG> or <DIGITAL> section"
                    )

                # Basic channel validation
                if analog is not None:
                    channels = analog.findall("CHANNEL")
                    if not channels:
                        raise ValueError("<ANALOG> section must contain CHANNEL elements")

                if digital is not None:
                    channels = digital.findall("CHANNEL")
                    if not channels:
                        raise ValueError("<DIGITAL> section must contain CHANNEL elements")

            except ET.ParseError as err:
                raise ValueError(f"Invalid XML syntax: {err}") from err

        await self.hass.async_add_executor_job(_sync_validate)

    async def _validate_de_csv(self, csv_content: str) -> None:
        """Validate DE.CSV format."""

        def _sync_validate() -> None:
            """Synchronous CSV validation."""
            lines = csv_content.strip().split("\n")
            if len(lines) < 1:
                raise ValueError("DE.CSV must contain at least one line")

            # Basic format check: should have semicolon-separated values
            for line in lines[:5]:  # Check first 5 lines
                if ";" not in line:
                    raise ValueError("DE.CSV must use semicolon (;) as delimiter")

        await self.hass.async_add_executor_job(_sync_validate)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HargassnerOptionsFlowHandler:
        """Get the options flow for this handler."""
        return HargassnerOptionsFlowHandler(config_entry)


class HargassnerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Hargassner integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PARAMS,
                        default=self.config_entry.data.get(
                            CONF_PARAMS, CONF_PARAMS_STANDARD
                        ),
                    ): vol.In([CONF_PARAMS_STANDARD, CONF_PARAMS_FULL]),
                    vol.Required(
                        CONF_LANG,
                        default=self.config_entry.data.get(CONF_LANG, CONF_LANG_EN),
                    ): vol.In([CONF_LANG_EN, CONF_LANG_DE]),
                }
            ),
        )
