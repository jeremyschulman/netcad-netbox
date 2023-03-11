from pydantic.dataclasses import dataclass
from netcad.design import Design
from netcad.device import Device


@dataclass
class NetBoxDeviceProperties:
    site: str
    status: str
    device_role: str
    device_type: str
    platform: str
    product_model: str

    def __sub__(self, other: "NetBoxDeviceProperties") -> set[str]:
        return {
            field
            for field in self.__dataclass_fields__
            if getattr(self, field) != getattr(other, field)
        }


class NetBoxDesignConfig:
    def __init__(self, design: Design):
        self.design = design

    def get_device_properties(
        self, device: Device, status: str
    ) -> NetBoxDeviceProperties:
        raise NotImplementedError()
