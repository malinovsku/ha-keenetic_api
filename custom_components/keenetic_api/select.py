"""The Keenetic API selects entities."""

from __future__ import annotations
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.typing import StateType

from .const import (
    DOMAIN,
    COORD_FULL,
    COORD_RC_INTERFACE,
    CONF_CLIENTS_SELECT_POLICY,
    CONF_CREATE_ALL_CLIENTS_POLICY,
    POLICY_DEFAULT,
    POLICY_NOT_INTERNET,
)
from .coordinator import KeeneticRouterCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: KeeneticRouterCoordinator = hass.data[DOMAIN][entry.entry_id][COORD_FULL]
    conf_client_select = entry.options.get(CONF_CLIENTS_SELECT_POLICY, [])
    policy_list = await coordinator.router.ip_policy_list()
    select_options={}
    select_options[POLICY_DEFAULT] = POLICY_DEFAULT
    select_options[POLICY_NOT_INTERNET] = POLICY_NOT_INTERNET
    for policy in policy_list:
        select_options[policy] = policy_list[policy]["description"]

    selects: list[KeeneticPolicySelectEntity] = []
    for mac, client in coordinator.data.show_ip_hotspot.items():
        if mac in conf_client_select or entry.options.get(CONF_CREATE_ALL_CLIENTS_POLICY, False):
            selects.append(
                KeeneticPolicySelectEntity(
                    coordinator,
                    client,
                    select_options,
                )
            )
    async_add_entities(selects)


class KeeneticPolicySelectEntity(CoordinatorEntity[KeeneticRouterCoordinator], SelectEntity):

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_translation_key = "client_policy"

    def __init__(
        self,
        coordinator: KeeneticRouterCoordinator,
        client,
        select_options,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._mac = format_mac(client.mac)
        self._hostname = client.name or client.hostname
        self._attr_unique_id = f"{coordinator.unique_id}_select_client_policy_{self._mac}"
        self._select_options = select_options
        self._attr_options = list([select_options[policy] for policy in select_options])
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
            name=self._hostname,
            # via_device=(DOMAIN, format_mac(self.coordinator.router.mac)),
        )

    @property
    def current_option(self) -> str | None:
        if cln := self.coordinator.data.show_ip_hotspot_policy.get(self._mac, False):
            if cln.get("policy") == None:
                if cln.get("access") == "permit":
                    policy = POLICY_DEFAULT
                elif cln.get("access") == "deny":
                    policy = POLICY_NOT_INTERNET
            else:
                policy = cln["policy"]
            return self._select_options[policy]
        else:
            return None

    async def async_select_option(self, option: str) -> None:
        policy = {"no": True}
        if option == POLICY_NOT_INTERNET:
            new_option = "deny"
        elif option == POLICY_DEFAULT:
            new_option = "permit"
        else:
            new_option = "permit"
            policy = [row for row in self._select_options if self._select_options[row] == option][0]
        resp = await self.coordinator.router.ip_hotspot_host_policy(self._mac, new_option, policy)
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        return True if self.current_option != None else False

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return the state attributes."""
        return {
            "mac": self._mac,
        }