from typing import Iterable
from httpx import Response
from netcad.device import Device
from netcad_netbox.aionetbox import NetboxClient


async def nb_sync_device_interface_objs(
    nb_api: NetboxClient, dev: Device, nb_dev_rec: dict
):
    res: Response = await nb_api.op.dcim_interfaces_list(
        params=dict(device_id=nb_dev_rec["id"])
    )
    res.raise_for_status()

    nb_if_name_map = {rec["name"]: rec for rec in res.json()["results"]}

    has_if_names = set(nb_if_name_map)
    expd_if_names = set(dev.interfaces)

    chk_if_names = expd_if_names & has_if_names
    add_if_names = expd_if_names - has_if_names
    unx_if_names = has_if_names - expd_if_names  # unexpected

    await _delete_interfaces(nb_api, del_if_recs=map(nb_if_name_map.get, unx_if_names))
    await _create_interfaces(nb_api, dev, add_if_names)
    await _sync_existing_interfaces(
        nb_api, dev, chk_if_recs=map(nb_if_name_map.get, chk_if_names)
    )


async def _create_interfaces(nb_api: NetboxClient, dev: Device, add_if_names: set[str]):
    pass


async def _delete_interfaces(nb_api: NetboxClient, del_if_recs: Iterable[dict]):
    pass


async def _sync_existing_interfaces(
    nb_api: NetboxClient, dev: Device, chk_if_recs: Iterable[dict]
):
    pass
