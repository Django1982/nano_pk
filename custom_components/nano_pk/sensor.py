"""Platform for sensor integration.

Original code by @TheRealKillaruna
Config entry support and async improvements by @Django1982 with Claude Code
"""
import csv
import io
import logging
import re
from pathlib import Path
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.util import file as file_util
from .const import (
    DOMAIN,
    CONF_HOST,
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
    BRIDGE_STATE_OK,
)
from .hargassner import HargassnerBridge


_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up sensors from a config entry (UI setup)."""
    # Load extended error codes asynchronously before creating sensors
    await HargassnerErrorSensor._async_ensure_extended_errors_loaded(hass)

    host = entry.data[CONF_HOST]
    format_file = entry.data.get(CONF_FORMAT_CONTENT) or entry.data[CONF_FORMAT]
    name = entry.data[CONF_NAME]
    paramSet = entry.data[CONF_PARAMS]
    lang = entry.data[CONF_LANG]
    uniqueId = entry.data[CONF_UNIQUE_ID]

    # Create bridge and sensors using shared logic
    await _setup_sensors(
        hass, async_add_entities, host, format_file, name, paramSet, lang, uniqueId
    )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None) -> None:
    """Set up the sensor platform (YAML setup)."""
    # Load extended error codes asynchronously before creating sensors
    await HargassnerErrorSensor._async_ensure_extended_errors_loaded(hass)

    host = hass.data[DOMAIN][CONF_HOST]
    format_file = hass.data[DOMAIN].get(CONF_FORMAT_CONTENT) or hass.data[DOMAIN][CONF_FORMAT]
    name = hass.data[DOMAIN][CONF_NAME]
    paramSet = hass.data[DOMAIN][CONF_PARAMS]
    lang = hass.data[DOMAIN][CONF_LANG]
    uniqueId = hass.data[DOMAIN][CONF_UNIQUE_ID]

    # Create bridge and sensors using shared logic
    await _setup_sensors(
        hass, async_add_entities, host, format_file, name, paramSet, lang, uniqueId
    )


async def _resolve_msg_format(hass, format_source: str | None) -> str | None:
    """Resolve msgformat source into XML content."""
    if not format_source:
        _LOGGER.error("No message format provided; cannot set up sensors.")
        return None

    source_str = str(format_source).strip()
    if source_str.startswith("<DAQPRJ"):
        return source_str

    needs_file = source_str.endswith(".xml") or "/" in source_str or "\\" in source_str

    if needs_file:
        path = Path(source_str)
        if not path.is_absolute():
            path = Path(__file__).parent / "msgformats" / source_str
        if not path.exists():
            _LOGGER.error("Message format file not found: %s", path)
            return None
        try:
            return await hass.async_add_executor_job(path.read_text, "utf-8")
        except Exception as err:
            _LOGGER.error("Failed to read message format file %s: %s", path, err)
            return None

    return source_str


async def _setup_sensors(
    hass, async_add_entities, host, format_source, name, paramSet, lang, uniqueId
) -> None:
    """Shared sensor setup logic for both YAML and Config Entry."""
    msg_format = await _resolve_msg_format(hass, format_source)
    if msg_format is None:
        return

    bridge = HargassnerBridge(host, name, uniqueId, msgFormat=msg_format)
    errorLog = bridge.getErrorLog()
    if errorLog != "": _LOGGER.error(errorLog)
    param_keys = set(bridge.data().keys())

    def _has_param(param_name: str) -> bool:
        return param_name in param_keys

    def _warn_missing(param_name: str, context: str) -> None:
        _LOGGER.warning(
            "Parameter '%s' not provided by configured msgformat; skipping %s.",
            param_name,
            context,
        )

    if paramSet == CONF_PARAMS_FULL:
        entities = [bridge]
        for p in bridge.data().values(): 
            if p.key()=="Störung": 
                entities.append(HargassnerErrorSensor(bridge, name))
            elif p.key()=="ZK": 
                entities.append(HargassnerStateSensor(bridge, name, lang))
            else:
                entities.append(HargassnerSensor(bridge, name+" "+p.description(), p.key()))
        if _has_param("Verbrauchszähler"):
            entities.append(HargassnerEnergySensor(bridge, name))
        else:
            _warn_missing("Verbrauchszähler", "energy sensor")
        async_add_entities(entities)
    else:
        entities = [bridge]

        def _add_sensor_if_available(param_name: str, context: str, factory):
            if _has_param(param_name):
                entities.append(factory())
            else:
                _warn_missing(param_name, context)

        _add_sensor_if_available("Störung", "error sensor", lambda: HargassnerErrorSensor(bridge, name))
        _add_sensor_if_available("ZK", "state sensor", lambda: HargassnerStateSensor(bridge, name, lang))
        _add_sensor_if_available("TK", "boiler temperature sensor", lambda: HargassnerSensor(bridge, name+" boiler temperature", "TK"))
        _add_sensor_if_available("TRG", "smoke gas temperature sensor", lambda: HargassnerSensor(bridge, name+" smoke gas temperature", "TRG"))
        _add_sensor_if_available("Leistung", "output sensor", lambda: HargassnerSensor(bridge, name+" output", "Leistung", "mdi:fire"))
        _add_sensor_if_available("Taus", "outside temperature sensor", lambda: HargassnerSensor(bridge, name+" outside temperature", "Taus"))
        _add_sensor_if_available("TB1", "buffer temperature 0 sensor", lambda: HargassnerSensor(bridge, name+" buffer temperature 0", "TB1", "mdi:thermometer-lines"))
        _add_sensor_if_available("TPo", "buffer temperature 1 sensor", lambda: HargassnerSensor(bridge, name+" buffer temperature 1", "TPo", "mdi:thermometer-lines"))
        _add_sensor_if_available("TPm", "buffer temperature 2 sensor", lambda: HargassnerSensor(bridge, name+" buffer temperature 2", "TPm", "mdi:thermometer-lines"))
        _add_sensor_if_available("TPu", "buffer temperature 3 sensor", lambda: HargassnerSensor(bridge, name+" buffer temperature 3", "TPu", "mdi:thermometer-lines"))
        _add_sensor_if_available("TRL", "return temperature sensor", lambda: HargassnerSensor(bridge, name+" return temperature", "TRL", "mdi:coolant-temperature"))
        _add_sensor_if_available("Puff Füllgrad", "buffer level sensor", lambda: HargassnerSensor(bridge, name+" buffer level", "Puff Füllgrad", "mdi:gauge"))
        _add_sensor_if_available("Lagerstand", "pellet stock sensor", lambda: HargassnerSensor(bridge, name+" pellet stock", "Lagerstand", "mdi:silo"))
        _add_sensor_if_available("TVL_1", "flow temperature sensor", lambda: HargassnerSensor(bridge, name+" flow temperature", "TVL_1", "mdi:coolant-temperature"))

        if _has_param("Verbrauchszähler"):
            entities.append(HargassnerSensor(bridge, name+" pellet consumption", "Verbrauchszähler", "mdi:basket-unfill"))
            entities.append(HargassnerEnergySensor(bridge, name))
        else:
            _warn_missing("Verbrauchszähler", "pellet consumption and energy sensors")

        async_add_entities(entities)


class HargassnerSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, bridge, description, paramName, icon=None):
        """Initialize the sensor."""
        self._value = None
        self._bridge = bridge
        self._description = description
        self._paramName = paramName
        self._icon = icon
        self._unique_id = bridge.getUniqueIdBase()
        self._unit = bridge.getUnit(paramName)
        sc = bridge.getStateClass(paramName)
        if (self._unit==None):
            self._stateClass = None
            self._deviceClass = SensorDeviceClass.ENUM
            self._options = ["True", "False"]
        else:
            if sc=="measurement": self._stateClass = SensorStateClass.MEASUREMENT
            elif sc=="total": self._stateClass = SensorStateClass.TOTAL
            elif sc=="total_increasing": self._stateClass = SensorStateClass.TOTAL_INCREASING
            if self._unit=="°C": self._deviceClass = SensorDeviceClass.TEMPERATURE
            else: self._deviceClass = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._description

    @property
    def device_class(self):
        """Return the state of the sensor."""
        return self._deviceClass

    @property
    def state_class(self):
        """Return the state of the sensor."""
        return self._stateClass

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return an icon for the sensor in the GUI."""
        return self._icon
        
    @property
    def available(self):
        if self._bridge.state == BRIDGE_STATE_OK: return True
        else: return False

    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._value = self._bridge.getValue(self._paramName)

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._unique_id + self._paramName


