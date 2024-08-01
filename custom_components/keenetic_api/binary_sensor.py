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
        value_fn= lambda coordinator, enti: coordinator.last_update_success,
    ),
    "connected_to_interface": KeeneticBinarySensorEntityDescription(
        key="connected_to_interface",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn= lambda coordinator, enti: coordinator.data.show_interface[enti].get('connected', "no") == "yes",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:

    coordinator = hass.data[DOMAIN][entry.entry_id][COORD_FULL]
    binary_sensors: list[BinarySensorEntity] = []

    binary_sensors.append(KeeneticBinarySensorEntity(coordinator, BINARY_SENSOR_TYPES["connected_to_router"], "status_router"))

    for interface, data_interface in coordinator.data.show_interface.items():
        if interface in coordinator.data.priority_interface:
            binary_sensors.append(
                KeeneticBinarySensorEntity(
                    coordinator,
                    BINARY_SENSOR_TYPES["connected_to_interface"],
                    interface,
                )
            )

    async_add_entities(binary_sensors, False)


class KeeneticBinarySensorEntity(CoordinatorEntity[KeeneticRouterCoordinator], BinarySensorEntity):

    _attr_has_entity_name = True
    entity_description: KeeneticRouterSensorEntityDescription

    def __init__(
        self,
        coordinator: KeeneticRouterCoordinator,
        description: KeeneticBinarySensorEntityDescription,
        enti = ""
    ) -> None:
        super().__init__(coordinator)
        self._enti = enti
        self._attr_key = description.key
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}_{self._attr_key}_{self._enti}"
        self._attr_translation_key = self._attr_key
        self._attr_translation_placeholders = {"name": f"{self._enti}"}

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator, self._enti)

    @property
    def available(self) -> bool:
        if self.entity_description.key == "connected_to_router":
            return True
        else:
            return self.coordinator.last_update_success
