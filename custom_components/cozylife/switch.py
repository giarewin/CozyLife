"""Platform for switch integration."""
import asyncio
import async_timeout
import logging
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, DEVICE_TYPE_SWITCH, CONF_DEVICE_TYPE
from .cozylife_device import CozyLifeDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)
TIMEOUT = 5
MAX_ERRORS = 3
ENABLE_LOGGING = False  # Có thể bật/tắt log toàn cục tại đây


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CozyLife Switch."""
    config = config_entry.data

    if config.get(CONF_DEVICE_TYPE) != DEVICE_TYPE_SWITCH:
        return

    switch_entity = CozyLifeSwitch(config, config_entry.entry_id)
    async_add_entities([switch_entity])

    async def refresh_state(now=None):
        """Refresh device state periodically."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                await hass.async_add_executor_job(switch_entity.update)
        except asyncio.TimeoutError:
            if ENABLE_LOGGING:
                _LOGGER.warning("Timeout while refreshing CozyLife switch state")
        except Exception as e:
            if ENABLE_LOGGING:
                _LOGGER.error(f"Exception during switch refresh: {e}")

    await refresh_state()
    async_track_time_interval(hass, refresh_state, SCAN_INTERVAL)


class CozyLifeSwitch(SwitchEntity):
    """Representation of a CozyLife Switch."""

    def __init__(self, config, entry_id):
        """Initialize the switch."""
        self._device = CozyLifeDevice(config[CONF_IP_ADDRESS])
        self._ip = config[CONF_IP_ADDRESS]
        self._name = config.get(CONF_NAME, f"CozyLife Switch {self._ip}")
        self._entry_id = entry_id
        self._is_on = False
        self._available = True
        self._error_count = 0

        self._attr_has_entity_name = True
        self._attr_name = self._name
        self._attr_unique_id = f"cozylife_switch_{self._ip}"

        self._initialize_state()

    def _initialize_state(self):
        """Initial read from the device."""
        try:
            state = self._device.query_state()
            if state is not None:
                self._is_on = state.get('1', 0) > 0
                self._available = True
                self._error_count = 0
                if ENABLE_LOGGING:
                    _LOGGER.debug(f"[{self._name}] Initial state: {self._is_on}")
            else:
                self._available = False
                if ENABLE_LOGGING:
                    _LOGGER.warning(f"[{self._name}] No response during initialization")
        except Exception as e:
            self._available = False
            if ENABLE_LOGGING:
                _LOGGER.error(f"[{self._name}] Error during initialization: {e}")

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._attr_unique_id

    @property
    def is_on(self):
        """Return True if the switch is on."""
        return self._is_on

    @property
    def available(self):
        """Return True if the entity is available."""
        return self._available

    @property
    def device_info(self):
        """Return device info for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._ip)},
            name=self._name,
            manufacturer="CozyLife",
            model="Smart Switch",
            sw_version="1.0",
        )

    def turn_on(self, **kwargs):
        """Turn on the switch."""
        try:
            if self._device.send_command(True):
                self._is_on = True
                self._error_count = 0
                if ENABLE_LOGGING:
                    _LOGGER.debug(f"[{self._name}] Turned ON")
            else:
                self._handle_error("Failed to turn on")
        except Exception as e:
            self._handle_error(f"Exception on turn on: {e}")

    def turn_off(self, **kwargs):
        """Turn off the switch."""
        try:
            if self._device.send_command(False):
                self._is_on = False
                self._error_count = 0
                if ENABLE_LOGGING:
                    _LOGGER.debug(f"[{self._name}] Turned OFF")
            else:
                self._handle_error("Failed to turn off")
        except Exception as e:
            self._handle_error(f"Exception on turn off: {e}")

    def update(self):
        """Fetch new state from the device."""
        try:
            state = self._device.query_state()
            if state is not None:
                self._is_on = state.get('1', 0) > 0
                self._available = True
                self._error_count = 0
                if ENABLE_LOGGING:
                    _LOGGER.debug(f"[{self._name}] Updated state: {self._is_on}")
            else:
                self._handle_error("No response on update")
        except Exception as e:
            self._handle_error(f"Exception on update: {e}")

    def _handle_error(self, message):
        """Handle error state."""
        self._error_count += 1
        if self._error_count >= MAX_ERRORS:
            self._available = False
            if ENABLE_LOGGING:
                _LOGGER.error(f"[{self._name}] {message} (Unavailable)")
        else:
            if ENABLE_LOGGING:
                _LOGGER.warning(f"[{self._name}] {message} (Retry {self._error_count}/{MAX_ERRORS})")