class HargassnerEnergySensor(HargassnerSensor):

    def __init__(self, bridge, deviceName):
        super().__init__(bridge, deviceName+" energy consumption", "Verbrauchszähler", "mdi:radiator")
        self._deviceClass = SensorDeviceClass.ENERGY
        self._unit = "kWh"

    async def async_update(self):
        try:
            self._value = 4.8 * float(self._bridge.getValue(self._paramName))
        except Exception:
            _LOGGER.warning("HargassnerEnergySensor.update(): Invalid value.\n")
            self._value = None

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._unique_id + self._paramName + "-E"


class HargassnerErrorSensor(HargassnerSensor):

    ERRORS = {
        "5" : "Aschelade entleeren", 
        "6" : "Aschelade zu voll", 
       "29" : "Verbrennungsstörung", 
       "30" : "Batterie leer", 
       "31" : "Blockade Einschubmotor", 
       "32" : "Füllzeit überschritten", 
       "70" : "Pelletslagerstand niedrig", 
       "89" : "Schieberost schwergängig", 
       "93" : "Aschelade offen", 
      "155" : "Spülung defekt", 
      "227" : "Lagerraumschalter aus", 
      "228" : "Pelletsbehälter fast leer", 
      "229" : "Füllstandsmelder kontrollieren", 
      "371" : "Brennraum prüfen"
    }
    _extended_errors_loaded = False

    def __init__(self, bridge, deviceName):
        super().__init__(bridge, deviceName+" operation", "Störung", "mdi:alert")
        self._stateClass = None
        self._deviceClass = SensorDeviceClass.ENUM
        # Extended errors are loaded asynchronously in async_setup_platform
        option_values = {"OK", "Unknown", "Unknown Error"}
        option_values.update(self.ERRORS.values())
        self._options = sorted(option_values)

    async def async_update(self):
        rawState = self._bridge.getValue(self._paramName)
        if rawState==None: self._value = "Unknown"
        elif rawState=="False":
            self._value = "OK"
            self._icon = "mdi:check"
        else:
            try:
                errorID = self._bridge.getValue("Störungs Nr")
                normalized_id = self._normalize_error_id(errorID)
                errorDescr = self.ERRORS.get(normalized_id)
                if errorDescr is None and errorID is not None:
                    errorDescr = self.ERRORS.get(str(errorID))
                if errorDescr is None:
                    shown_id = errorID if errorID is not None else "Unknown"
                    self._value = "Error " + str(shown_id)
                else:
                    self._value = errorDescr
            except Exception:
                _LOGGER.warning("HargassnerErrorSensor.update(): Invalid error ID.\n")
                self._value = "Unknown Error"
            self._icon = "mdi:alert"
        errorLog = self._bridge.getErrorLog()
        if errorLog != "": _LOGGER.error(errorLog)
        infoLog = self._bridge.getInfoLog()
        if infoLog != "": _LOGGER.info(infoLog)

    @classmethod
    async def _async_ensure_extended_errors_loaded(cls, hass: HomeAssistant):
        """Load extended error codes from DE.CSV file (async, non-blocking)."""
        if cls._extended_errors_loaded:
            return
        translations = {}
        csv_path = Path(__file__).with_name("DE.CSV")
        if csv_path.exists():
            try:
                # Use Home Assistant's async file read utility
                content = await hass.async_add_executor_job(
                    lambda: csv_path.read_text(encoding="latin-1")
                )

                # Parse CSV from string (non-blocking)
                reader = csv.reader(io.StringIO(content), delimiter=';')
                for row in reader:
                    if len(row) < 3:
                        continue
                    key, text = row[0], row[2]
                    if not key.startswith("T21_ERR_") or key.endswith("_DESC"):
                        continue
                    normalized_key = cls._normalize_error_id(key)
                    if not normalized_key or not text:
                        continue
                    cleaned_text = " ".join(text.split())
                    translations.setdefault(normalized_key, cleaned_text)
            except Exception as exc:
                _LOGGER.warning(
                    "HargassnerErrorSensor: Failed loading extended errors from DE.CSV (%s).",
                    exc,
                )
            else:
                if translations:
                    cls.ERRORS.update({k: v for k, v in translations.items() if k not in cls.ERRORS})
                    _LOGGER.info(
                        "HargassnerErrorSensor: Loaded %d extended error codes from DE.CSV",
                        len(translations)
                    )
        else:
            _LOGGER.debug("HargassnerErrorSensor: DE.CSV not found; extended errors unavailable.")
        cls._extended_errors_loaded = True

    @staticmethod
    def _normalize_error_id(error_id):
        if error_id is None:
            return ""
        if not isinstance(error_id, str):
            error_id = str(error_id)
        normalized = error_id.strip().upper()
        normalized = normalized.replace(" ", "_").replace("-", "_").replace("\n", "_")
        return re.sub(r"^T\d+_", "", normalized)

    @classmethod
    def get_csv_diagnostics(cls) -> dict:
        """Return diagnostics about DE.CSV loading status."""
        csv_path = Path(__file__).with_name("DE.CSV")

        diagnostics = {
            "csv_file": {
                "path": str(csv_path),
                "exists": csv_path.exists(),
                "size_bytes": csv_path.stat().st_size if csv_path.exists() else None,
            },
            "error_codes": {
                "built_in_count": 14,  # Original hardcoded errors
                "total_loaded_count": len(cls.ERRORS),
                "extended_errors_loaded": cls._extended_errors_loaded,
                "loaded_from_csv": len(cls.ERRORS) - 14 if cls._extended_errors_loaded else 0,
            },
            "sample_error_codes": list(cls.ERRORS.keys())[:20],  # First 20 error codes
        }

        # Try to get CSV stats if file exists
        if csv_path.exists():
            try:
                with csv_path.open("r", encoding="latin-1") as csvfile:
                    reader = csv.reader(csvfile, delimiter=';')
                    total_rows = sum(1 for _ in reader)

                diagnostics["csv_file"]["total_rows"] = total_rows
            except Exception as e:
                diagnostics["csv_file"]["read_error"] = str(e)

        return diagnostics


