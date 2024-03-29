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

from netcad.device import Device
from netcad.logger import get_logger

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from netcad_netbox.aionetbox import NetboxClient
from netcad_netbox.netbox_design_config import NetBoxDeviceProperties
from netcad_netbox import device_sync

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["nb_device_push"]

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


async def nb_device_push(
    nb_api: NetboxClient, dev: Device, dev_prop_obj: NetBoxDeviceProperties, status: str
):
    """
    This is the main function that will push all aspects of a device into NetBox. This
    includes the NetBox device object, interface objects, ip-address objects.

    Notes
    -----
    Cabling is done as a separate process after all devices have been push.

    Parameters
    ----------
    nb_api:
        The instance to the NetBox API client

    dev:
        The device object from the device for which we will push data into NetBox

    dev_prop_obj:
        The NetBox plugin device properties object

    status:
        The expected NetBox device status (slug), for example "active" or "planning"
    """
    log = get_logger()
    log.info(f"{dev.name}: Pushing device into NetBox ...")

    nb_dev_rec = await device_sync.nb_sync_device_obj(nb_api, dev, dev_prop_obj, status)

    if not nb_dev_rec:
        log.error(f"{dev.name}: aborting further NetBox push due to prior errors.")

    nb_dev_if_map = await device_sync.nb_sync_device_interface_objs(
        nb_api, dev, nb_dev_rec
    )

    await device_sync.nb_sync_device_lag_objs(nb_api, dev, nb_dev_if_map)

    nb_dev_if_ipaddr_map = await device_sync.nb_sync_device_ipaddr_objs(
        nb_api, dev, nb_dev_rec, nb_dev_if_map
    )

    await device_sync.nb_sync_device_obj_primary_ip(
        nb_api, dev, nb_dev_rec, nb_dev_if_ipaddr_map
    )

    log.info(f"{dev.name}: Pushing device into NetBox completed.")
