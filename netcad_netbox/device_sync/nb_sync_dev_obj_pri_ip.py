from netcad.device import Device
from netcad.logger import get_logger

from http import HTTPStatus
from httpx import Response

from netcad_netbox.aionetbox import NetboxClient


async def nb_sync_device_obj_primary_ip(
    nb_api: NetboxClient,
    dev: Device,
    nb_dev_rec: dict,
    nb_if_ipaddr_map: dict[tuple[str, str], dict],
):
    log = get_logger()

    pri_if_obj = dev.primary_ip.interface
    if_name = pri_if_obj.name
    dsn_pri_if_ipaddr = str(pri_if_obj.profile.if_ipaddr)

    # ensure that the expected IP address exists in NetBox so that we can make
    # the assignement / chanage.

    if not (nb_ip_rec := nb_if_ipaddr_map.get((if_name, dsn_pri_if_ipaddr))):
        log.error(
            f"{dev.name}: unexpectedly missing IP address for "
            f"interface: {if_name} address: {dsn_pri_if_ipaddr}, please check NetBox."
        )
        return

    # If the NetBox device record primary IP is correctly set, then nothing
    # more to do.

    if (nb_ip_obj := nb_dev_rec["primary_ip"]) and (
        nb_ip_obj["address"] == dsn_pri_if_ipaddr
    ):
        return

    # if here, then either the primary IP was not set, or the primary IP
    # address was not correct. in either case, patch the device record with the
    # correct IP address record.

    res: Response = await nb_api.op.dcim_devices_partial_update(
        id=nb_dev_rec["id"], json=dict(primary_ip4=nb_ip_rec["id"])
    )
    if res.status_code != HTTPStatus.OK:
        log.error(
            f"{dev.name}: failed to assign IP {dsn_pri_if_ipaddr} on "
            f"interface {if_name} as primary IP: {res.text}"
        )
        return

    log.info(f"{dev.name}: assigned IP {dsn_pri_if_ipaddr} on {if_name} as primary IP")
