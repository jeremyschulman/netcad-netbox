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
