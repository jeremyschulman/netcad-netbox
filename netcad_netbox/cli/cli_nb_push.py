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

from typing import Tuple
import asyncio

import click
from netcad.design import Design
from netcad.logger import get_logger
from netcad.cli.common_opts import opt_devices, opt_designs
from netcad.cli.device_inventory import get_devices_from_designs

from netcad_netbox.aionetbox import NetboxClient
from netcad_netbox.device_sync import nb_device_push
from netcad_netbox.nb_site_sync import nb_sync_sites

from netcad_netbox.nb_cabling_sync import nb_cabling_sync
from netcad_netbox.netbox_design_config import NetBoxDesignConfig

from .cli_nb_main import clig_netbox_main


@clig_netbox_main.command("push")
@click.option(
    "--status",
    help="NetBox status slug",
    type=click.Choice(["active", "planned", "staged"]),
    default="planned",
)
@opt_devices()
@opt_designs()
@click.option("--no-cabling", is_flag=True, help="Skp the cabling sync step")
def cli_nb_push(
    devices: Tuple[str], designs: Tuple[str], status: str, no_cabling: bool
):
    """
    Push design devices into NetBox
    """
    log = get_logger()

    if not (device_objs := get_devices_from_designs(designs, include_devices=devices)):
        log.error("No devices located in the given designs")
        return

    # -------------------------------------------------------------------------
    # get the collection of all devices in all the given designs provided by
    # the User.  We need to keep track of all unique design instances (though
    # typically just one) and all device objects.
    # -------------------------------------------------------------------------

    design_insts: dict[Design, NetBoxDesignConfig] = dict()
    nbdev_prop_objs = dict()

    for dev in device_objs:
        nb_design_cfg: NetBoxDesignConfig = dev.design.config["netcad_netbox"]
        design_insts[dev.design] = nb_design_cfg

        # not all devices in the design could be put into NetBox.
        if not (
            nbdev_prop_obj := nb_design_cfg.get_device_properties(dev, status=status)
        ):
            continue

        nbdev_prop_objs[dev] = nbdev_prop_obj

    # -------------------------------------------------------------------------
    # we need the collection of the NetBox site property objects so that we can
    # ensure they exist before we start attempting to create devices.
    # -------------------------------------------------------------------------

    nbsite_prop_objs = set()
    for nb_design in design_insts.values():
        nbsite_prop_objs.add(nb_design.get_site_properties(status=status))

    async def run():
        """run the process in an asyncio context"""

        async with NetboxClient() as nb_api:
            # ensure that each of the sites exist in NetBox ... if they do not,
            # then automatically create them.
            await nb_sync_sites(nb_api, nbsite_prop_objs)

            # push each of the devices into NetBox.
            await asyncio.gather(
                *{
                    nb_device_push(nb_api, dev_obj, dev_prop_obj, status=status)
                    for dev_obj, dev_prop_obj in nbdev_prop_objs.items()
                }
            )

            if not no_cabling:
                # ensure cabling is good.
                await nb_cabling_sync(nb_api, nbdev_prop_objs)

    asyncio.run(run())
