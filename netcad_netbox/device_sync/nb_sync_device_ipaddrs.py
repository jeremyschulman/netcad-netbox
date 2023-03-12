from collections import defaultdict

from http import HTTPStatus
from httpx import Response

from netcad.device import Device, DeviceInterface
from netcad.device.profiles import InterfaceLag
from netcad.logger import get_logger
from netcad.device.profiles.l3_interfaces import InterfaceL3

from netcad_netbox.aionetbox import NetboxClient
from netcad_netbox.aionetbox.nb_fetch import fetch_device_ipaddrs


async def nb_sync_device_ipaddr_objs(
    nb_api: NetboxClient, device: Device, nb_dev_rec: dict, nb_if_map: dict[str, dict]
):
    # -------------------------------------------------------------------------
    # get the IP addresses assigned ot this device in NetBox
    # -------------------------------------------------------------------------

    nb_ip_recs = await fetch_device_ipaddrs(nb_api, device_id=nb_dev_rec["id"])
    if_ipaddr_map_has = dict()  # key=(if-name, ip-addr), value=nb-ip-rec

    for ip_rec in nb_ip_recs:
        if_ipaddr = ip_rec["address"]
        if_name = ip_rec["assigned_object"]["name"]
        if_ipaddr_map_has[(if_name, if_ipaddr)] = ip_rec

    # get the IP addresses assigned in the design:

    if_ipaddr_map_exp = {
        (iface.name, str(iface.profile.if_ipaddr)): iface
        for iface in device.interfaces.used().values()
        if isinstance(iface.profile, InterfaceL3) and iface.profile.if_ipaddr
    }

    has_keys = set(if_ipaddr_map_has)
    exp_keys = set(if_ipaddr_map_exp)

    if add_if_ipaddrs := (exp_keys - has_keys):
        await _add_if_ipaddrs(nb_api, device, add_if_ipaddrs, nb_if_map)

    if del_if_ipaddrs := (has_keys - exp_keys):
        await _del_if_ipaddrs(nb_api, device)


async def _add_if_ipaddrs(
    nb_api: NetboxClient,
    device: Device,
    add_keys: set[tuple[str, str]],
    nb_if_map: dict[str, dict],
):
    log = get_logger()

    for if_name, if_ipaddr in add_keys:
        nb_if_id = nb_if_map[if_name]["id"]

        new_ip_body = dict(
            address=if_ipaddr,
            assigned_object_type="dcim.interface",
            assigned_object_id=nb_if_id,
        )

        res: Response = await nb_api.op.ipam_ip_addresses_create(json=new_ip_body)
        if res.status_code == HTTPStatus.CREATED:
            log.info(
                f"{device.name}:{if_name} IP address {if_ipaddr} created and assigned OK"
            )
            continue

        log.error(
            f"{device.name}:{if_name} IP address {if_ipaddr} failed to create: {res.text}"
        )


async def _del_if_ipaddrs(
    nb_api: NetboxClient,
    device: Device,
):
    pass
