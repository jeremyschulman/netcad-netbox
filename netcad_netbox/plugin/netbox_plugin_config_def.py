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

from pydantic import BaseModel, Extra
from pydantic_env.models import EnvSecretStr, EnvUrl

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["NetBoxPluginConfig"]

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Use pydantic models to validate the User configuration file.  Configure
# pydantic to prevent the User from providing (accidentally) any fields that are
# not specifically supported; via the Extra.forbid config.
# -----------------------------------------------------------------------------


class NetBoxPluginConfig(BaseModel, extra=Extra.forbid):
    """
    Configuration in the netcad.toml file for the plugig "config" seciotn.
    For exmaple:

    [[netcad.plugins]]
        name = 'NetBox'
        package = "netcad_netbox"

        config.netbox_url = "$NETBOX_ADDR"
        config.netbox_token = "$NETBOX_TOKEN"
    """

    netbox_url: EnvUrl
    netbox_token: EnvSecretStr
    timeout: int = 60
