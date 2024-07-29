"""The Keenetic API."""

from __future__ import annotations
from hashlib import md5, sha256
from collections.abc import Mapping
from typing import Literal, Any
import asyncio
import aiohttp
import logging
import aiofiles.os
from pathlib import Path
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

@dataclass
class KeeneticFullData:
    show_system: dict[str, Any]
    show_ip_hotspot: DataDevice
    show_interface: dict[str, Any]
    show_rc_ip_static: dict[str, Any]
    show_associations: dict[str, Any]
    show_ip_hotspot_policy: dict[str, Any]
    priority_interface: dict[str, Any]

@dataclass
class DataDevice():
    mac: str
    name: str
    hostname: str
    ip: str
    active: bool
    interface_id: str
    uptime: int

@dataclass
class DataPortForwarding():
    name: str
    interface: str
    protocol: str
    port: int
    end_port: str
    to_host: str
    index: str
    comment: str
    disable: bool = False

@dataclass
class DataRcInterface():
    id: str
    name_interface: str
    interface: str
    ssid: str
    password: str
    active: str
    rename: str
    description: str


INTERFACES_NAME = {
    "GigabitEthernet1": "WAN",
    "Wireguard0": "Wireguard",
    "WifiMaster0": "WiFi 2.4g",
    "WifiMaster1": "WiFi 5g"
}


