"""Config flow for BetterCozyLife integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_IP_ADDRESS
import homeassistant.helpers.config_validation as cv
from typing import Any
import socket
import logging
from .const import DOMAIN, CONF_DEVICE_TYPE, DEVICE_TYPE_SWITCH
from .cozylife_device import CozyLifeDevice

_LOGGER = logging.getLogger(__name__)

class BetterCozyLifeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BetterCozyLife."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Test connection to device
                device = CozyLifeDevice(user_input[CONF_IP_ADDRESS])
                if await self.hass.async_add_executor_job(device.test_connection):
                    # Create unique ID from IP address
                    await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input
                    )
                else:
                    errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error(f"Error connecting to device: {e}")
                errors["base"] = "cannot_connect"

        # Show configuration form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_IP_ADDRESS): str,
                vol.Required(CONF_DEVICE_TYPE, default=DEVICE_TYPE_SWITCH): vol.In([
                    DEVICE_TYPE_SWITCH
                
                ]),
                vol.Optional(CONF_NAME): str,
            }),
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_config)
