from typing import Tuple
import asyncio

import click
from netcad.logger import get_logger
from netcad.cli.common_opts import opt_devices, opt_designs
from netcad.cli.device_inventory import get_devices_from_designs

from netcad_netbox.aionetbox import NetboxClient
from netcad_netbox.device_sync import nb_device_push
from netcad_netbox.cabling_sync import nb_cabling_sync


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
def cli_nb_push(devices: Tuple[str], designs: Tuple[str], status: str):
    """
    Push design devices into NetBox
    """
    log = get_logger()

    if not (device_objs := get_devices_from_designs(designs, include_devices=devices)):
        log.error("No devices located in the given designs")
        return

    async def run():
        async with NetboxClient() as nb_api:
            # push each of the devices into NetBox.
            await asyncio.gather(
                *{
                    nb_device_push(nb_api, dev_obj, status=status)
                    for dev_obj in device_objs
                }
            )

            # ensure cabling is good.
            await nb_cabling_sync(nb_api, device_objs)

    asyncio.run(run())
