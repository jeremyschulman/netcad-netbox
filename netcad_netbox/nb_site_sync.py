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

import asyncio

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from first import first
from netcad.logger import get_logger

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from .netbox_design_config import NetBoxSiteProperties

__all__ = ["nb_sync_sites"]

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


async def nb_sync_sites(nb_api, sites: set[NetBoxSiteProperties]):
    """
    This function ensures that the sites used by the design exist in NetBox.

    Parameters
    ----------
    nb_api:
        Instance to the NetBox API client

    sites:
        The set of Netcad-NetBox site properties; one for each site.
    """

    # determine which sites need to be created by checking the existing set in
    # netbox.

    known_site_slugs = set(
        first(res.json()["results"], default={}).get("slug")
        for res in await asyncio.gather(
            *(nb_api.op.dcim_sites_list(params=dict(slug=site.site)) for site in sites)
        )
    )

    # determine the set of sites that need to be created

    if not (need_sites := {site.site for site in sites} - known_site_slugs):
        return

    log = get_logger()

    site_prop_obj: NetBoxSiteProperties

    for site_prop_obj in filter(lambda _s: _s.site in need_sites, sites):
        # get the site-group records for any site-obj that needs it since we need
        # that group-id (int) when creating the site.

        res = await nb_api.op.dcim_site_groups_list(
            params=dict(slug=site_prop_obj.site_group)
        )

        if not res.is_error:
            site_group_id = res.json()["results"][0]["id"]
        else:
            log.warning(
                "site-group=%s for site=%s does not exist, skipping field, but adding site",
                site_prop_obj.site_group,
                site_prop_obj.name,
            )
            site_group_id = None

        res = await nb_api.op.dcim_sites_create(
            json=dict(
                name=site_prop_obj.site.upper(),
                description=site_prop_obj.description,
                slug=site_prop_obj.site,
                group=site_group_id,
            )
        )

        if res.is_error:
            log.error("Unable to create site '%s': %s", site_prop_obj.site, res.text)
            continue

        log.info("Site '%s' created", site_prop_obj.name)
