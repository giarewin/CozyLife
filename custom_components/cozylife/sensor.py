"""Nền tảng tích hợp cảm biến."""

# ============================
# Các hằng số cấu hình
from datetime import timedelta

DEFAULT_TIMEOUT = 5  # giây
SCAN_INTERVAL = timedelta(seconds=5)

# Các cờ bật/tắt các loại cảm biến
ENABLE_SENSOR_POWER = True
ENABLE_SENSOR_VOLTAGE = False
ENABLE_SENSOR_CURRENT = False

# Cờ debug
ENABLE_LOGGING = False
# ============================

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
import asyncio
import async_timeout
from .const import DOMAIN, DEVICE_TYPE_SWITCH, CONF_DEVICE_TYPE
from .cozylife_device import CozyLifeDevice
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Thiết lập cảm biến Ổ Cắm Cozy Life."""
    config = config_entry.data

    if config[CONF_DEVICE_TYPE] == DEVICE_TYPE_SWITCH:
        device = CozyLifeDevice(config[CONF_IP_ADDRESS])
        sensors = []

        if ENABLE_SENSOR_CURRENT:
            sensors.append(CozyLifeCurrentSensor(config, config_entry.entry_id, device))
        if ENABLE_SENSOR_POWER:
            sensors.append(CozyLifePowerSensor(config, config_entry.entry_id, device))
        if ENABLE_SENSOR_VOLTAGE:
            sensors.append(CozyLifeVoltageSensor(config, config_entry.entry_id, device))

        async_add_entities(sensors)

        async def refresh_state(now=None):
            """Làm mới trạng thái cảm biến."""
            try:
                async with async_timeout.timeout(DEFAULT_TIMEOUT):
                    for sensor in sensors:
                        await hass.async_add_executor_job(sensor.update)
            except asyncio.TimeoutError:
                if ENABLE_LOGGING:
                    _LOGGER.warning("Timeout while updating sensors")
            except Exception as e:
                if ENABLE_LOGGING:
                    _LOGGER.error(f"Error updating sensors: {e}")

        await refresh_state()
        async_track_time_interval(hass, refresh_state, SCAN_INTERVAL)


# Base Sensor Class (common logic)
class CozyLifeBaseSensor(SensorEntity):
    def __init__(self, config, device, key, name_suffix, unit, device_class):
        self._device = device
        self._ip = config[CONF_IP_ADDRESS]
        self._entry_id = config.get("entry_id")
        base_name = config.get(CONF_NAME, f"cozylife_ {self._ip}")
        self._attr_name = f"{base_name} {name_suffix}"
        self._attr_unique_id = f"cozylife_{name_suffix.lower()}_{self._ip}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ip)},
            name=base_name,
            manufacturer="CozyLife",
            model="Smart Switch",
            sw_version="1.0",
        )
        self._attr_has_entity_name = True
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._key = key
        self._state = None
        self._available = True
        self._error_count = 0
        self._max_errors = 3
        self._last_valid_state = None

        self._initialize_state()

    def _initialize_state(self):
        try:
            state = self._device.query_state()
            if state is not None:
                raw = state.get(self._key, 0)
                self._state = self._convert(raw)
                self._last_valid_state = self._state
                self._available = True
                self._error_count = 0
                if ENABLE_LOGGING:
                    _LOGGER.info(f"Initialized sensor {self.name}: {self._state}")
            else:
                self._handle_error("Failed to initialize sensor state")
        except Exception as e:
            self._handle_error(f"Exception during initialization: {e}")

    def _handle_error(self, error_message):
        self._error_count += 1
        if self._error_count >= self._max_errors:
            self._available = False
            if ENABLE_LOGGING:
                _LOGGER.error(f"{error_message} - Marking sensor unavailable")
        else:
            if ENABLE_LOGGING:
                _LOGGER.warning(f"{error_message} - Attempt {self._error_count}/{self._max_errors}")

    @property
    def available(self):
        return self._available

    @property
    def native_value(self):
        return self._state

    def update(self):
        try:
            state = self._device.query_state()
            if state is not None:
                raw = state.get(self._key, 0)
                self._state = self._convert(raw)
                self._last_valid_state = self._state
                self._available = True
                self._error_count = 0
            else:
                self._handle_error("Failed to update sensor state")
        except Exception as e:
            self._handle_error(f"Exception during update: {e}")

    def _convert(self, raw):
        return raw  # Override in child class if needed


class CozyLifePowerSensor(CozyLifeBaseSensor):
    def __init__(self, config, entry_id, device):
        super().__init__(
            config=config,
            device=device,
            key='28',
            name_suffix="Power",
            unit=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
        )


class CozyLifeCurrentSensor(CozyLifeBaseSensor):
    def __init__(self, config, entry_id, device):
        super().__init__(
            config=config,
            device=device,
            key='27',
            name_suffix="Current",
            unit=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
        )

    def _convert(self, raw):
        return float(raw) / 1000.0


class CozyLifeVoltageSensor(CozyLifeBaseSensor):
    def __init__(self, config, entry_id, device):
        super().__init__(
            config=config,
            device=device,
            key='29',
            name_suffix="Voltage",
            unit=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
        )