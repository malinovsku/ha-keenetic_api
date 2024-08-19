import logging

from homeassistant.helpers import device_registry as dr
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)

from .const import (
    DOMAIN,
    CROUTER,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_services(hass: HomeAssistant) -> None:

    @callback
    def async_get_entry_id_for_service_call(call: ServiceCall) -> str:
        """Получите идентификатор записи, связанный с вызовом службы (by device ID)."""
        if entry_id := call.data.get('entry_id', False):
            return entry_id
        device_id = call.data['device_id']
        device_registry = dr.async_get(hass)
        if (device_entry := device_registry.async_get(device_id)) is None:
            raise ValueError(f"Некорректный device ID: {device_id}")
        for entry_id in device_entry.config_entries:
            if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
                continue
            if entry.domain == DOMAIN:
                return entry_id
        raise ValueError(f"Нет записи в конфигурации для device ID: {device_id}")


    async def request_api(service: ServiceCall):
        entry_id = async_get_entry_id_for_service_call(service)
        data_json = service.data.get("data_json", [])
        response = await hass.data[DOMAIN][entry_id][CROUTER].api(service.data["method"], service.data["endpoint"], data_json)
        _LOGGER.debug(f'Services request_api response - {response}')
        return {"response": response}


    async def backup_router(service: ServiceCall):
        entry_id = async_get_entry_id_for_service_call(service)
        response = await hass.data[DOMAIN][entry_id][CROUTER].async_backup(service.data["folder"], service.data["type"])
        return True



    hass.services.async_register(DOMAIN, "request_api", request_api, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "backup_router", backup_router)



@callback
def async_unload_services(hass: HomeAssistant) -> None:
    hass.services.async_remove(DOMAIN, "request_api")
    hass.services.async_remove(DOMAIN, "backup_router")
