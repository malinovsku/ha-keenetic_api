"""The Keenetic API update entities."""

from __future__ import annotations
import logging
from typing import Any
import os
from datetime import timedelta

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN, 
    COORD_FIREWARE, 
    SCAN_INTERVAL_FIREWARE,
    DEFAULT_BACKUP_TYPE_FILE,
    CONF_BACKUP_TYPE_FILE,
)
from .coordinator import KeeneticRouterFirmwareCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][COORD_FIREWARE]
    entities = [KeeneticUpdateEntity(coordinator, entry.options.get(CONF_BACKUP_TYPE_FILE, DEFAULT_BACKUP_TYPE_FILE))]
    async_add_entities(entities)


class KeeneticUpdateEntity(CoordinatorEntity[KeeneticRouterFirmwareCoordinator], UpdateEntity):

    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category=EntityCategory.CONFIG
    # _attr_available=False

    def __init__(
        self,
        coordinator: KeeneticRouterFirmwareCoordinator,
        backup_type_file,
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}_main_update"
        self._in_progress_old_version: str | None = None
        self._backup_type_file = backup_type_file
        self._attr_supported_features = (
            UpdateEntityFeature.INSTALL | 
            UpdateEntityFeature.PROGRESS 
        )
        if len(self._backup_type_file) > 0:
            self._attr_supported_features |= UpdateEntityFeature.BACKUP

    @property
    def title(self) -> str | None:
        """Title channel."""
        return self.coordinator.data.get('channel')

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self.coordinator.data.get("current").get("title")

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.coordinator.data.get("new").get("title")

    @property
    def in_progress(self) -> bool:
        """Update installation in progress."""
        return self._in_progress_old_version == self.installed_version

    @property
    def release_url(self) -> str | None:
        """Release summary."""
        return self.coordinator.data.get("release_notes")

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install the latest firmware version."""
        self._in_progress_old_version = self.installed_version
        self.async_write_ha_state()
        try:
            if backup:
                download_path = "keenetic_backup"
                if not await self.hass.async_add_executor_job(os.path.isabs, download_path):
                    download_path = self.hass.config.path(download_path)
                await self.coordinator.router.async_backup(download_path, self._backup_type_file)
            await self.coordinator.router.async_update()
        except Exception as err:
            self._in_progress_old_version = None
            raise HomeAssistantError(err)
