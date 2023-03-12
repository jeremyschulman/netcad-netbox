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

import asyncio
from typing import Iterable

from http import HTTPStatus
from httpx import Response
from first import first

from netcad.logger import get_logger
from netcad.device import Device, DeviceInterface
from netcad_netbox.aionetbox import NetboxClient


async def nb_cabling_sync(nb_api: NetboxClient, device_objs: Iterable[Device]):
    log = get_logger()
    log.info("Checking cabling ... ")
    # -------------------------------------------------------------------------
    # Formulate the design cabling map from the list of provided devices.
    # -------------------------------------------------------------------------

    def cable_key(if_obj: DeviceInterface):
        _if_key = (if_obj.device.name, if_obj.name)
        _rmt_if_obj: DeviceInterface = if_obj.cable_peer
        _rmt_key = (_rmt_if_obj.device.name, _rmt_if_obj.name)
        return tuple(sorted((_if_key, _rmt_key)))

    dev_cables = set()

    for dev_obj in device_objs:
        dev_cables.update(
            {
                cable_key(interface)
                for interface in dev_obj.interfaces.values()
                if interface.cable_peer and not interface.profile.is_lag
            }
        )

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
        if_rec = first(each_res.json()["results"])
        dev_if_rec_map[(if_rec["device"]["name"], if_rec["name"])] = if_rec

    # -------------------------------------------------------------------------
    # Formulate cabling actions.
    # -------------------------------------------------------------------------

    add_cables = set()
    del_cables = set()

    for lcl_key, rmt_key in dev_cables:
        lcl_if_rec = dev_if_rec_map[lcl_key]

        # if there is no cable yet, then add one.

        if not lcl_if_rec["cable"]:
            add_cables.add((lcl_key, rmt_key))
            continue

        # if there is a cable, but it is connected to the wrong peer, then we
        # need to remove it, and add the correct one.

        has_link_peer_obj = lcl_if_rec["link_peers"][0]
        has_link_peer_key = (
            has_link_peer_obj["device"]["name"],
            has_link_peer_obj["name"],
        )

        if has_link_peer_key == rmt_key:
            continue

        del_cables.add(lcl_key)
        del_cables.add(rmt_key)
        add_cables.add((lcl_key, rmt_key))

    if not del_cables or add_cables:
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

        if res.status_code != HTTPStatus.CREATED:
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
    log = get_logger()

    for if_rec in del_cable_if_recs:
        dev_name = if_rec["device"]["name"]
        if_name = if_rec["name"]
        cable_id = if_rec["cable"]["id"]

        res: Response = await nb_api.op.dcim_cables_delete(id=cable_id)

        if res.status_code != HTTPStatus.OK:
            log.error(f"{dev_name}:{if_name} failed to remove cable: {res.text}")
            continue

        log.info(f"{dev_name}:{if_name} cable removed OK")
