"""Platform for sensor integration."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import (
    CONF_NAME,
    CONF_IP_ADDRESS,
    UnitOfPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta
import asyncio
import async_timeout
import re

from .const import DOMAIN, DEVICE_TYPE_SWITCH, CONF_DEVICE_TYPE
from .cozylife_device import CozyLifeDevice
import logging

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=5)
TIMEOUT = 5

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BetterCozyLife sensors."""
    config = config_entry.data

    if config[CONF_DEVICE_TYPE] == DEVICE_TYPE_SWITCH:
        device = CozyLifeDevice(config[CONF_IP_ADDRESS])
        currentSensor = BetterCozyLifeCurrentSensor(config, config_entry.entry_id, device)
        powerSensor = BetterCozyLifePowerSensor(config, config_entry.entry_id, device)
        voltageSensor = BetterCozyLifeVoltageSensor(config, config_entry.entry_id, device)
        async_add_entities([currentSensor, powerSensor, voltageSensor])

        async def refresh_state(now=None):
            """Refresh sensor state."""
            try:
                async with async_timeout.timeout(TIMEOUT):
                    await hass.async_add_executor_job(currentSensor.update)
                    await hass.async_add_executor_job(powerSensor.update)
                    await hass.async_add_executor_job(voltageSensor.update)
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout while updating sensors")
            except Exception as e:
                _LOGGER.error(f"Error updating sensors: {e}")

        await refresh_state()
        async_track_time_interval(hass, refresh_state, SCAN_INTERVAL)

# =========================
# Power Sensor
# =========================
class BetterCozyLifePowerSensor(SensorEntity):
    """Representation of a BetterCozyLife Power Sensor."""

    _attr_has_entity_name = True

    def __init__(self, config, entry_id, device):
        """Initialize the power sensor."""
        self._device = device
        self._ip = config[CONF_IP_ADDRESS]
        self._entry_id = entry_id

        base_name = config.get(CONF_NAME, f"BetterCozyLife {self._ip}")
        clean_name = base_name.strip()
        slugified_name = re.sub(r"[^\w]+", "_", clean_name.lower()).strip("_")

        self._attr_name = "Power"
        self._attr_suggested_object_id = f"{slugified_name}_power"
        self._attr_unique_id = f"bettercozylife_power_{self._ip}"

        self._state = None
        self._available = True
        self._error_count = 0
        self._max_errors = 3
        self._last_valid_state = None

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ip)},
            name=base_name,
            manufacturer="CozyLife",
            model="Smart Switch",
            sw_version="1.0",
        )

        self._initialize_state()

    def _initialize_state(self):
        try:
            state = self._device.query_state()
            if state is not None:
                power = state.get('28', 0)
                self._state = float(power)
                self._last_valid_state = self._state
                self._available = True
                self._error_count = 0
                _LOGGER.info(f"Successfully initialized power sensor: {self._state}W")
            else:
                self._handle_error("Failed to initialize power sensor state")
        except Exception as e:
            self._handle_error(f"Error initializing power sensor state: {e}")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def native_value(self):
        return self._state

    def _handle_error(self, error_message):
        self._error_count += 1
        if self._error_count >= self._max_errors:
            self._available = False
            _LOGGER.error(f"{error_message} - Device marked as unavailable")
        else:
            _LOGGER.warning(f"{error_message} - Attempt {self._error_count} of {self._max_errors}")

    def update(self) -> None:
        try:
            state = self._device.query_state()
            if state is not None:
                power = state.get('28', 0)
                self._state = float(power)
                self._last_valid_state = self._state
                self._available = True
                self._error_count = 0
            else:
                self._handle_error("Failed to update power sensor state")
        except Exception as e:
            self._handle_error(f"Error updating power sensor state: {e}")

