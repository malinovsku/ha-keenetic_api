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
        value_fn= lambda coordinator, obj_id: coordinator.last_update_success,
    ),
    "connected_to_interface": KeeneticBinarySensorEntityDescription(
        key="connected_to_interface",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn= lambda coordinator, obj_id: coordinator.data.show_interface[obj_id].get('connected', "no") == "yes",
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
            new_name = f"{data_interface['type']} {data_interface.get('description', '')}"
            binary_sensors.append(
                KeeneticBinarySensorEntity(
                    coordinator,
                    BINARY_SENSOR_TYPES["connected_to_interface"],
                    interface,
                    new_name,
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
        obj_id: str,
        obj_name: str = "",
    ) -> None:
        super().__init__(coordinator)
        self._obj_id = obj_id
        self._attr_key = description.key
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}_{self._attr_key}_{self._obj_id}"
        self._attr_translation_key = self._attr_key
        self._attr_translation_placeholders = {"name": f"{obj_name}"}

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator, self._obj_id)

    @property
    def available(self) -> bool:
        if self.entity_description.key == "connected_to_router":
            return True
        else:
            return self.coordinator.last_update_success
