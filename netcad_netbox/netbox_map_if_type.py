from types import MappingProxyType
from netcad.device import DeviceInterface
from netcad.device.device_type import DeviceInterfaceType
from netcad.phy_port import PhyPortFormFactorType, PhyPortSpeeds
from netcad.logger import get_logger

NETBOX_IF_TYPE_MAP = MappingProxyType(
    {
        (PhyPortFormFactorType.RJ45, PhyPortSpeeds.speed_1G): "1000base-t",
        (PhyPortFormFactorType.RJ45, PhyPortSpeeds.speed_2_5G): "2.5gbase-t",
        (PhyPortFormFactorType.RJ45, PhyPortSpeeds.speed_5G): "5gbase-t",
        (PhyPortFormFactorType.RJ45, PhyPortSpeeds.speed_1G): "10gbase-t",
        (PhyPortFormFactorType.SFP, PhyPortSpeeds.speed_1G): "1000base-x-sfp",
        (PhyPortFormFactorType.SFPP, PhyPortSpeeds.speed_10G): "10gbase-x-sfpp",
        (PhyPortFormFactorType.SFP28, PhyPortSpeeds.speed_25G): "25gbase-x-sfp28",
        # (PhyPortFormFactorType.SFP28, PhyPortSpeeds.speed_50G): "50gbase-x-sfp28",
        (PhyPortFormFactorType.QSFPP, PhyPortSpeeds.speed_40G): "40gbase-x-qsfpp",
        (PhyPortFormFactorType.QSFP28, PhyPortSpeeds.speed_100G): "100gbase-x-qsfp28",
    }
)


def netbox_map_interface_type(iface_obj: DeviceInterface) -> str:
    # if the interface is not used, that is it does not have a profile
    # assigned, then examine the interface spec from the device-spec to
    # determine the interface type. if there is no interface type in the
    # lookup-table, then report that warned and use "other" for now.

    dev_obj = iface_obj.device
    dev_name = dev_obj.name

    if not (if_prof := iface_obj.profile):
        if_spec: DeviceInterfaceType = dev_obj.device_type_spec.get_interface(
            if_name=iface_obj.name
        )
        if_key = (if_spec.formfactor, if_spec.speed)

        if nb_if_type := NETBOX_IF_TYPE_MAP.get(if_key):
            return nb_if_type

        get_logger().warning(
            f"{dev_name}:{iface_obj.name}: unknown NetBox interface "
            f'type for form/speed {if_key}, default = "other"'
        )

        return "other"

    # see if this is a non-physical interface before using the physical lookup
    # table.

    if if_prof.is_lag:
        return "lag"
    elif if_prof.is_loopback:
        return "virtual"
    elif if_prof.is_virtual:
        return "virtual"

    if not (phy_profile := if_prof.phy_profile):
        get_logger().error(
            f'{dev_name}:{iface_obj.name}: expending phy-profile, missing.  Using "other" for now.'
        )

    if_type_key = (
        phy_profile.form_factor or phy_profile.transceiver.form_factor,
        phy_profile.speed,
    )

    if nb_if_type := NETBOX_IF_TYPE_MAP.get(if_type_key):
        return nb_if_type

    get_logger().warning(
        f"{dev_name}:{iface_obj.name}: unknown NetBox interface "
        f'type for form/speed {if_type_key}, default = "other"'
    )

    return "other"