# =========================
# Current Sensor
# =========================
class BetterCozyLifeCurrentSensor(SensorEntity):
    """Representation of a BetterCozyLife Current Sensor."""

    _attr_has_entity_name = True

    def __init__(self, config, entry_id, device):
        self._device = device
        self._ip = config[CONF_IP_ADDRESS]
        self._entry_id = entry_id

        base_name = config.get(CONF_NAME, f"BetterCozyLife {self._ip}")
        clean_name = base_name.strip()
        slugified_name = re.sub(r"[^\w]+", "_", clean_name.lower()).strip("_")

        self._attr_name = "Current"
        self._attr_suggested_object_id = f"{slugified_name}_current"
        self._attr_unique_id = f"bettercozylife_current_{self._ip}"

        self._state = None
        self._available = True
        self._error_count = 0
        self._max_errors = 3
        self._last_valid_state = None

        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ip)},
            name=base_name,
            manufacturer="CozyLife",
            model="Smart Switch",
            sw_version="1.0",
        )

        self._initialize_state()

    def _initialize_state(self):
        try:
            state = self._device.query_state()
            if state is not None:
                current = state.get('27', 0)
                self._state = float(current) / 1000.0
                self._last_valid_state = self._state
                self._available = True
                self._error_count = 0
                _LOGGER.info(f"Successfully initialized current sensor: {self._state}A")
            else:
                self._handle_error("Failed to initialize current sensor state")
        except Exception as e:
            self._handle_error(f"Error initializing current sensor state: {e}")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def native_value(self):
        return self._state

    def _handle_error(self, error_message):
        self._error_count += 1
        if self._error_count >= self._max_errors:
            self._available = False
            _LOGGER.error(f"{error_message} - Device marked as unavailable")
        else:
            _LOGGER.warning(f"{error_message} - Attempt {self._error_count} of {self._max_errors}")

    def update(self) -> None:
        try:
            state = self._device.query_state()
            if state is not None:
                current = state.get('27', 0)
                self._state = float(current) / 1000.0
                self._last_valid_state = self._state
                self._available = True
                self._error_count = 0
            else:
                self._handle_error("Failed to update current sensor state")
        except Exception as e:
            self._handle_error(f"Error updating current sensor state: {e}")

# =========================
# Voltage Sensor
# =========================
class BetterCozyLifeVoltageSensor(SensorEntity):
    """Representation of a BetterCozyLife Voltage Sensor."""

    _attr_has_entity_name = True

    def __init__(self, config, entry_id, device):
        self._device = device
        self._ip = config[CONF_IP_ADDRESS]
        self._entry_id = entry_id

        base_name = config.get(CONF_NAME, f"BetterCozyLife {self._ip}")
        clean_name = base_name.strip()
        slugified_name = re.sub(r"[^\w]+", "_", clean_name.lower()).strip("_")

        self._attr_name = "Voltage"
        self._attr_suggested_object_id = f"{slugified_name}_voltage"
        self._attr_unique_id = f"bettercozylife_voltage_{self._ip}"

        self._state = None
        self._available = True
        self._error_count = 0
        self._max_errors = 3
        self._last_valid_state = None

        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ip)},
            name=base_name,
            manufacturer="CozyLife",
            model="Smart Switch",
            sw_version="1.0",
        )

        self._initialize_state()

    def _initialize_state(self):
        try:
            state = self._device.query_state()
            if state is not None:
                voltage = state.get('29', 0)
                self._state = float(voltage)
                self._last_valid_state = self._state
                self._available = True
                self._error_count = 0
                _LOGGER.info(f"Successfully initialized voltage sensor: {self._state}V")
            else:
                self._handle_error("Failed to initialize voltage sensor state")
        except Exception as e:
            self._handle_error(f"Error initializing voltage sensor state: {e}")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def native_value(self):
        return self._state

    def _handle_error(self, error_message):
        self._error_count += 1
        if self._error_count >= self._max_errors:
            self._available = False
            _LOGGER.error(f"{error_message} - Device marked as unavailable")
        else:
            _LOGGER.warning(f"{error_message} - Attempt {self._error_count} of {self._max_errors}")

    def update(self) -> None:
        try:
            state = self._device.query_state()
            if state is not None:
                voltage = state.get('29', 0)
                self._state = float(voltage)
                self._last_valid_state = self._state
                self._available = True
                self._error_count = 0
            else:
                self._handle_error("Failed to update voltage sensor state")
        except Exception as e:
            self._handle_error(f"Error updating voltage sensor state: {e}")