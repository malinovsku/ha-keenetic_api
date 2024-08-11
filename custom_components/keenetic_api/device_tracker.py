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
    CONF_SELECT_CREATE_DT,
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
        device_trackers: list[KeeneticScannerEntity] = []
        for mac, device in coordinator.data.show_ip_hotspot.items():
            if mac in entry.options.get(CONF_SELECT_CREATE_DT, []) or entry.options.get(CONF_CREATE_DT, False):
                if mac not in tracked:
                    tracked[mac] = KeeneticScannerEntity(
                        coordinator, 
                        mac, 
                        device.name or device.hostname or device.mac,
                    )
                    device_trackers.append(tracked[mac])
        async_add_entities(device_trackers)

    entry.async_on_unload(coordinator.async_add_listener(async_update_router))
    async_update_router()


class KeeneticScannerEntity(CoordinatorEntity[KeeneticRouterCoordinator], ScannerEntity, RestoreEntity):
    _unrecorded_attributes = frozenset({
        "uptime",
        "rssi",
        "rxbytes",
        "txbytes",
    })

    def __init__(
        self, 
        coordinator: KeeneticRouterCoordinator, 
        mac: str,
        hostname: str,
    ) -> None:
        """Initialize the device."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_name = hostname
        self._attr_hostname = hostname
        self._via_device_mac = coordinator.router.mac
        self._attr_unique_id = f"{coordinator.unique_id}_dt_{self._mac}"
        self._ip_address = None

    @property
    def source_type(self) -> str:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        return any(
            devs.active
            for mac, devs in self.coordinator.data.show_ip_hotspot.items()
            if mac == self._mac and devs.active
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
            name=self._attr_name,
            # via_device=(DOMAIN, format_mac(self._via_device_mac))
        )

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return the state attributes of the device."""
        if self._mac in self.coordinator.data.show_ip_hotspot:
            dt_hotspot = self.coordinator.data.show_ip_hotspot[self._mac]
            self._ip_address = dt_hotspot.ip
            return {"interface_type": dt_hotspot.interface_id,
                    "uptime": dt_hotspot.uptime,
                    "rssi": dt_hotspot.rssi,
                    "rxbytes": dt_hotspot.rxbytes,
                    "txbytes": dt_hotspot.txbytes,
                    }
        else:
            return None

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac

    @property
    def ip_address(self) -> str:
        """Return the IP address."""
        return self._ip_address
