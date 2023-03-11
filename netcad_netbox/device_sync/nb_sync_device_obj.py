from http import HTTPStatus
from httpx import Response

from netcad.device import Device
from netcad.logger import get_logger

from netcad_netbox.aionetbox import NetboxClient, nb_fetch

from netcad_netbox.netbox_design_config import (
    NetBoxDesignConfig,
    NetBoxDeviceProperties,
)

from first import first


async def nb_sync_device_obj(nb_api: NetboxClient, dev: Device, status: str):
    res: Response = await nb_api.op.dcim_devices_list(params=dict(name=dev.name))
    res.raise_for_status()

    if not (nb_dev_rec := first(res.json()["results"])):
        await nb_create_new_device_obj(nb_api, dev, status)
        return

    # if we are here, then the device record exists, and we should check to see
    # if the properties match our expected values.

    await nb_sync_existing_device_obj(nb_api, dev, status, nb_dev_rec)


async def nb_create_new_device_obj(nb_api: NetboxClient, dev: Device, status: str):
    log = get_logger()
    log.info(f"Creating new NetBox device record: {dev.name}")


async def nb_sync_existing_device_obj(
    nb_api: NetboxClient, dev: Device, status: str, nb_dev_obj: dict
):
    log = get_logger()
    log.info(f"{dev.name}: Sync existing NetBox device record: ")

    # need the product-model from the device-type
    res = await nb_api.get(nb_dev_obj["device_type"]["url"])
    device_type_data = res.json()

    dev_platform_obj = nb_dev_obj.get("platform") or {}

    dev_props_has = NetBoxDeviceProperties(
        status=nb_dev_obj["status"]["value"],
        device_type=nb_dev_obj["device_type"]["display"],
        device_role=nb_dev_obj["device_role"]["slug"],
        platform=dev_platform_obj.get("slug") or "",
        product_model=device_type_data["part_number"],
        site=nb_dev_obj["site"]["slug"],
    )

    nb_design_cfg: NetBoxDesignConfig = dev.design.config["netcad_netbox"]
    dev_props_design = nb_design_cfg.get_device_properties(dev, status=status)

    mismatch_fields = dev_props_design - dev_props_has
    if not mismatch_fields:
        # then nothing to do, all is good.  log the information and return
        log.info(f"{dev.name}: NetBox is correct, no further action.")
        return

    log.info(f'{dev.name}: need to update {", ".join(mismatch_fields)}')

    patch_nb_dev = dict(
        name=nb_dev_obj["name"],
        site=nb_dev_obj["site"]["id"],
        device_type=nb_dev_obj["device_type"]["id"],
        device_role=nb_dev_obj["device_role"]["id"],
        platform=dev_platform_obj.get("id"),
    )

    for field in mismatch_fields:
        match field:
            case "device_type":
                dt_rec = await nb_fetch.fetch_device_type(
                    nb_api, device_type=dev_props_design.device_type
                )
                patch_nb_dev["device_type"] = dt_rec["id"]
            case "device_role":
                dr_rec = await nb_fetch.fetch_device_role(
                    nb_api, device_role=dev_props_design.device_role
                )
                patch_nb_dev["device_role"] = dr_rec["id"]
            case "platform":
                os_rec = await nb_fetch.fetch_platform(
                    nb_api, platform=dev_props_design.platform
                )
                patch_nb_dev["platform"] = os_rec["id"]
            case "site":
                site_rec = await nb_fetch.fetch_site(
                    nb_api, site_slug=dev_props_design.site
                )
                patch_nb_dev["site"] = site_rec["id"]
            case "status":
                patch_nb_dev["status"] = dev_props_design.status
            case "product_model":
                log.error(
                    f'{dev.name}: device-type "{dev_props_design.device_type}" matches, "'
                    f'"but not product-model "{dev_props_design.product_model}", check NetBox.'
                )

    res: Response = await nb_api.op.dcim_devices_partial_update(
        id=nb_dev_obj["id"], json=patch_nb_dev
    )
    if res.status_code == HTTPStatus.OK:
        log.info(f"{dev.name}: NetBox device record update OK.")
    else:
        log.error(f"{dev.name}: NetBox device record update failed: {res.text}")
