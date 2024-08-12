"""The Keenetic API button entities."""

from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
import logging

from homeassistant.const import EntityCategory
from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    COORD_FULL,
)
from .coordinator import KeeneticRouterCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class KeeneticButtonEntityDescription(ButtonEntityDescription):
    press_fn: Callable[[KeeneticRouterCoordinator], Any]


BUTTON_TYPES = (
    KeeneticButtonEntityDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.router.async_reboot(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][COORD_FULL]
    buttons: list[KeeneticButtonEntity] = []

    for description in BUTTON_TYPES:
        buttons.append(KeeneticButtonEntity(coordinator, description))

    async_add_entities(buttons, False)


class KeeneticButtonEntity(CoordinatorEntity[KeeneticRouterCoordinator], ButtonEntity, RestoreEntity):

    _attr_has_entity_name = True
    entity_description: KeeneticButtonEntityDescription

    def __init__(
            self,
            coordinator: KeeneticRouterCoordinator,
            description: KeeneticButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}_{description.key}"
        self._attr_translation_key = description.key
        self.entity_description = description

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator)
