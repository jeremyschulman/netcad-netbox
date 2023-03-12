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

from collections import defaultdict

from http import HTTPStatus
from httpx import Response

from netcad.device import Device
from netcad.device.profiles import InterfaceLag
from netcad.logger import get_logger

from netcad_netbox.aionetbox import NetboxClient


async def nb_sync_device_lag_objs(
    nb_api: NetboxClient, device: Device, nb_if_map: dict[str, dict]
):
    """
    This function is used to form the LAG interface relationships between the
    physical interfaces and the logical LAG interfaces.  This funciton assumes
    that the actual interface objects exist in the given nb_if_map.

    Parameters
    ----------
    nb_api:
        The instance to the NetBox API.

    device:
        The design device object

    nb_if_map:
        The device interface map from NetBox where key=if-name, value=NetBox interface record.
    """

    # -------------------------------------------------------------------------
    # formulate the expected lag interface relationships.
    # -------------------------------------------------------------------------

    lag_ifs_exp = defaultdict(set)
    for if_name, interface in device.interfaces.used().items():
        if not isinstance(interface.profile, InterfaceLag):
            continue

        lag_ifs_exp[interface.name].update(
            iface.name for iface in interface.profile.if_lag_members
        )

    # -------------------------------------------------------------------------
    # formulate the NetBox lag interface relationships.
    # -------------------------------------------------------------------------

    lag_ifs_has = defaultdict(set)
    for if_name, nb_if_obj in nb_if_map.items():
        # if the interface is not in a lag, then skip
        if not (if_lag := nb_if_obj["lag"]):
            continue

        lag_ifs_has[if_lag["name"]].add(nb_if_obj["name"])

    # -------------------------------------------------------------------------
    # formulate the NetBox lag interface relationships.
    # -------------------------------------------------------------------------

    for lag_name, lag_mbrs_exp in lag_ifs_exp.items():
        lag_mbrs_has = lag_ifs_has[lag_name]

        # if all members are present and accounted for, then nothing to do.
        if lag_mbrs_exp == lag_mbrs_has:
            continue

        if del_if_names := (lag_mbrs_has - lag_mbrs_exp):
            await _del_lag_members(nb_api, device, nb_if_map, lag_name, del_if_names)

        if add_if_names := (lag_mbrs_exp - lag_mbrs_has):
            await _add_lag_members(nb_api, device, nb_if_map, lag_name, add_if_names)


async def _add_lag_members(
    nb_api: NetboxClient,
    dev: Device,
    nb_if_map: dict[str, dict],
    lag_name: str,
    add_if_names: set[str],
):
    log = get_logger()
    lag_id = nb_if_map[lag_name]["id"]

    for if_name in add_if_names:
        res: Response = await nb_api.op.dcim_interfaces_partial_update(
            id=nb_if_map[if_name]["id"], json=dict(lag=lag_id)
        )

        if res.status_code == HTTPStatus.OK:
            log.info(f"{dev.name}:{if_name} added to LAG {lag_name} OK")
            continue

        log.error(f"{dev.name}:{if_name} failed add to LAG {lag_name}: {res.text}")


async def _del_lag_members(
    nb_api: NetboxClient,
    dev: Device,
    nb_if_map: dict[str, dict],
    lag_name: str,
    del_if_names: set[str],
):
    log = get_logger()

    for if_name in del_if_names:
        res: Response = await nb_api.op.dcim_interfaces_partial_update(
            id=nb_if_map[if_name]["id"], json=dict(lag=None)
        )

        if res.status_code == HTTPStatus.OK:
            log.info(f"{dev.name}:{if_name} removed from LAG {lag_name} OK")
            continue

        log.error(f"{dev.name}:{if_name} failed remove from LAG {lag_name}: {res.text}")
