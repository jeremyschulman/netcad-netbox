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
# System Imports
# -----------------------------------------------------------------------------

from typing import Sequence
import asyncio

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from httpx import Response
from first import first

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from .netbox_client import NetboxClient
from .pager import Pager

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = [
    "fetch_site",
    "fetch_platform",
    "fetch_device_ipaddrs",
    "fetch_device_role",
    "fetch_device_type",
    "fetch_devices_by_name",
]

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


async def fetch_site(api: NetboxClient, site_slug: str):
    """
    This function is used to return the NetBox Site record assocaited to the
    site_slug.  If the value is not found then this function will raise a
    RuntimeError.
    """
    res: Response = await api.op.dcim_sites_list(params=dict(slug=site_slug))
    res.raise_for_status()

    if site_rec := first(res.json()["results"]):
        return site_rec

    raise RuntimeError(f"NetBox missing site {site_slug}, please resolve.")


async def fetch_platform(api: NetboxClient, platform: str):
    """
    This function is used to return the NetBox Platform record assocaited to
    the platform (slug).  If the value is not found then this function will
    raise a RuntimeError.
    """

    res: Response = await api.op.dcim_platforms_list(params=dict(slug=platform))
    res.raise_for_status()

    if platform_rec := first(res.json()["results"]):
        return platform_rec

    raise RuntimeError(f"NetBox missing platform {platform}, please resolve.")


async def fetch_device_role(api: NetboxClient, device_role: str):
    """
    This function is used to return the NetBox Device-Role record assocaited to
    the device_role (slug).  If the value is not found then this function will
    raise a RuntimeError.
    """

    res: Response = await api.op.dcim_device_roles_list(params=dict(slug=device_role))
    res.raise_for_status()

    if device_role_rec := first(res.json()["results"]):
        return device_role_rec

    raise RuntimeError(f"NetBox missing device-role {device_role}, please resolve.")


async def fetch_device_type(api: NetboxClient, device_type: str):
    """
    This function is used to return the NetBox Device-Type record assocaited to
    the device_type (model name, not slug).  If the value is not found then
    this function will raise a RuntimeError.
    """

    res: Response = await api.op.dcim_device_types_list(params=dict(model=device_type))
    res.raise_for_status()
    if device_type_rec := first(res.json()["results"]):
        return device_type_rec

    raise RuntimeError(f"NetBox missing device-type {device_type}, please resolve.")


async def fetch_device_ipaddrs(api: NetboxClient, device_id: int) -> list[dict]:
    """
    Retrieves all IP address records for the given device.  If the device does not have
    any IP addresses assigned, then the empty-list is returned.
    """

    return await Pager(api).all(
        api.op.ipam_ip_addresses_list, params=dict(device_id=device_id)
    )


async def fetch_device_interfaces(api: NetboxClient, device_id: int) -> list[dict]:
    """
    Retrieves all interface records for the given device.  If the device does
    not have any interfaces, then the empty-list is returned.
    """
    return await Pager(api).all(
        api.op.dcim_interfaces_list, params=dict(device_id=device_id)
    )


async def fetch_devices_by_name(
    api: NetboxClient, names: Sequence[str], **params
) -> list[dict]:
    """
    Fetch netbox devices give a list of names.

    Parameters
    ----------
    api:
        Instance to NetBox client

    names:
        A list of device hostnames to retrieve from NetBox.

    Other Parameters
    ----------------
    Any other NetBox API supported parameters.  For example, getting only
    decommissioning devices, an extra param would be: status='decommissioning'

    Returns
    -------
    List of NetBox device records.
    """
    gathered = await asyncio.gather(
        *(api.op.dcim_devices_list(params=dict(name=name, **params)) for name in names)
    )
    records = [rec for res in gathered for rec in res.json()["results"]]
    found_names = {rec["name"] for rec in records}
    if missing_names := (set(names) - found_names):
        raise RuntimeError(f"NetBox missing devices: {missing_names}")

    return records
