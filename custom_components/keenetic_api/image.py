"""The Keenetic API image entities."""

from __future__ import annotations
from typing import Any
import logging
import io
import pyqrcode

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    COORD_RC_INTERFACE,
)
from .coordinator import KeeneticRouterRcInterfaceCoordinator
from .keenetic import INTERFACES_NAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][COORD_RC_INTERFACE]
    images: list[ImageEntity] = []

    if coordinator != None:
        interfaces = coordinator.data
        for interface in interfaces:
            interface_wifi = interfaces[interface]
            interface_wifi['id'] = interface
            interface_wifi['name_interface'] = INTERFACES_NAME.get(interface.split('/')[0], interface)
            if (interface_wifi.get('ssid', False) and(
                interface.startswith('WifiMaster0') 
                or interface.startswith('WifiMaster1'))):
                    images.append(
                        KeeneticQrWiFiImageEntity(
                            coordinator,
                            interface_wifi,
                        )
                    )

    async_add_entities(images)


class KeeneticQrWiFiImageEntity(CoordinatorEntity[KeeneticRouterRcInterfaceCoordinator], ImageEntity):

    _attr_has_entity_name = True
    _attr_content_type = "image/png"
    _attr_translation_key = "qrwifi"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    # entity_registry_enabled_default = False
    _unrecorded_attributes = frozenset({
        "active", 
        "rename", 
        "description", 
        "ssid", 
        "password"
    })

    def __init__(
            self,
            coordinator: KeeneticRouterRcInterfaceCoordinator,
            interface_wifi,
    ) -> None:
        super().__init__(coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._draft_name = f"{interface_wifi['name_interface']} {interface_wifi['ssid']}"
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}_{self._attr_translation_key}_{self._draft_name}"
        self._attr_translation_placeholders = {"name": self._draft_name}
        self._attr_image_last_updated = dt_util.utcnow()
        self._interface_wifi = interface_wifi
        self.image: io.BytesIO = io.BytesIO()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        wifi_ssid = self._interface_wifi["ssid"]
        wifi_pass = self._interface_wifi["authentication"]["wpa-psk"]["psk"]
        code = pyqrcode.create(f'WIFI:S:{wifi_ssid};T:WPA;P:{wifi_pass};;')
        code.png(self.image,scale=10)
        return self.image.getvalue()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self._interface_wifi["ssid"] != self.coordinator.data[self._interface_wifi["id"]]["ssid"]
            or self._interface_wifi["authentication"]["wpa-psk"]["psk"] != self.coordinator.data[self._interface_wifi["id"]]["authentication"]["wpa-psk"]["psk"]
        ):
            self._interface_wifi = self.coordinator.data[self._interface_wifi['id']]
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes of the image."""
        return {
            "interface": self._interface_wifi["id"],
            "ssid": self._interface_wifi["ssid"],
            "password": self._interface_wifi["authentication"]["wpa-psk"]["psk"],
            "active": self._interface_wifi.get("up", False),
            "rename": self._interface_wifi.get("rename", None),
            "description": self._interface_wifi.get("description", None),
        }
