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
# Public Imports
# -----------------------------------------------------------------------------

from httpx import Response
from netcad.device import Device
from netcad.logger import get_logger

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------


from netcad_netbox.aionetbox import NetboxClient

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["nb_sync_device_obj_primary_ip"]


# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


async def nb_sync_device_obj_primary_ip(
    nb_api: NetboxClient,
    dev: Device,
    nb_dev_rec: dict,
    nb_if_ipaddr_map: dict[tuple[str, str], dict],
):
    """
    This function is used to sync the NetBox device primary IP value from the design.

    Parameters
    ----------
    nb_api:
        Instance to the NetBox REST API.

    dev:
        Instance to the design device

    nb_dev_rec
        The NetBox device record

    nb_if_ipaddr_map
        The map of NetBox IP address records, key=(device-name,
        interface-name), value=NetBox IP record.
    """
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
    if res.is_error:
        log.error(
            f"{dev.name}: failed to assign IP {dsn_pri_if_ipaddr} on "
            f"interface {if_name} as primary IP: {res.text}"
        )
        return

    log.info(f"{dev.name}: assigned IP {dsn_pri_if_ipaddr} on {if_name} as primary IP")
