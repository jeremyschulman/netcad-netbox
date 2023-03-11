from typing import Tuple
import asyncio

import click
from netcad.logger import get_logger
from netcad.cli.common_opts import opt_devices, opt_designs
from netcad.cli.device_inventory import get_devices_from_designs

from netcad_netbox.device_sync import nb_device_push

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

    asyncio.run(nb_device_push(device_objs[0], status=status))