class Router:
    def __init__(
        self, 
        session: aiohttp.ClientSession, 
        username="admin", 
        password="admin", 
        host="192.168.1.1", 
        port: int = 80, 
        ssl: bool | None = False,
        ):
        self._session = session
        self.host = host
        self.url_router = f'{host}:{port}'
        self._username = username
        self._password = password

        self._mac = ""
        self._serial_number = ""
        self._model = ""
        self._hw_type = ""
        self._hw_id = ""
        self._name_device = ""

    @property
    def mac(self):
        return self._mac
    @property
    def serial_number(self):
        return self._serial_number
    @property
    def model(self):
        return self._model
    @property
    def hw_type(self):
        return self._hw_type
    @property
    def hw_id(self):
        return self._hw_id
    @property
    def name_device(self):
        return self._name_device


    async def async_setup_obj(self):
        await self.auth()

        data_show_identification = await self.show_identification()
        self._mac = data_show_identification["mac"]
        self._serial_number = data_show_identification["serial"]

        data_show_version = await self.show_version()
        self._model = data_show_version["model"]
        self._hw_id = data_show_version["hw_id"]
        self._name_device = data_show_version["device"]

        data_show_system_mode = await self.show_system_mode()
        self._hw_type = data_show_system_mode["active"]


    async def async_download_file(self, download_url, folder):
        try:
            await aiofiles.os.makedirs(folder, exist_ok=True)
            async with self._session.get(download_url, timeout=180) as response:
                    if response.status != 200:
                        raise Exception('Got non-200 response!')
                    async with aiofiles.open(f"{folder}/{response.content_disposition.filename}", 'wb') as file:
                        async for data, _ in response.content.iter_chunks():
                            await file.write(data)
        except asyncio.TimeoutError as err:
            raise Exception("TimeoutError") from err
        return True

    async def reguest_api(self, method: str, endpoint: str, json: Mapping[str, Any] | None = None, headers: str | None = None) -> tuple[aiohttp.ClientResponse]:
        url = self.url_router + endpoint
        try:
            _LOGGER.debug(f'{self._mac} request - {endpoint} - {json}')
            async with self._session.request(method=method, url=url, json=json, headers=headers) as res:
                if res.status == 200 and res.content_type == 'application/json':
                    result = await res.json()
                elif res.status == 200 and res.content_type == 'application/javascript':
                    result = await res.text()
                    result = self.data_parser(result)
                else:
                    result = res
                _LOGGER.debug(f'{self._mac} status - {endpoint} {res.status}')
        except asyncio.TimeoutError as err:
            raise Exception("TimeoutError") from err
        return result



    async def api(self, method: str, endpoint: str, json: Mapping[str, Any] | None = {}):
        resp = await self.auth()
        return await self.reguest_api(method, endpoint, json)

    async def auth(self):
        response = await self.reguest_api("get", "/auth")
        if response.status == 401:
            password = f"{self._username}:{response.headers['X-NDM-Realm']}:{self._password}"
            password = md5(password.encode("utf-8"))
            password = response.headers["X-NDM-Challenge"] + password.hexdigest()
            password = sha256(password.encode("utf-8")).hexdigest()
            response = await self.reguest_api("post", "/auth", json={"login": self._username, "password": password})
            if response.status == 401:
                raise Exception(response)
        return response.status == 200

    async def components_list(self):
        return await self.api("post", "/rci/components/list")

    async def release_notes(self, version: str, channel: str = "dev"):
        return await self.api("post", "/rci/webhelp/release-notes", {"version":f"{version}","locale":"ru","channel":f"{channel}"})

    async def show_identification(self):
        return await self.api("get", "/rci/show/identification")

    async def async_reboot(self):
        return await self.api("post", "/rci/system/reboot", {})

    async def async_update(self):
        return await self.api("post", "/rci/components/commit", {"reason": "manual"})

    async def async_backup(self, folder: str, type_fw: list = ["firmware", "config"]):
        if "firmware" in type_fw:
            await self.async_download_file(f"{self.url_router}/ci/firmware", folder)
        if "config" in type_fw:
            await self.async_download_file(f"{self.url_router}/ci/startup-config", folder)
        return True

    async def show_system(self):
        return await self.api("get", "/rci/show/system")

    async def show_system_mode(self):
        return await self.api("get", "/rci/show/system/mode")

    async def show_version(self):
        return await self.api("get", "/rci/show/version")

    async def ndm_components(self):
        return await self.api("get", "/ndmComponents.js")

    async def show_ip_hotspot(self):
        return await self.api("get", "/rci/show/ip/hotspot/host")

    async def show_interface(self):
        return await self.api("get", "/rci/show/interface")

    async def show_rc_interface(self):
        interfaces = await self.api("get", "/rci/show/rc/interface")
        interface_wifi = {}
        for interface in interfaces:
            interf = interfaces[interface]
            if interf.get("authentication", False):
                psw = interf["authentication"]["wpa-psk"]["psk"]
            else:
                psw = None
            interface_wifi[interface] = DataRcInterface(
                interface,
                INTERFACES_NAME.get(interface.split('/')[0], interface),
                interface.split('/')[0],
                interf.get("ssid", False),
                psw,
                interf.get("up", False),
                interf.get("rename", None),
                interf.get("description", None),
            )
        return interface_wifi

    async def show_associations(self):
        return await self.api("get", "/rci/show/associations")

    async def show_interface_stat(self, interface: str):
        return await self.api("get", f"/rci/show/interface/stat?name={interface}")

    async def ip_hotspot_host_list(self):
        return await self.api("get", "/rci/ip/hotspot/host")

    async def ip_policy_list(self):
        return await self.api("get", "/rci/ip/policy")
    # async def ip_hotspot_host_access(self, mac: str, access: str):
    #     return await self.api("post", "/rci/ip/hotspot/host", f'{"mac": {mac}, "access": {access}}')

    async def ip_hotspot_host_policy(self, mac: str, access: str = "permit", policy: str = False):
        data_send = {"mac": mac, "access": access, "policy": policy}
        return await self.api("post", "/rci/ip/hotspot/host", data_send)

    async def turn_on_off_interface(self, interface: str, state: str):
        return await self.api("post", f"/rci/interface/{interface}", {state: "true"})
        # return await self.api("get", "/rci/interface")

    async def turn_on_off_port_forwarding(self, port_forwarding: str, state: bool):
        data_send = [
            {
                "ip": {
                    "index": port_forwarding,
                    "static": {
                        "disable": not state
                    }
                }
            },
            {"system": {"configuration": {"save": {}}}}
        ]
        return await self.api("post", f"/rci/", data_send)


    def data_parser(self, data):
        new_data = {}
        data = data.replace('\n\t', '').replace('\n', '')
        data = data.split(';')
        for row in data:
            if row != '':
                row = row.split('=')
                nu = row[0].rstrip()
                te = row[1].lstrip()
                if '{' not in te:
                    te = te.replace('"', '')
                new_data[nu] = te
        return new_data


    async def custom_request(self):
        if self.hw_type == "router":
            data_json_send=[
                {"show": {"system": {}}}, 
                {"show": {"interface": {}}},
                {"show": {"associations": {}}},

                {"show": {"ip": {"hotspot": {}}}},
                {"show": {"rc": {"ip": {"static": {}}}}},

                {"show": {"rc": {"ip": {"hotspot": {}}}}},

                {"show": {"rc": {"interface": {"ip": {"global": {}}}}}},
            ]
        else:
            data_json_send=[
                {"show": {"system": {}}}, 
                {"show": {"interface": {}}},
                {"show": {"associations": {}}},
            ]

        full_info_other = await self.api("post", "/rci/", json=data_json_send)

        show_system = full_info_other[0]['show']['system']
        data_show_interface = full_info_other[1]['show']['interface']
        show_associations = full_info_other[2]['show']['associations']

        show_interface = {}
        show_ip_hotspot = {}
        show_rc_ip_static = {}
        show_ip_hotspot_policy = {}
        priority_interface = {}

        for dsi in data_show_interface:
            show_interface[dsi] = data_show_interface[dsi]
            nm = INTERFACES_NAME.get(dsi.split('/')[0], dsi)
            if dsi.startswith('WifiMaster0') or dsi.startswith('WifiMaster1'):
                nm = f"{nm} {data_show_interface[dsi]['interface-name']}"
            show_interface[dsi]['name'] = nm

        if self.hw_type == "router":
            data_show_ip_hotspot = full_info_other[3]['show']['ip']['hotspot']['host']
            # show_rc_ip_static = full_info_other[4]['show']['rc']['ip']['static']
            data_show_ip_hotspot_policy = full_info_other[5]['show']['rc']['ip']['hotspot']['host']
            for hotspot in data_show_ip_hotspot:
                show_ip_hotspot[hotspot["mac"]] = DataDevice(
                    hotspot.get('mac'), 
                    hotspot.get('name'), 
                    hotspot.get('hostname'), 
                    hotspot.get('ip'), 
                    hotspot.get('active'), 
                    hotspot.get('interface', {"id": None}).get('id'),
                    hotspot.get('uptime'), 
                )

            for hotspot_pl in data_show_ip_hotspot_policy:
                show_ip_hotspot_policy[hotspot_pl["mac"]] = hotspot_pl


            data_show_rc_ip_static = full_info_other[4]['show']['rc']['ip']['static']
            for port_frw in data_show_rc_ip_static:
                show_rc_ip_static[port_frw["index"]] = DataPortForwarding(
                    port_frw.get('comment', port_frw.get('index')), 
                    port_frw.get('interface'), 
                    port_frw.get('protocol'), 
                    port_frw.get('port'), 
                    port_frw.get('end-port', port_frw.get('port')), 
                    port_frw.get('to-host'), 
                    port_frw.get('index'), 
                    port_frw.get('comment', None), 
                    port_frw.get('disable', False), 
                )
            
            priority_interface = full_info_other[6]['show']['rc']['interface']['ip']['global']

        return KeeneticFullData(
            show_system, 
            show_ip_hotspot, 
            show_interface, 
            show_rc_ip_static, 
            show_associations, 
            show_ip_hotspot_policy,
            priority_interface,
            )