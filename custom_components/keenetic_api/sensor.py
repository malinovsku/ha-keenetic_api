"""The Keenetic API sensor entities."""

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any
from datetime import UTC, datetime, timedelta
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    PERCENTAGE, 
    UnitOfInformation, 
    EntityCategory, 
    UnitOfDataRate,
    UnitOfTemperature,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KeeneticRouterCoordinator
from .keenetic import KeeneticFullData
from .const import (
    DOMAIN,
    COORD_FULL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class KeeneticRouterSensorEntityDescription(SensorEntityDescription):
    """A class that describes sensor entities."""
    value: Callable[[KeeneticFullData, Any], Any] = (
        lambda coordinator, key: coordinator.data.show_system[key] if coordinator.data.show_system[key] is not None else None
    )
    attributes_fn: Callable[[KeeneticFullData], dict[str, Any]] | None = None


def convert_uptime(update_success_time: str, uptime: str) -> datetime:
    """Convert uptime."""
    time_start = update_success_time.replace(microsecond=0) - timedelta(seconds=int(uptime))
    _LOGGER.debug(f"Convert uptime: {update_success_time} / {uptime} / {time_start}")
    return time_start


def ind_wan_ip_adress(fdata: KeeneticFullData):
    """Определение внешнего IP адреса."""
    try:
        data_p_i = fdata.priority_interface
        show_interface = fdata.show_interface
        priority_interface = sorted(data_p_i, key=lambda x: data_p_i[x]['order'])
        for row in priority_interface:
            if show_interface[row]["connected"] == "yes":
                if row.startswith('Wireguard'):
                    return show_interface[row]["wireguard"]["peer"][0]["remote"]
                else:
                    return show_interface[row]["address"]
    except Exception as ex:
        _LOGGER.debug(f'Not ind_wan_ip_adress - {ex}')
        return None


SENSOR_TYPES: tuple[KeeneticRouterSensorEntityDescription, ...] = (
    KeeneticRouterSensorEntityDescription(
        key="cpuload",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    KeeneticRouterSensorEntityDescription(
        key="memory",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda coordinator, key: int(float(coordinator.data.show_system[key].split('/')[0])/float(coordinator.data.show_system[key].split('/')[1])*100),
    ),
    KeeneticRouterSensorEntityDescription(
        key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda coordinator, key: convert_uptime(coordinator.last_update_success_time, coordinator.data.show_system[key]),
    ),
    KeeneticRouterSensorEntityDescription(
        key="wan_ip_adress",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda coordinator, key: ind_wan_ip_adress(coordinator.data),
    ),
    KeeneticRouterSensorEntityDescription(
        key="temperature_2_4g",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda coordinator, key: coordinator.data.show_interface['WifiMaster0']['temperature'],
    ),
    KeeneticRouterSensorEntityDescription(
        key="temperature_5g",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda coordinator, key: coordinator.data.show_interface['WifiMaster1']['temperature'],
    ),
    KeeneticRouterSensorEntityDescription(
        key="clients_wifi",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda coordinator, key: len(coordinator.data.show_associations.get("station", [])),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][COORD_FULL]
    sensors = []
    for description in SENSOR_TYPES:
        if description.value(coordinator, description.key) is not None:
            sensors.append(KeeneticRouterSensor(coordinator, description))
    async_add_entities(sensors, False)


class KeeneticRouterSensor(CoordinatorEntity[KeeneticRouterCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: KeeneticRouterSensorEntityDescription

    def __init__(
            self,
            coordinator: KeeneticRouterCoordinator,
            description: KeeneticRouterSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def native_value(self) -> StateType:
        """Sensor value."""
        return self.entity_description.value(self.coordinator, self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes of the sensor."""
        if self.entity_description.attributes_fn is not None:
            return self.entity_description.attributes_fn(self.coordinator.data)
        else:
            return None