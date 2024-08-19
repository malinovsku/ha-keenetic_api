import logging

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

    async def request_api(service: ServiceCall):
        data_json = service.data.get("data_json", [])
        response = await hass.data[DOMAIN][service.data["entry_id"]][CROUTER].api(service.data["method"], service.data["endpoint"], data_json)
        _LOGGER.debug(f'Services request_api response - {response}')
        return {"response": response}
    hass.services.async_register(DOMAIN, "request_api", request_api, supports_response=SupportsResponse.OPTIONAL)

    async def backup_router(service: ServiceCall):
        response = await hass.data[DOMAIN][service.data["entry_id"]][CROUTER].async_backup(service.data["folder"], service.data["type"])
        return True
    hass.services.async_register(DOMAIN, "backup_router", backup_router)


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    hass.services.async_remove(DOMAIN, "request_api")
    hass.services.async_remove(DOMAIN, "backup_router")