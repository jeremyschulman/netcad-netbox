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
import logging
from types import MappingProxyType
from netcad.device import DeviceInterface
from netcad.device.device_type import DeviceInterfaceType
from netcad.phy_port import PhyPortFormFactorType, PhyPortSpeeds
from netcad.logger import get_logger

# ['virtual',
#  'bridge',
#  'lag',
#  '100base-tx',
#  '1000base-t',
#  '2.5gbase-t',
#  '5gbase-t',
#  '10gbase-t',
#  '10gbase-cx4',
#  '1000base-x-gbic',
#  '1000base-x-sfp',
#  '10gbase-x-sfpp',
#  '10gbase-x-xfp',
#  '10gbase-x-xenpak',
#  '10gbase-x-x2',
#  '25gbase-x-sfp28',
#  '50gbase-x-sfp56',
#  '40gbase-x-qsfpp',
#  '50gbase-x-sfp28',
#  '100gbase-x-cfp',
#  '100gbase-x-cfp2',
#  '200gbase-x-cfp2',
#  '100gbase-x-cfp4',
#  '100gbase-x-cpak',
#  '100gbase-x-qsfp28',
#  '200gbase-x-qsfp56',
#  '400gbase-x-qsfpdd',
#  '400gbase-x-osfp',
#  '1000base-kx',
#  '10gbase-kr',
#  '10gbase-kx4',
#  '25gbase-kr',
#  '40gbase-kr4',
#  '50gbase-kr',
#  '100gbase-kp4',
#  '100gbase-kr2',
#  '100gbase-kr4',
#  'ieee802.11a',
#  'ieee802.11g',
#  'ieee802.11n',
#  'ieee802.11ac',
#  'ieee802.11ad',
#  'ieee802.11ax',
#  'ieee802.11ay',
#  'ieee802.15.1',
#  'other-wireless',
#  'gsm',
#  'cdma',
#  'lte',
#  'sonet-oc3',
#  'sonet-oc12',
#  'sonet-oc48',
#  'sonet-oc192',
#  'sonet-oc768',
#  'sonet-oc1920',
#  'sonet-oc3840',
#  '1gfc-sfp',
#  '2gfc-sfp',
#  '4gfc-sfp',
#  '8gfc-sfpp',
#  '16gfc-sfpp',
#  '32gfc-sfp28',
#  '64gfc-qsfpp',
#  '128gfc-qsfp28',
#  'infiniband-sdr',
#  'infiniband-ddr',
#  'infiniband-qdr',
#  'infiniband-fdr10',
#  'infiniband-fdr',
#  'infiniband-edr',
#  'infiniband-hdr',
#  'infiniband-ndr',
#  'infiniband-xdr',
#  't1',
#  'e1',
#  't3',
#  'e3',
#  'xdsl',
#  'docsis',
#  'gpon',
#  'xg-pon',
#  'xgs-pon',
#  'ng-pon2',
#  'epon',
#  '10g-epon',
#  'cisco-stackwise',
#  'cisco-stackwise-plus',
#  'cisco-flexstack',
#  'cisco-flexstack-plus',
#  'cisco-stackwise-80',
#  'cisco-stackwise-160',
#  'cisco-stackwise-320',
#  'cisco-stackwise-480',
#  'juniper-vcp',
#  'extreme-summitstack',
#  'extreme-summitstack-128',
#  'extreme-summitstack-256',
#  'extreme-summitstack-512',
#  'other']

NETBOX_IF_TYPE_MAP = MappingProxyType(
    {
        (PhyPortFormFactorType.RJ45, PhyPortSpeeds.speed_100M): "100base-tx",
        (PhyPortFormFactorType.RJ45, PhyPortSpeeds.speed_1G): "1000base-t",
        (PhyPortFormFactorType.RJ45, PhyPortSpeeds.speed_2_5G): "2.5gbase-t",
        (PhyPortFormFactorType.RJ45, PhyPortSpeeds.speed_5G): "5gbase-t",
        (PhyPortFormFactorType.RJ45, PhyPortSpeeds.speed_10G): "10gbase-t",
        (PhyPortFormFactorType.SFP, PhyPortSpeeds.speed_1G): "1000base-x-sfp",
        (PhyPortFormFactorType.SFPP, PhyPortSpeeds.speed_10G): "10gbase-x-sfpp",
        (PhyPortFormFactorType.SFP28, PhyPortSpeeds.speed_10G): "10gbase-x-sfpp",
        (PhyPortFormFactorType.SFP28, PhyPortSpeeds.speed_25G): "25gbase-x-sfp28",
        (PhyPortFormFactorType.SFP28, PhyPortSpeeds.speed_50G): "50gbase-x-sfp28",
        (PhyPortFormFactorType.QSFPP, PhyPortSpeeds.speed_40G): "40gbase-x-qsfpp",
        (PhyPortFormFactorType.QSFP28, PhyPortSpeeds.speed_100G): "100gbase-x-qsfp28",
    }
)


def netbox_map_interface_type(iface_obj: DeviceInterface) -> str:
    """
    This function is used to return the NetBox interface "type" string that is
    associated to the design device interface object.

    Parameters
    ----------
    iface_obj:
        The design device interface object.
    """
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

    try:
        if_type_key = (
            phy_profile.form_factor or phy_profile.transceiver.form_factor,
            phy_profile.speed,
        )
    except AttributeError:
        logging.error(
            f"{dev_name}:{iface_obj.name} profile {if_prof.name} missing form-factor information, please check."
        )
        return "other"

    if nb_if_type := NETBOX_IF_TYPE_MAP.get(if_type_key):
        return nb_if_type

    get_logger().warning(
        f"{dev_name}:{iface_obj.name}: unknown NetBox interface "
        f'type for form/speed {if_type_key}, default = "other"'
    )

    return "other"
