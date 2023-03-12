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

from httpx import Response
from first import first
from .netbox_client import NetboxClient


async def fetch_site(api: NetboxClient, site_slug: str):
    res: Response = await api.op.dcim_sites_list(params=dict(slug=site_slug))
    res.raise_for_status()

    if site_rec := first(res.json()["results"]):
        return site_rec

    raise RuntimeError(f"NetBox missing site {site_slug}, please resolve.")


async def fetch_platform(api: NetboxClient, platform: str):
    res: Response = await api.op.dcim_platforms_list(params=dict(slug=platform))
    res.raise_for_status()

    if platform_rec := first(res.json()["results"]):
        return platform_rec

    raise RuntimeError(f"NetBox missing platform {platform}, please resolve.")


async def fetch_device_role(api: NetboxClient, device_role: str):
    res: Response = await api.op.dcim_device_roles_list(params=dict(slug=device_role))
    res.raise_for_status()

    if device_role_rec := first(res.json()["results"]):
        return device_role_rec

    raise RuntimeError(f"NetBox missing device-role {device_role}, please resolve.")


async def fetch_device_type(api: NetboxClient, device_type: str):
    res: Response = await api.op.dcim_device_types_list(params=dict(model=device_type))
    res.raise_for_status()
    if device_type_rec := first(res.json()["results"]):
        return device_type_rec

    raise RuntimeError(f"NetBox missing device-type {device_type}, please resolve.")


async def fetch_device_ipaddrs(api: NetboxClient, device_id: int) -> list[dict]:
    """
    Retrieves all IP address records for the given device.  If the device does not have
    any IP addresses assigned, then the empty-list is returned.

    Parameters
    ----------
    api:
        The instance to the NetBox API client.

    device_id:
        The NetBox device-ID value.
    """
    res: Response = await api.op.ipam_ip_addresses_list(
        params=dict(device_id=device_id)
    )
    res.raise_for_status()
    return res.json()["results"]
