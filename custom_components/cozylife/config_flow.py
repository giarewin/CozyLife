"""Cấu hình cho ổ cắm Cozy Life.
THAY THẾ FILE config_flow.py GỐC BẰNG FILE NÀY
File config_flow.py này định nghĩa quá trình cấu hình (config flow) cho integration trong Home Assistant.

Chức năng chính:
- Cho phép người dùng thêm thiết bị thủ công (nhập IP), từ file JSON hoặc từ liên kết JSON online.
- Kiểm tra kết nối trước khi thêm thiết bị.
- Đảm bảo mỗi IP chỉ thêm một lần (unique_id).
"""

from __future__ import annotations

# Nhập các thư viện cần thiết
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_IP_ADDRESS
import homeassistant.helpers.config_validation as cv
from typing import Any
import os
import json
import logging
import aiohttp

# Nhập các hằng số và lớp điều khiển thiết bị CozyLife
from .const import DOMAIN, CONF_DEVICE_TYPE, DEVICE_TYPE_SWITCH
from .cozylife_device import CozyLifeDevice

# Khởi tạo logger
_LOGGER = logging.getLogger(__name__)

# Các lựa chọn cấu hình ban đầu
CHOICE_MANUAL = "manual"
CHOICE_FROM_FILE = "from_file"
CHOICE_FROM_LINK = "from_link"

class CozyLifeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Xử lý quy trình cấu hình cho ổ cắm Cozy Life."""

    VERSION = 1  # Phiên bản schema config flow

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Bắt đầu flow: chuyển tới bước lựa chọn cấu hình."""
        return await self.async_step_start(user_input)

    async def async_step_start(self, user_input: dict[str, Any] | None = None):
        """Bước chọn cách thêm thiết bị: thủ công, từ file hoặc từ link."""
        if user_input is not None:
            if user_input["mode"] == CHOICE_MANUAL:
                return await self.async_step_manual()
            elif user_input["mode"] == CHOICE_FROM_FILE:
                return await self.async_step_import_file()
            elif user_input["mode"] == CHOICE_FROM_LINK:
                return await self.async_step_import_link()

        # Hiển thị form lựa chọn cách thêm thiết bị
        return self.async_show_form(
            step_id="start",
            data_schema=vol.Schema({
                vol.Required("mode", default=CHOICE_MANUAL): vol.In({
                    CHOICE_MANUAL: "Nhập thủ công",
                    CHOICE_FROM_FILE: "Tải từ file JSON",
                    CHOICE_FROM_LINK: "Tải từ đường link"
                })
            }),
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None):
        """Bước cấu hình thủ công: nhập IP, loại thiết bị và tên."""
        errors = {}

        if user_input is not None:
            try:
                # Tạo kết nối kiểm tra thiết bị
                device = CozyLifeDevice(user_input[CONF_IP_ADDRESS])
                if await self.hass.async_add_executor_job(device.test_connection):
                    # Đặt unique ID theo IP và kiểm tra trùng
                    await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
                    self._abort_if_unique_id_configured()

                    # Tạo entry sau khi xác minh thành công
                    return self.async_create_entry(
                        title=user_input.get(CONF_NAME) or user_input[CONF_IP_ADDRESS],
                        data=user_input
                    )
                else:
                    errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error(f"Error connecting to device: {e}")
                errors["base"] = "cannot_connect"

        # Hiển thị form nhập IP
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_IP_ADDRESS): str,
                vol.Required(CONF_DEVICE_TYPE, default=DEVICE_TYPE_SWITCH): vol.In([
                    DEVICE_TYPE_SWITCH
                ]),
                vol.Optional(CONF_NAME): str,
            }),
            errors=errors,
        )

    async def async_step_import_file(self):
        """Bước nhập thiết bị từ file JSON nội bộ (devices.json)."""
        try:
            # Xác định đường dẫn tới file devices.json trong thư mục component
            json_path = os.path.join(os.path.dirname(__file__), "devices.json")
            with open(json_path, "r", encoding="utf-8") as f:
                devices = json.load(f)

            # Gửi danh sách thiết bị sang hàm xử lý chung
            return await self._import_devices_list(devices)

        except FileNotFoundError:
            _LOGGER.error("file devices.json không có trong thư mục cài đặt")
            return self.async_abort(reason="file_not_found")
        except Exception as e:
            _LOGGER.error(f"Failed to load devices from file: {e}")
            return self.async_abort(reason="file_import_failed")

    async def async_step_import_link(self, user_input: dict[str, Any] | None = None):
        """Bước nhập thiết bị từ đường dẫn chứa JSON."""
        errors = {}

        if user_input is not None:
            url = user_input.get("link")
            try:
                # Tạo session và tải JSON từ link
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status != 200:
                            raise Exception(f"HTTP {resp.status}")
                        data = await resp.json()

                return await self._import_devices_list(data)

            except Exception as e:
                _LOGGER.error(f"Failed to import devices from link: {e}")
                errors["base"] = "link_error"

        # Hiển thị form nhập link
        return self.async_show_form(
            step_id="import_link",
            data_schema=vol.Schema({
                vol.Required("link", default="http://giare.win/cozy.json"): str
            }),
            errors=errors,
        )

    async def _import_devices_list(self, devices: list[dict[str, Any]]):
        """Hàm xử lý chung để import danh sách thiết bị (từ file hoặc link)."""
        if not isinstance(devices, list) or len(devices) == 0:
            _LOGGER.warning("Device list is empty or malformed")
            return self.async_abort(reason="empty_or_invalid_file")

        count = 0
        for device in devices:
            ip = device.get(CONF_IP_ADDRESS)
            if not ip:
                continue

            name = device.get(CONF_NAME, ip)
            dev_type = device.get(CONF_DEVICE_TYPE, DEVICE_TYPE_SWITCH)

            try:
                # Đảm bảo mỗi IP chỉ thêm 1 lần
                await self.async_set_unique_id(ip)
                self._abort_if_unique_id_configured()
            except Exception:
                continue  # thiết bị đã tồn tại, bỏ qua

            # Khởi tạo flow thêm thiết bị ngầm (background)
            self.hass.async_create_task(self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data={
                    CONF_IP_ADDRESS: ip,
                    CONF_NAME: name,
                    CONF_DEVICE_TYPE: dev_type
                }
            ))
            count += 1

        if count == 0:
            return self.async_abort(reason="no_new_devices")

        return self.async_abort(reason="import_success")

    async def async_step_import(self, import_config):
        """Xử lý khi import từ configuration.yaml (nếu có hỗ trợ YAML)."""
        return await self.async_step_manual(import_config)