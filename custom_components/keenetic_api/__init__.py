"""The Keenetic API integration."""

from __future__ import annotations
import logging
from aiohttp import CookieJar, ClientTimeout, ClientError
from typing import Any
from datetime import timedelta

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

from .services import async_setup_services, async_unload_services
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
    CROUTER,
    CONF_CREATE_DT,
    CONF_CREATE_ALL_CLIENTS_POLICY,
    CONF_CLIENTS_SELECT_POLICY,
    CONF_CREATE_PORT_FRW,
    CONF_CREATE_IMAGE_QR,
    CONF_SELECT_CREATE_DT,
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

    client = await get_api(hass, entry.data)

    coordinator_full = KeeneticRouterCoordinator(hass, client, entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL), entry)
    await coordinator_full.async_config_entry_first_refresh()

    coordinator_firmware = KeeneticRouterFirmwareCoordinator(hass, client, SCAN_INTERVAL_FIREWARE, entry)
    await coordinator_firmware.async_refresh()

    if client.hw_type == "router":
        coordinator_rc_interface = KeeneticRouterRcInterfaceCoordinator(hass, client, SCAN_INTERVAL_FIREWARE, entry)
        await coordinator_rc_interface.async_config_entry_first_refresh()
    else:
        coordinator_rc_interface = None

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        CROUTER: client,
        COORD_FULL: coordinator_full,
        COORD_FIREWARE: coordinator_firmware,
        COORD_RC_INTERFACE: coordinator_rc_interface
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await async_setup_services(hass)

    try:
        remove_entities_or_devices(hass, entry)
    except Exception as err:
        _LOGGER.error(f'remove_entities_or_devices - {err}')

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator_full = hass.data[DOMAIN][entry.entry_id][COORD_FULL]
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        async_unload_services(hass)
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


@callback
def remove_entities_or_devices(hass, entry) -> None:
    entity_registry = er.async_get(hass)
    entity_conf = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    for entity in entity_conf:
        delete_ent = False
        if (
            entity.domain == "device_tracker" 
            and not entry.options.get(CONF_CREATE_DT, False) 
            and hass.states.get(entity.entity_id).attributes.get("mac") not in entry.options.get(CONF_SELECT_CREATE_DT, []) 
        ):
            delete_ent = True
        elif (
            entity.domain == "switch" 
            and entity.translation_key == "port_forwarding"
            and not entry.options.get(CONF_CREATE_PORT_FRW, False) 
        ):
            delete_ent = True
        elif (
            entity.domain == "image" 
            and entity.translation_key == "qrwifi"
            and not entry.options.get(CONF_CREATE_IMAGE_QR, False) 
        ):
            delete_ent = True
        elif (
            entity.domain == "select" 
            and entity.translation_key == "client_policy"
            and not entry.options.get(CONF_CREATE_ALL_CLIENTS_POLICY, False) 
            and hass.states.get(entity.entity_id).attributes.get("mac") not in entry.options.get(CONF_CLIENTS_SELECT_POLICY, []) 
        ):
            delete_ent = True
        if delete_ent:
            _LOGGER.debug(f"Removing entity: {entity}")
            entity_registry.async_remove(entity.entity_id)

    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        entity_dev = er.async_entries_for_device(entity_registry, device_entry.id)

        if (len(entity_dev) == 0):
            _LOGGER.debug(f"Removing device: {device_entry}")
            device_registry.async_remove_device(device_entry.id)
        elif not any(x in {x.entity_id for x in entity_conf} for x in {x.entity_id for x in entity_dev}):
            _LOGGER.debug(f"Update device, remove_config_entry_id: {device_entry}")
            device_registry.async_update_device(device_entry.id, remove_config_entry_id=entry.entry_id)