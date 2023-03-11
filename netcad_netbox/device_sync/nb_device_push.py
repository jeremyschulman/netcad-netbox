from netcad.device import Device
from netcad.logger import get_logger

from netcad_netbox.aionetbox import NetboxClient
from netcad_netbox import device_sync


async def nb_device_push(dev: Device, status: str):
    """
    This is the main function that will push all aspects of a device into NetBox. This
    includes the NetBox device object, interface objects, ip-address objects.

    Notes
    -----
    Cabling is done as a separate process after all devices have been push.

    Parameters
    ----------
    dev:
        The device object from the device for which we will push data into NetBox

    status:
        The expected NetBox device status (slug), for example "active" or "planning"
    """
    log = get_logger()
    log.info(f"{dev.name}: Pushing device  into NetBox ...")
    async with NetboxClient() as nb_api:
        await device_sync.nb_sync_device_obj(nb_api, dev, status)

    log.info(f"{dev.name}: Pushing device into NetBox completed.")
