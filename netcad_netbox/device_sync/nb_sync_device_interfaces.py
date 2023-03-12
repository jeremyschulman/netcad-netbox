from typing import Iterable
from http import HTTPStatus

from httpx import Response

from netcad.logger import get_logger
from netcad.device import Device

from netcad_netbox.aionetbox import NetboxClient
from netcad_netbox.netbox_map_if_type import netbox_map_interface_type
from netcad_netbox.netbox_design_config import NetBoxInterfaceProperties


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

    await _delete_interfaces(
        nb_api, dev, del_if_recs=map(nb_if_name_map.get, unx_if_names)
    )

    for if_name in unx_if_names:
        del nb_if_name_map[if_name]

    new_if_map = await _create_interfaces(
        nb_api, dev, nb_dev_id=nb_dev_rec["id"], add_if_names=add_if_names
    )
    nb_if_name_map.update(new_if_map)

    upd_if_map = await _sync_existing_interfaces(
        nb_api, dev, chk_if_recs=map(nb_if_name_map.get, chk_if_names)
    )
    nb_if_name_map.update(upd_if_map)

    return nb_if_name_map


# -----------------------------------------------------------------------------
#
#                    Create new NetBox Interface Records
#
# -----------------------------------------------------------------------------


async def _create_interfaces(
    nb_api: NetboxClient, dev: Device, add_if_names: set[str], nb_dev_id: int
) -> dict[str, dict]:
    log = get_logger()
    new_if_map = dict()

    for if_name in add_if_names:
        if_obj = dev.interfaces[if_name]
        if_type = netbox_map_interface_type(if_obj)

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

    return new_if_map


# -----------------------------------------------------------------------------
#
#                    Update existing NetBox Interface Records
#
# -----------------------------------------------------------------------------


async def _sync_existing_interfaces(
    nb_api: NetboxClient, dev: Device, chk_if_recs: Iterable[dict]
) -> dict[str, dict]:
    """
    This function updates any interfaces that needs to be updated.  Any updated
    interface records are returned.

    Parameters
    ----------
    nb_api
        The instance to the NetBox API

    dev
        The design device

    chk_if_recs
        The list of NetBox interface records that will be used to check against the
        design device interfaces
    """
    log = get_logger()

    updated_if_recs = dict()

    for nb_if_rec in chk_if_recs:
        if_name = nb_if_rec["name"]
        dsn_if_obj = dev.interfaces[if_name]

        if_props_has = NetBoxInterfaceProperties(
            description=nb_if_rec["description"],
            enabled=nb_if_rec["enabled"],
            if_type=nb_if_rec["type"]["value"],
        )

        if_props_epx = NetBoxInterfaceProperties(
            description=dsn_if_obj.desc,
            if_type=netbox_map_interface_type(dsn_if_obj),
            enabled=dsn_if_obj.enabled,
        )

        if if_props_epx == if_props_has:
            # no change
            continue

        patch_if_body = dict(
            name=if_name,
            type=if_props_epx.if_type,
            description=if_props_epx.description,
            enabled=if_props_epx.enabled,
        )

        res = await nb_api.op.dcim_interfaces_partial_update(
            id=nb_if_rec["id"], json=patch_if_body
        )

        if res.status_code != HTTPStatus.OK:
            log.error(f"{dev.name}:{if_name} update failed: {res.text}")
            continue

        log.info(f"{dev.name}: {if_name}: updated OK")
        updated_if_recs[if_name] = res.json()

    return updated_if_recs


# -----------------------------------------------------------------------------
#
#                 Delete NetBox Interface Records not in design
#
# -----------------------------------------------------------------------------


async def _delete_interfaces(
    nb_api: NetboxClient, dev: Device, del_if_recs: Iterable[dict]
):
    pass
