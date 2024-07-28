"""The Keenetic API integration."""

from __future__ import annotations
import logging
from aiohttp import CookieJar, ClientTimeout, ClientError
from typing import Any
from datetime import timedelta

from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_VERIFY_SSL,
    CONF_USERNAME,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ConfigEntryNotReady
from homeassistant.helpers.json import json_loads
from homeassistant.helpers import entity_registry

from .coordinator import (
    KeeneticRouterCoordinator, 
    KeeneticRouterFirmwareCoordinator, 
    KeeneticRouterRcInterfaceCoordinator
)
from .keenetic import Router
from .const import (
    DOMAIN, 
    DEFAULT_SCAN_INTERVAL, 
    MIN_SCAN_INTERVAL,
    COORD_FULL,
    COORD_FIREWARE,
    COORD_RC_INTERFACE,
    REQUEST_TIMEOUT,
    SCAN_INTERVAL_FIREWARE,
    FAST_SCAN_INTERVAL_FIREWARE,
)

PLATFORMS: list[Platform] = [
    Platform.UPDATE,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.DEVICE_TRACKER,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    try:
        client = await get_api(hass, entry.data)
    except Exception as ex:
        raise ConfigEntryNotReady from ex

    coordinator_full = KeeneticRouterCoordinator(hass, client, entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL), entry)
    await coordinator_full.async_config_entry_first_refresh()

    coordinator_firmware = KeeneticRouterFirmwareCoordinator(hass, client, FAST_SCAN_INTERVAL_FIREWARE, entry)
    try:
        await coordinator_firmware.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error(f'coordinator_firmware error - {err}')

    if client.hw_type == "router" and entry.options.get("create_image_qr", False):
        coordinator_rc_interface = KeeneticRouterRcInterfaceCoordinator(hass, client, SCAN_INTERVAL_FIREWARE, entry)
        await coordinator_rc_interface.async_config_entry_first_refresh()
    else:
        coordinator_rc_interface = None

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORD_FULL: coordinator_full,
        COORD_FIREWARE: coordinator_firmware,
        COORD_RC_INTERFACE: coordinator_rc_interface
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))


    async def request_api(service: ServiceCall):
        data_json = service.data.get("data_json", [])
        response = await hass.data[DOMAIN][service.data["entry_id"]][COORD_FULL].router.api(service.data["method"], service.data["endpoint"], data_json)
        _LOGGER.debug(f'Services request_api response - {response}')
        return {"response": response}
    hass.services.async_register(DOMAIN, "request_api", request_api, supports_response=SupportsResponse.OPTIONAL)

    async def backup_router(service: ServiceCall):
        response = await hass.data[DOMAIN][service.data["entry_id"]][COORD_FULL].router.async_backup(service.data["folder"], service.data["type"])
        return True
    hass.services.async_register(DOMAIN, "backup_router", backup_router)

    return True



async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator_full = hass.data[DOMAIN][entry.entry_id][COORD_FULL]
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    hass.services.async_remove(DOMAIN, "request_api")
    hass.services.async_remove(DOMAIN, "backup_router")
    return unload_ok



async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)



async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry) -> bool:
    return True



async def get_api(hass: HomeAssistant, data: dict[str, Any]) -> Router:
    kwargs: dict[str, Any] = {
            "timeout": ClientTimeout(total=REQUEST_TIMEOUT),
            "cookie_jar": CookieJar(unsafe=True),
        }
    session = aiohttp_client.async_create_clientsession(hass, data[CONF_SSL], **kwargs)
    client = Router(
        session = session,
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        host=data[CONF_HOST],
        port=data[CONF_PORT],
    )
    await client.async_setup_obj()
    return client