class HargassnerStateSensor(HargassnerSensor):

    _STATE_LABELS = {
        CONF_LANG_DE: {
            0: "Unbekannt",
            1: "Aus",
            2: "Zünd. warten",
            3: "Anheizen",
            4: "Zündüberwachung",
            5: "Zündung",
            6: "Leistungsbrand",
            7: "Übergang LB",
            8: "Gluterhaltung",
            9: "Ausbrand",
            10: "Entaschung",
            11: "Restwärme",
            12: "Übertemperatur",
            13: "Störung aktiv",
        },
        CONF_LANG_EN: {
            0: "Unknown",
            1: "Off",
            2: "Preparing start",
            3: "Boiler start",
            4: "Monitoring ignition",
            5: "Ignition",
            6: "Full firing",
            7: "Transition to full firing",
            8: "Ember preservation",
            9: "Waiting for AR",
            10: "Ash removal",
            11: "Cleaning",
            12: "Over-temperature",
            13: "Fault active",
        },
    }

    def __init__(self, bridge, deviceName, lang):
        super().__init__(bridge, deviceName+" boiler state", "ZK")
        self._stateClass = None
        self._deviceClass = SensorDeviceClass.ENUM
        self._language = lang if lang in (CONF_LANG_DE, CONF_LANG_EN) else CONF_LANG_EN
        self._labels = dict(self._STATE_LABELS[self._language])
        self._fallback_prefix = "Zustand" if self._language == CONF_LANG_DE else "State"
        self._options_set = set(self._labels.values())
        self._options = sorted(self._options_set)

    async def async_update(self):
        rawState = self._bridge.getValue(self._paramName)
        try:
            idxState = int(round(float(rawState)))
            if idxState not in self._labels:
                _LOGGER.debug(
                    "HargassnerStateSensor: unmapped state code %s (raw=%s).",
                    idxState,
                    rawState,
                )
        except (TypeError, ValueError):
            _LOGGER.warning("HargassnerStateSensor.update(): Invalid state (%s).", rawState)
            idxState = 0
        label = self._labels.get(idxState)
        if label is None:
            label = f"{self._fallback_prefix} {idxState}"
            if label not in self._options_set:
                self._options_set.add(label)
                self._options = sorted(self._options_set)
        self._value = label
        if idxState in (6, 7):
            self._icon = "mdi:fireplace"
        else:
            self._icon = "mdi:fireplace-off"
