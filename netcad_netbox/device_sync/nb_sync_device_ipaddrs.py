from typing import Iterable

from http import HTTPStatus
from httpx import Response

from netcad.device import Device, DeviceNonExclusive
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

    # -------------------------------------------------------------------------
    # get the IP addresses assigned in the design:
    # -------------------------------------------------------------------------

    if_ipaddr_map_exp = {
        (iface.name, str(iface.profile.if_ipaddr)): iface
        for iface in device.interfaces.used().values()
        if isinstance(iface.profile, InterfaceL3) and iface.profile.if_ipaddr
    }

    # -------------------------------------------------------------------------
    # Process new IP addresses
    # -------------------------------------------------------------------------

    has_keys = set(if_ipaddr_map_has)
    exp_keys = set(if_ipaddr_map_exp)

    if add_if_ipaddrs := (exp_keys - has_keys):
        new_if_ipaddr_map = await _add_if_ipaddrs(
            nb_api, device, add_if_ipaddrs, nb_if_map
        )
        if_ipaddr_map_has.update(new_if_ipaddr_map)

    # -------------------------------------------------------------------------
    # if the device is exclusively managed by NetCAD/CAM and there are
    # unepected IP addresses in NetBox, then remove these.
    # -------------------------------------------------------------------------

    if (del_if_ipaddrs := (has_keys - exp_keys)) and (
        not isinstance(device, DeviceNonExclusive)
    ):
        await _del_if_ipaddrs(
            nb_api, device, map(if_ipaddr_map_has.get, del_if_ipaddrs)
        )
        for del_key in del_if_ipaddrs:
            del if_ipaddr_map_has[del_key]

    # return the current map of NetBox Interface IP addresses.
    return if_ipaddr_map_has


# -----------------------------------------------------------------------------
#
#              Add NetBox IP address records to Interface Records
#
# -----------------------------------------------------------------------------


async def _add_if_ipaddrs(
    nb_api: NetboxClient,
    device: Device,
    add_keys: set[tuple[str, str]],
    nb_if_map: dict[str, dict],
) -> dict[tuple[str, str], dict]:
    log = get_logger()
    new_if_ipaddr_map = dict()

    for if_name, if_ipaddr in add_keys:
        nb_if_id = nb_if_map[if_name]["id"]

        new_ip_body = dict(
            address=if_ipaddr,
            assigned_object_type="dcim.interface",
            assigned_object_id=nb_if_id,
        )

        res: Response = await nb_api.op.ipam_ip_addresses_create(json=new_ip_body)
        if res.status_code != HTTPStatus.CREATED:
            log.error(
                f"{device.name}:{if_name} IP address {if_ipaddr} failed to create: {res.text}"
            )
            continue

        log.info(
            f"{device.name}:{if_name} IP address {if_ipaddr} created and assigned OK"
        )
        new_if_ipaddr_map[(if_name, if_ipaddr)] = res.json()

    return new_if_ipaddr_map


# -----------------------------------------------------------------------------
#
#              Delete NetBox IP address records not in Design
#
# -----------------------------------------------------------------------------


async def _del_if_ipaddrs(
    nb_api: NetboxClient,
    device: Device,
    del_if_ipaddr_recs: Iterable[dict],
):
    log = get_logger()
    dev_name = device.name
    for if_ipaddr_rec in del_if_ipaddr_recs:
        if_ipaddr = if_ipaddr_rec["address"]
        if_name = if_ipaddr_rec["assigned_object"]["name"]
        res: Response = await nb_api.op.ipam_ip_addresses_delete(id=if_ipaddr_rec["id"])
        if res.status_code == HTTPStatus.OK:
            log.info(f"{dev_name}:{if_name}: IP addresse {if_ipaddr} removed OK")
            continue

        log.error(
            f"{dev_name}:{if_name}: IP addresse {if_ipaddr} failed to remove: {res.text}"
        )
