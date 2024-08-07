"""The Keenetic API binary switch entities."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.typing import StateType

from .const import (
    DOMAIN,
    COORD_FULL,
    CONF_CREATE_PORT_FRW,
    COORD_RC_INTERFACE,
)
from .coordinator import (
    KeeneticRouterCoordinator,
)
from .keenetic import DataRcInterface

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class KeeneticSwitchEntityDescription(SwitchEntityDescription):

    is_on_func: Callable[[KeeneticRouterCoordinator], bool | None]
    on_func: Callable[[KeeneticRouterCoordinator], None]
    off_func: Callable[[KeeneticRouterCoordinator], None]
    placeholder: str | None = None

SWITCH_TYPES: tuple[KeeneticSwitchEntityDescription, ...] = (
    KeeneticSwitchEntityDescription(
        key="web_configurator_access",
        is_on_func=lambda coordinator, label_sw: coordinator.data.show_rc_ip_http['security-level'].get('public', False),
        on_func=lambda coordinator, label_sw: coordinator.router.turn_on_off_web_configurator_access(True),
        off_func=lambda coordinator, label_sw: coordinator.router.turn_on_off_web_configurator_access(False),
    ),
    KeeneticSwitchEntityDescription(
        key="power_usb",
        is_on_func=lambda coordinator, label_sw: coordinator.data.show_rc_system_usb[int(label_sw)-1].get('power', False) == False, # ЧЗХ
        on_func=lambda coordinator, label_sw: coordinator.router.turn_on_off_usb(True, label_sw),
        off_func=lambda coordinator, label_sw: coordinator.router.turn_on_off_usb(False, label_sw),
        placeholder="number",
    ),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,) -> None:

    coordinator: KeeneticRouterCoordinator = hass.data[DOMAIN][entry.entry_id][COORD_FULL]
    switchs: list[SwitchEntity] = []
    if coordinator.router.hw_type == "router":
        rc_interface: DataRcInterface = hass.data[DOMAIN][entry.entry_id][COORD_RC_INTERFACE].data

        interfaces = coordinator.data.show_interface
        for interface, data_interface in interfaces.items():
            if ((data_interface.get('usedby', False)
                and (interface.startswith('WifiMaster0') 
                    or interface.startswith('WifiMaster1')))):
                switchs.append(
                    KeeneticInterfaceSwitchEntity(
                        coordinator,
                        data_interface,
                        rc_interface[interface].name_interface,
                    )
                )
            elif interface in coordinator.data.priority_interface:
                new_name = f"{data_interface['type']} {data_interface.get('description', '')}"
                switchs.append(
                    KeeneticInterfaceSwitchEntity(
                        coordinator,
                        data_interface,
                        new_name,
                    )
                )

        if entry.options.get(CONF_CREATE_PORT_FRW, False):
            port_forwardings = coordinator.data.show_rc_ip_static
            for index, port_frw in port_forwardings.items():
                switchs.append(
                    KeeneticPortForwardingSwitchEntity(
                        coordinator,
                        port_frw,
                    )
                )

    for description in SWITCH_TYPES:
        if description.key == "power_usb":
            for row in coordinator.data.show_rc_system_usb:
                switchs.append(KeeneticSwitchEntity(coordinator, description, row['port']))
        else:
            switchs.append(KeeneticSwitchEntity(coordinator, description, description.key))

    async_add_entities(switchs)


class KeeneticSwitchEntity(CoordinatorEntity[KeeneticRouterCoordinator], SwitchEntity):

    entity_description: KeeneticSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KeeneticSwitchEntityDescription,
        entity_description: KeeneticSwitchEntityDescription,
        label_sw,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._label_sw = label_sw
        self._attr_translation_key = self.entity_description.key
        self._attr_unique_id = f"{coordinator.unique_id}_{self._attr_translation_key}_{self._label_sw}"
        self._attr_device_info = coordinator.device_info
        if self.entity_description.placeholder:
            self._attr_translation_placeholders = {
                self.entity_description.placeholder: label_sw
            }

    @property
    def is_on(self) -> bool:
        return bool(self.entity_description.is_on_func(self.coordinator, self._label_sw))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.on_func(self.coordinator, self._label_sw)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.off_func(self.coordinator, self._label_sw)
        await self.coordinator.async_request_refresh()


class KeeneticInterfaceSwitchEntity(CoordinatorEntity[KeeneticRouterCoordinator], SwitchEntity):

    _attr_translation_key="interface"
    _attr_has_entity_name = True

    _unrecorded_attributes = frozenset({
        "uptime"
    })

    def __init__(
        self,
        coordinator: KeeneticRouterCoordinator,
        data_interface,
        name_interface
    ) -> None:
        """Initialize the Keenetic Interface switch."""
        super().__init__(coordinator)
        self._id_interface = data_interface['id']
        self._name_interface = name_interface
        self._attr_unique_id = f"{coordinator.unique_id}_{self._attr_translation_key}_{self._id_interface}"
        self._attr_device_info = coordinator.device_info
        self._attr_translation_placeholders = {"name_interface": f"{self._name_interface}"}

    @property
    def is_on(self) -> bool:
        """Return state."""
        return self.coordinator.data.show_interface[self._id_interface]['state'] == "up"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.coordinator.router.turn_on_off_interface(self._id_interface, 'up'),
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.coordinator.router.turn_on_off_interface(self._id_interface, 'down'),
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return the state attributes."""
        return {
            "interface_type": self._id_interface,
            "uptime": self.coordinator.data.show_interface[self._id_interface].get('uptime'),
        }


class KeeneticPortForwardingSwitchEntity(CoordinatorEntity[KeeneticRouterCoordinator], SwitchEntity):

    _attr_translation_key="port_forwarding"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KeeneticRouterCoordinator,
        port_frw,
    ) -> None:
        """Initialize the Keenetic PortForwarding switch."""
        super().__init__(coordinator)
        self._pfrw = port_frw
        self._pfrw_index = port_frw.index
        self._pfrw_name = port_frw.name
        self._attr_unique_id = f"{coordinator.unique_id}_{self._attr_translation_key}_{self._pfrw_index}"
        self._attr_device_info = coordinator.device_info
        self._attr_translation_placeholders = {"pfrw_name": f"{self._pfrw_name}"}

    @property
    def is_on(self) -> bool:
        """Return state."""
        return self.coordinator.data.show_rc_ip_static[self._pfrw_index].disable == False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.coordinator.router.turn_on_off_port_forwarding(self._pfrw_index, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.coordinator.router.turn_on_off_port_forwarding(self._pfrw_index, False)
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return the state attributes."""
        return {
            "interface": self._pfrw.interface,
            "protocol": self._pfrw.protocol,
            "port": self._pfrw.port,
            "end_port": self._pfrw.end_port,
            "to_host": self._pfrw.to_host,
            "index": self._pfrw.index,
            "comment": self._pfrw.comment,
        }
