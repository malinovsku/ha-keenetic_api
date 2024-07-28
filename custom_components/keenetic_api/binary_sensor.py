"""The Keenetic API binary sensor entities."""

from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    COORD_FULL,
)
from .coordinator import KeeneticRouterCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class KeeneticBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Keenetic sensor entity."""
    value_fn: Callable[[KeeneticRouterCoordinator], bool]


BINARY_SENSOR_TYPES: dict[str, KeeneticBinarySensorEntityDescription] = {
    "connected_to_router": KeeneticBinarySensorEntityDescription(
        key="connected_to_router",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn= lambda coordinator: coordinator.last_update_success,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][COORD_FULL]
    entities: list[BinarySensorEntity] = []

    for key, description in BINARY_SENSOR_TYPES.items():
        entities.append(KeeneticBinarySensorEntity(coordinator, description))

    async_add_entities(entities, False)


class KeeneticBinarySensorEntity(CoordinatorEntity[KeeneticRouterCoordinator], BinarySensorEntity):

    _attr_has_entity_name = True
    entity_description: KeeneticRouterSensorEntityDescription

    def __init__(
        self,
        coordinator: KeeneticRouterCoordinator,
        description: KeeneticBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def available(self) -> bool:
        return True