from typing import Iterable
from http import HTTPStatus

from httpx import Response

from netcad.logger import get_logger
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
    await _create_interfaces(
        nb_api, dev, nb_dev_id=nb_dev_rec["id"], add_if_names=add_if_names
    )
    await _sync_existing_interfaces(
        nb_api, dev, chk_if_recs=map(nb_if_name_map.get, chk_if_names)
    )


async def _create_interfaces(
    nb_api: NetboxClient, dev: Device, add_if_names: set[str], nb_dev_id: int
):
    log = get_logger()
    new_if_map = dict()

    for if_name in add_if_names:
        if_obj = dev.interfaces[if_name]
        if_prof = if_obj.profile
        if if_prof.is_lag:
            if_type = "lag"
        elif if_prof.is_loopback:
            if_type = "virtual"
        elif if_prof.is_virtual:
            if_type = "virtual"
        else:
            if_type = "other"

        new_if_body = dict(
            device=nb_dev_id,
            name=if_name,
            type=if_type,
            description=if_obj.desc,
            enabled=if_obj.enabled,
        )

        res: Response = await nb_api.op.dcim_interfaces_create(json=new_if_body)
        if res.status_code != HTTPStatus.CREATED:
            log.error(f"{dev.name}: {if_name}: failed to be created: {res.text}")
            continue

        log.info(f"{dev.name}: {if_name}: created OK.")
        new_if_map[if_name] = res.json()


async def _delete_interfaces(nb_api: NetboxClient, del_if_recs: Iterable[dict]):
    pass


async def _sync_existing_interfaces(
    nb_api: NetboxClient, dev: Device, chk_if_recs: Iterable[dict]
):
    pass
