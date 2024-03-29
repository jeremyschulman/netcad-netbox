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

from httpx import Response
from first import first

from netcad.device import Device
from netcad.logger import get_logger

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from netcad_netbox.aionetbox import NetboxClient, nb_fetch

from netcad_netbox.netbox_design_config import (
    NetBoxDesignConfig,
    NetBoxDeviceProperties,
)

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["nb_sync_device_obj"]

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


async def nb_sync_device_obj(
    nb_api: NetboxClient, dev: Device, dev_prop_obj: NetBoxDeviceProperties, status: str
):
    """
    This function is used to sync the device properties into NetBox.

    Notes
    -----
    The primary IP address is handled separately after interfaces and
    ip-address records have been populated.
    """

    res: Response = await nb_api.op.dcim_devices_list(params=dict(name=dev.name))
    res.raise_for_status()

    if not (nb_dev_rec := first(res.json()["results"])):
        return await nb_create_new_device_obj(nb_api, dev, dev_prop_obj)

    # if we are here, then the device record exists, and we should check to see
    # if the properties match our expected values.

    return await nb_sync_existing_device_obj(nb_api, dev, status, nb_dev_rec)


# =============================================================================
#
#                    Push / Create New Device Record
#
# =============================================================================


async def nb_create_new_device_obj(
    nb_api: NetboxClient, dev: Device, dev_props_design: NetBoxDeviceProperties
) -> dict | None:
    """
    Creates a new NetBox device record.  If ok, then this function returns the
    new record object.  If not OK, then this function returns None.
    """

    log = get_logger()
    log.info(f"{dev.name}: Creating new NetBox device record")

    dt_rec = await nb_fetch.fetch_device_type(
        nb_api, device_type=dev_props_design.device_type
    )
    site_rec = await nb_fetch.fetch_site(nb_api, site_slug=dev_props_design.site)
    dr_rec = await nb_fetch.fetch_device_role(
        nb_api, device_role=dev_props_design.device_role
    )
    os_rec = await nb_fetch.fetch_platform(nb_api, platform=dev_props_design.platform)

    new_dev_obj = dict(
        name=dev.name,
        status=dev_props_design.status,
        site=site_rec["id"],
        device_type=dt_rec["id"],
        role=dr_rec["id"],
        platform=os_rec["id"],
    )

    res: Response = await nb_api.op.dcim_devices_create(json=new_dev_obj)
    if res.is_error:
        log.error(f"{dev.name}: Failed to create record in NetBox: {res.text}")
        return None

    log.info(f"{dev.name}: Created in NetBox OK.")
    return res.json()


# =============================================================================
#
#                    Push / Sync Existing Device Record
#
# =============================================================================


async def nb_sync_existing_device_obj(
    nb_api: NetboxClient, dev: Device, status: str, nb_dev_obj: dict
) -> dict | None:
    """
    Updates the existing NetBox record with the property values from the
    design. If this process is OK, this function returns the updated NetBox
    record. If this process fails, then this funciton returns None.
    """
    log = get_logger()
    log.info(f"{dev.name}: Sync existing NetBox device record: ")

    # need the product-model from the device-type
    res = await nb_api.get(nb_dev_obj["device_type"]["url"])
    device_type_data = res.json()

    dev_platform_obj = nb_dev_obj.get("platform") or {}
    dev_pri_ip_obj = nb_dev_obj["primary_ip"] or {}

    dev_props_has = NetBoxDeviceProperties(
        status=nb_dev_obj["status"]["value"],
        primary_ip=dev_pri_ip_obj.get("address") or "",
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
        return nb_dev_obj

    return await _patch_nb_record(
        nb_api, dev, dev_props_design, nb_dev_obj, mismatch_fields
    )


async def _patch_nb_record(
    nb_api,
    dev,
    dev_props_design,
    nb_dev_obj,
    mismatch_fields,
) -> dict | None:
    """
    This function is called when any of the device property values need to be
    updated.
    """

    log = get_logger()

    log.info(f'{dev.name}: need to update {", ".join(mismatch_fields)}')

    patch_nb_dev = dict(
        name=nb_dev_obj["name"],
        site=nb_dev_obj["site"]["id"],
        device_type=nb_dev_obj["device_type"]["id"],
        device_role=nb_dev_obj["device_role"]["id"],
        platform=(nb_dev_obj["platform"] or {}).get("id"),
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
                log.warning(
                    f'{dev.name}: device-type "{dev_props_design.device_type}" matches, '
                    f'but not product-model "{dev_props_design.product_model}", check NetBox.'
                )

    res: Response = await nb_api.op.dcim_devices_partial_update(
        id=nb_dev_obj["id"], json=patch_nb_dev
    )

    if res.is_error:
        log.error(f"{dev.name}: NetBox device record update failed: {res.text}")
        return None

    log.info(f"{dev.name}: NetBox device record update OK.")
    return res.json()
