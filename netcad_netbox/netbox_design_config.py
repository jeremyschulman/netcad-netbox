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

from typing import Optional

from pydantic.dataclasses import dataclass
from pydantic import Field
from netcad.design import Design
from netcad.device import Device


def find_mismatched_fields(me, other) -> set[str]:
    """used by datacase objects to detect field differences"""
    return {
        field
        for field in getattr(me, "__dataclass_fields__")
        if getattr(me, field) != getattr(other, field)
    }


@dataclass
class NetBoxDeviceProperties:
    """
    Device properites that we want to sync with NetBox
    """

    site: str
    status: str
    device_role: str
    device_type: str
    platform: str
    product_model: str
    primary_ip: str

    def __sub__(self, other: "NetBoxDeviceProperties") -> set[str]:
        """find field differences"""
        return find_mismatched_fields(self, other)


@dataclass
class NetBoxInterfaceProperties:
    """
    Interface properties that we want to sync with NetBox
    """

    enabled: bool
    description: str
    if_type: str
    tags: Optional[list[str]] = Field(default_factory=list)
    is_mgmt_only: Optional[bool] = Field(False)

    def __sub__(self, other: "NetBoxInterfaceProperties") -> set[str]:
        """find field differences"""
        return find_mismatched_fields(self, other)


class NetBoxDesignConfig:
    """
    Any design that wants to use this plugin needs to subclass and provide the
    method implementations.  The configuration object should be stored in:

        design.config['netcad_netbox] = <instance to this config>

    """

    def __init__(self, design: Design):
        """
        Constructor, should be called during the deisgn build process.
        """
        self.design = design

    def get_device_properties(
        self, device: Device, status: str
    ) -> NetBoxDeviceProperties:
        """
        This method is responsible for returing the NetBox specific device
        properpies that are associated to the given device object.

        Parameters
        ----------
        device:
            The design device instance.

        status:
            The NetBox status value, such as "active" or "planned"
        """
        raise NotImplementedError()
