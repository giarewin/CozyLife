"""Platform for switch integration."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_NAME, CONF_IP_ADDRESS
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
SCAN_INTERVAL = timedelta(seconds=10)
TIMEOUT = 5

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BetterCozyLife Switch."""
    config = config_entry.data
    
    if config[CONF_DEVICE_TYPE] == DEVICE_TYPE_SWITCH:
        switch = BetterCozyLifeSwitch(config, config_entry.entry_id)
        async_add_entities([switch])
        
        # Set up regular state refresh
        async def refresh_state(now=None):
            """Refresh device state."""
            try:
                async with async_timeout.timeout(TIMEOUT):
                    await hass.async_add_executor_job(switch.update)
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout while updating device state")
            except Exception as e:
                _LOGGER.error(f"Error updating device state: {e}")

        # Initial state refresh
        await refresh_state()
        
        # Schedule regular updates
        async_track_time_interval(hass, refresh_state, SCAN_INTERVAL)

class BetterCozyLifeSwitch(SwitchEntity):
    """Representation of a BetterCozyLife Switch."""

    _attr_has_entity_name = True

    def __init__(self, config, entry_id):
        """Initialize the switch."""
        self._device = CozyLifeDevice(config[CONF_IP_ADDRESS])
        self._ip = config[CONF_IP_ADDRESS]
        self._entry_id = entry_id

        base_name = config.get(CONF_NAME, f"BetterCozyLife Switch {self._ip}")
        clean_name = base_name.strip()
        slugified_name = re.sub(r"[^\w]+", "_", clean_name.lower()).strip("_")

        self._attr_name = "Switch"
        self._attr_suggested_object_id = f"{slugified_name}_switch"
        self._attr_unique_id = f"bettercozylife_switch_{self._ip}"

        self._is_on = False
        self._available = True
        self._last_update = 0
        self._error_count = 0
        self._max_errors = 3

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ip)},
            name=base_name,
            manufacturer="CozyLife",
            model="Smart Switch",
            sw_version="1.0",
        )

        # Initialize state
        self._initialize_state()

    def _initialize_state(self):
        """Initialize the switch state."""
        try:
            state = self._device.query_state()
            if state is not None:
                self._is_on = state.get('1', 0) > 0
                self._available = True
                self._error_count = 0
                _LOGGER.info(f"Successfully initialized switch state: {self._is_on}")
            else:
                self._available = False
                _LOGGER.warning("Failed to initialize switch state")
        except Exception as e:
            self._available = False
            _LOGGER.error(f"Error initializing switch state: {e}")

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._attr_unique_id

    @property
    def device_info(self):
        """Return device information about this switch."""
        return self._attr_device_info

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._attr_name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        try:
            if self._device.send_command(True):
                self._is_on = True
                self._error_count = 0
                _LOGGER.info(f"Successfully turned on switch: {self._attr_name}")
            else:
                self._handle_error("Failed to turn on switch")
        except Exception as e:
            self._handle_error(f"Error turning on switch: {e}")

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            if self._device.send_command(False):
                self._is_on = False
                self._error_count = 0
                _LOGGER.info(f"Successfully turned off switch: {self._attr_name}")
            else:
                self._handle_error("Failed to turn off switch")
        except Exception as e:
            self._handle_error(f"Error turning off switch: {e}")

    def _handle_error(self, error_message):
        """Handle errors and update availability."""
        self._error_count += 1
        if self._error_count >= self._max_errors:
            self._available = False
            _LOGGER.error(f"{error_message} - Device marked as unavailable")
        else:
            _LOGGER.warning(f"{error_message} - Attempt {self._error_count} of {self._max_errors}")

    def update(self):
        """Fetch new state data for this switch."""
        try:
            state = self._device.query_state()
            if state is not None:
                self._is_on = state.get('1', 0) > 0
                self._available = True
                self._error_count = 0
            else:
                self._handle_error("Failed to update switch state")
        except Exception as e:
            self._handle_error(f"Error updating switch state: {e}")