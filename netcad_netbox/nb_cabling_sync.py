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

# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

import asyncio
from typing import Iterable

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from httpx import Response
from first import first
from netcad.logger import get_logger
from netcad.device import Device, DeviceInterface

# -----------------------------------------------------------------------------
# Priavte Imports
# -----------------------------------------------------------------------------

from .aionetbox import NetboxClient
from .netbox_design_config import NetBoxDeviceProperties

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["nb_cabling_sync"]

# -----------------------------------------------------------------------------
#
#                              CODE BEGINS
#
# -----------------------------------------------------------------------------


async def nb_cabling_sync(
    nb_api: NetboxClient, device_prop_objs: dict[Device, NetBoxDeviceProperties]
):
    """
    This function is used to ensure the NetBox cabling is correct relative to
    the design device cabling map.
    """

    log = get_logger()
    log.info("Checking cabling ... ")

    # we only want to cable devices in the design that are expected to be in
    # NetBox. not all devices in the design may be in netbox; for example the
    # host devices.

    allowed_device_names = {dev.name for dev in device_prop_objs}

    # -------------------------------------------------------------------------
    # Formulate the design cabling map from the list of provided devices.
    # -------------------------------------------------------------------------

    def cable_key(if_obj: DeviceInterface):
        """
        sorted key for cable-map.

        If either of the endpoint devices are not in the allowed devices names,
        meaning these are devices not expected in NetBox, then return 'None' to
        prevent a cable action to a non-existing device.
        """
        if if_obj.device.name not in allowed_device_names:
            return None

        _rmt_if_obj: DeviceInterface = if_obj.cable_peer

        if _rmt_if_obj.device.name not in allowed_device_names:
            return None

        _if_key = (if_obj.device.name, if_obj.name)
        _rmt_key = (_rmt_if_obj.device.name, _rmt_if_obj.name)
        return tuple(sorted((_if_key, _rmt_key)))

    dev_cables = set()

    for dev_obj in device_prop_objs.keys():
        dev_cables.update(
            {
                cable_key(interface)
                for interface in dev_obj.interfaces.values()
                if interface.cable_peer and not interface.profile.is_lag
            }
        )

    # noinspection PyTypeChecker
    dev_cables.discard(None)

    # -------------------------------------------------------------------------
    # Fetch all of the NetBox device records
    # -------------------------------------------------------------------------

    tasks = []
    for lcl_key, rmt_key in dev_cables:
        tasks.append(
            nb_api.op.dcim_interfaces_list(
                params=dict(device=lcl_key[0], name=lcl_key[1])
            )
        )
        tasks.append(
            nb_api.op.dcim_interfaces_list(
                params=dict(device=rmt_key[0], name=rmt_key[1])
            )
        )

    log.info(f"Fetching {len(tasks)} interface records, please be patient ...")
    dev_if_rec_resps = await asyncio.gather(*tasks)

    # -------------------------------------------------------------------------
    # Formulate the NetBox interface mapping lookup
    # -------------------------------------------------------------------------

    dev_if_rec_map = {}

    each_res: Response
    for each_res in dev_if_rec_resps:
        if not (if_rec := first(each_res.json()["results"])):
            u_parms = each_res.request.url.params
            r_dev_n, r_if_n = u_parms["device"], u_parms["name"]
            log.error(
                f"{r_dev_n}:{r_if_n} interface missing from NetBox, please check."
            )
            continue

        dev_if_rec_map[(if_rec["device"]["name"], if_rec["name"])] = if_rec

    # -------------------------------------------------------------------------
    # Formulate cabling actions.
    # -------------------------------------------------------------------------

    add_cables = set()
    del_cables = set()

    for lcl_key, rmt_key in dev_cables:
        lcl_if_rec = dev_if_rec_map.get(lcl_key)
        rmt_if_rec = dev_if_rec_map.get(rmt_key)

        if not all((lcl_if_rec, rmt_if_rec)):
            continue

        # check for "dangling cables" that have no link peers ... if these
        # exist, then remove the cable.

        if rmt_if_rec["cable"] and not rmt_if_rec["link_peers"]:
            del_cables.add(rmt_key)

        if lcl_if_rec["cable"] and not lcl_if_rec["link_peers"]:
            del_cables.add(lcl_key)

        # if the link-peer does not exist then add

        if not (has_link_peer_obj := first(lcl_if_rec["link_peers"])):
            add_cables.add((lcl_key, rmt_key))
            continue

        has_link_peer_key = (
            has_link_peer_obj["device"]["name"],
            has_link_peer_obj["name"],
        )

        # if the link-peer exists and is correct, then no further action is
        # needed

        if has_link_peer_key == rmt_key:
            continue

        # if here, then the link-peer exists but is connected to the wrong place.

        del_cables.add(lcl_key)
        del_cables.add(rmt_key)
        add_cables.add((lcl_key, rmt_key))

    if not (del_cables or add_cables):
        log.info("No cable changes required.")
        return

    if del_cables:
        log.info(f"Removing {len(del_cables)} cables ...")
        await _del_cabling(nb_api, map(dev_if_rec_map.get, del_cables))

    if add_cables:
        log.info(f"Adding {len(add_cables)} cables ...")
        await _add_cabling(nb_api, add_cables, dev_if_rec_map)


