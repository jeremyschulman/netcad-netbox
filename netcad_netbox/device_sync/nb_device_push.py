from netcad.device import Device
from netcad.logger import get_logger


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
    log.info(f"START: Pushing device {dev.name} into NetBox ...")
    log.info(f"DONE: Pushing device {dev.name} into NetBox completed.")
