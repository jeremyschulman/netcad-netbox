from typing import Optional

from pydantic.dataclasses import dataclass
from pydantic import Field
from netcad.design import Design
from netcad.device import Device


def find_mismatched_fields(me, other):
    return {
        field
        for field in getattr(me, "__dataclass_fields__")
        if getattr(me, field) != getattr(other, field)
    }


@dataclass
class NetBoxDeviceProperties:
    site: str
    status: str
    device_role: str
    device_type: str
    platform: str
    product_model: str
    primary_ip: str

    def __sub__(self, other: "NetBoxDeviceProperties") -> set[str]:
        return find_mismatched_fields(self, other)


@dataclass
class NetBoxInterfaceProperties:
    enabled: bool
    description: str
    if_type: str
    tags: Optional[list[str]] = Field(default_factory=list)
    is_mgmt_only: Optional[bool] = Field(False)

    def __sub__(self, other: "NetBoxInterfaceProperties") -> set[str]:
        return find_mismatched_fields(self, other)


class NetBoxDesignConfig:
    def __init__(self, design: Design):
        self.design = design

    def get_device_properties(
        self, device: Device, status: str
    ) -> NetBoxDeviceProperties:
        raise NotImplementedError()
