#  Copyright 2023 Jeremy Schulman
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

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
    """
    This function is used to sync interface IP adddress assignements into NetBox.

    Parameters
    ----------
    nb_api
    device:
        The design device instance.

    nb_dev_rec:
        The NetBox device record for this device.

    nb_if_map:
        The NetBox interfaces for this device, where key=if-name, and
        value=NetBox interface record.
    """

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

    has_keys = set(if_ipaddr_map_has)
    exp_keys = set(if_ipaddr_map_exp)

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

    # -------------------------------------------------------------------------
    # Process new IP addresses
    # -------------------------------------------------------------------------

    if add_if_ipaddrs := (exp_keys - has_keys):
        new_if_ipaddr_map = await _add_if_ipaddrs(
            nb_api, device, add_if_ipaddrs, nb_if_map
        )
        if_ipaddr_map_has.update(new_if_ipaddr_map)

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
    """
    Called when IP addresses need to be added and assigned to NetBox interfaces.
    """

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
    """
    Called when IP addresses need to be removed from interfaces that are
    managed by the design.
    """
    log = get_logger()
    dev_name = device.name
    for if_ipaddr_rec in del_if_ipaddr_recs:
        if_ipaddr = if_ipaddr_rec["address"]
        if_name = if_ipaddr_rec["assigned_object"]["name"]
        res: Response = await nb_api.op.ipam_ip_addresses_delete(id=if_ipaddr_rec["id"])

        if res.is_error:
            log.error(
                f"{dev_name}:{if_name}: IP addresse {if_ipaddr} failed to remove: {res.text}"
            )
            continue

        log.info(f"{dev_name}:{if_name}: IP addresse {if_ipaddr} removed OK")
