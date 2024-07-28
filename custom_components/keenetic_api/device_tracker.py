"""The Keenetic API device tracking entities."""

from __future__ import annotations
import logging

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KeeneticRouterCoordinator
from .const import (
    DOMAIN,
    COORD_FULL,
    CONF_CREATE_DT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: KeeneticRouterCoordinator = hass.data[DOMAIN][entry.entry_id][COORD_FULL]
    tracked: dict[str, KeeneticScannerEntity] = {}

    @callback
    def async_update_router() -> None:
        new_device: list[KeeneticScannerEntity] = []
        if entry.options.get(CONF_CREATE_DT):
            for mac, device in coordinator.data.show_ip_hotspot.items():
                if mac not in tracked:
                    tracked[mac] = KeeneticScannerEntity(coordinator, mac)
                    new_device.append(tracked[mac])
        async_add_entities(new_device)

    entry.async_on_unload(coordinator.async_add_listener(async_update_router))
    async_update_router()


class KeeneticScannerEntity(CoordinatorEntity[KeeneticRouterCoordinator], ScannerEntity, RestoreEntity):
    _unrecorded_attributes = frozenset({
        "uptime",
    })

    def __init__(self, coordinator: KeeneticRouterCoordinator, mac: str) -> None:
        """Initialize the device."""
        super().__init__(coordinator)
        self._mac = mac
        self._via_device_mac = coordinator.router.mac,
        self._attr_unique_id = f"{coordinator.unique_id}_dt_{self._mac}"

    @property
    def device(self) -> Device:
        """Return the device entity."""
        return self.coordinator.data.show_ip_hotspot[self._mac]

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return (
            self.device.name
            or self.device.hostname
            or self.device.mac
        )

    @property
    def source_type(self) -> str:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        """Get whether the entity is connected."""
        return self.device.active or False

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            name=self.name,
            # via_device=(DOMAIN, format_mac(self._via_device_mac))
        )

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return the state attributes of the device."""
        return {"interface_type": self.device.interface_id,
                "uptime": self.device.uptime}

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self.device.ip or None

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self.device.mac

    @property
    def hostname(self) -> str:
        """Return hostname of the device."""
        return self.device.hostname or self.device.name