# -----------------------------------------------------------------------------
#
#                    Add NetBox Interface Cabling
#
# -----------------------------------------------------------------------------


async def _add_cabling(
    nb_api: NetboxClient,
    add_cables: set[tuple[tuple[str, str], tuple[str, str]]],
    dev_if_rec_map: dict[tuple[str, str], dict],
):
    """
    This function is used to add the issing cabling that is defined in the
    NetCAD design, but not present in NetBox.

    Parameters
    ----------
    nb_api:
        Instance to the NetBox API.

    add_cables:
        The set of cabling end-point keys, each (device-name, interface-name)

    dev_if_rec_map:
        The dictionary of NetBox device interface records that are keyed by the
        tuple (device-name, interface-name)
    """
    log = get_logger()

    for lcl_key, rmt_key in add_cables:
        lcl_if_rec = dev_if_rec_map[lcl_key]
        rmt_if_rec = dev_if_rec_map[rmt_key]

        # TODO: could cable the 'type' field to the cable create.

        new_cable_body = dict(
            a_terminations=[
                dict(object_type="dcim.interface", object_id=lcl_if_rec["id"])
            ],
            b_terminations=[
                dict(object_type="dcim.interface", object_id=rmt_if_rec["id"])
            ],
        )

        res: Response = await nb_api.op.dcim_cables_create(json=new_cable_body)
        lcl_devn, lcl_ifn = lcl_key
        rmt_devn, rmt_ifn = rmt_key

        if res.is_error:
            log.error(
                f"{lcl_devn}:{lcl_ifn} cabling {rmt_devn}:{rmt_ifn} failed: {res.text}"
            )
            continue

        log.info(f"{lcl_devn}:{lcl_ifn} cabled {rmt_devn}:{rmt_ifn} OK")


# -----------------------------------------------------------------------------
#
#                    Delete NetBox Interface Cabling
#
# -----------------------------------------------------------------------------


async def _del_cabling(nb_api: NetboxClient, del_cable_if_recs: Iterable[dict]):
    """
    This function is used to remove unwanted cabling that is not defined in the
    NetCAD design, but is present in NetBox.

    Parameters
    ----------
    nb_api:
        Instance to the NetBox API.

    del_cable_if_recs:
        The NetBox interface records for which a cable exists and needs to be
        removed.
    """

    log = get_logger()

    for if_rec in del_cable_if_recs:
        dev_name = if_rec["device"]["name"]
        if_name = if_rec["name"]

        if not (if_cable := if_rec["cable"]):
            log.warning(f"{dev_name}:{if_name} no cable to remove, skipping")
            continue

        cable_id = if_cable["id"]

        res: Response = await nb_api.op.dcim_cables_delete(id=cable_id)

        if res.is_error:
            log.error(f"{dev_name}:{if_name} failed to remove cable: {res.text}")
            continue

        log.info(f"{dev_name}:{if_name} cable removed OK")
