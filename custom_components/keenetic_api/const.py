"""The Keenetic API constants."""

from typing import Final

DOMAIN: Final = "keenetic_api"

MIN_SCAN_INTERVAL: Final = 1
DEFAULT_SCAN_INTERVAL: Final = 30
REQUEST_TIMEOUT: Final = 30
SCAN_INTERVAL_FIREWARE: Final = 1800

COORD_FULL: Final = "coordinator_full"
COORD_FIREWARE: Final = "coordinator_firmware"
COORD_RC_INTERFACE: Final = "coordinator_rc_interface"

CONF_CLIENTS_SELECT_POLICY: Final = "cliens_select_policy"
CONF_CREATE_ALL_CLIENTS_POLICY: Final = "create_entity_all_cliens_button_policy"
CONF_CREATE_IMAGE_QR: Final = "create_image_qr"
CONF_CREATE_PORT_FRW: Final = "create_entity_port_forwarding"
CONF_BACKUP_TYPE_FILE: Final = "backup_type_file"

CONF_CREATE_DT: Final = "create_device_tracker"

FW_SANDBOX: Final = {
    "stable": "main",
    "preview": "preview",
    "draft": "dev"
}

POLICY_DEFAULT: Final = "default"
POLICY_NOT_INTERNET: Final = "not_internet"

CROUTER: Final = "client_router"

DEFAULT_BACKUP_TYPE_FILE: Final = ["config"]

COUNT_REPEATED_REQUEST_FIREWARE: Final = 15
TIMER_REPEATED_REQUEST_FIREWARE: Final = 0.3