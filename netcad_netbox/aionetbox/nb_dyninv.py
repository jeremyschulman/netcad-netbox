# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Sequence
from ipaddress import IPv4Interface

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.device import DeviceNonExclusive
from netcad.device.profiles import InterfaceL3

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from netcad_netbox.aionetbox import NetboxClient, Pager
from .nb_fetch import fetch_devices_by_name

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["NetBoxDynamicInventory"]

# -----------------------------------------------------------------------------
#
#                             CODE BEGINS
#
# -----------------------------------------------------------------------------


class NetBoxDynamicInventory:
    """
    This class is used to create a NETCAD list of Device instances using Netbox
    device records as the source of truth.
    """

    def __init__(self):
        """Constructor for the NetBoxDynamicInventory class."""
        self.netbox_devices: dict[int, dict] = dict()
        self.devices: set[DeviceNonExclusive] = set()

    # -------------------------------------------------------------------------
    #
    #                                   Public Methods
    #
    # -------------------------------------------------------------------------

    @staticmethod
    def api(**kwargs) -> NetboxClient:
        """
        This function is used to return an API client instance to NetBox so
        that the Caller can make direct calls as needed to retrieve device
        records.

        Other Parameters
        ----------------
        Any parameters supported by the NetboxClient constructor.

        Returns
        -------
        The NetboxClient instance.
        """
        return NetboxClient(**kwargs)

    async def fetch_devices(self, **params) -> Sequence[dict]:
        """
        This function is used to retrieve a list of device records.  The caller must provide
        the API parameters that will be used in the call to GET /dcim/devices.  The resulting
        device records are added to the internally managed list of NetBox devices.

        Parameters
        ----------
        params
            The NetBox /dcim/devices query parameters.

        Returns
        -------
        The list of retrieve device records
        """
        async with NetboxClient() as api:
            records = await Pager(api).all(api.op.dcim_devices_list, params=params)

        self.add_netbox_devices(records)

        return records

    def add_netbox_devices(self, records: dict):
        self.netbox_devices.update({rec["id"]: rec for rec in records})

    async def custom_fetch(self, fetching_func, *args, **kwargs):
        """
        This function is used to call a custom fetching function that will retrieve
        the device records.  The Caller must provide the function and any additional
        arguments that are needed for the function to execute.

        Parameters
        ----------
        fetching_func
            The custom fetching function that will retrieve the device records.

        args
            The list of positional arguments for the fetching function.

        kwargs
            The list of keyword arguments for the fetching function.

        Returns
        -------
        The list of device records.
        """
        async with self.api() as api:
            async for nb_recs in fetching_func(api, *args, **kwargs):
                self.add_netbox_devices(nb_recs)

    async def fetch_devices_by_name(self, names: Sequence[str]):
        """
        This function is used to retrieve a list of device records by name.  The caller must provide
        the list of device names.  The resulting device records are added to the internally managed list
        of NetBox devices.

        Parameters
        ----------
        names
            The list of device names to retrieve.

        Returns
        -------
        The list of device records.
        """
        devices = await fetch_devices_by_name(self.api(), names)
        self.add_netbox_devices(devices)
        return devices

    def build_inventory(self) -> Sequence[DeviceNonExclusive]:
        """
        This property is used to return the list of Device instances that have been
        retrieved from NetBox.

        Returns
        -------
        The list of Device instances.
        """

        dev_type_map = {
            # we need to define specific class definitions dynamically using
            # "type" for each of the OS+Device-Type combinations. we will map
            # these to the Device instances that we will create.
            (os_name, device_type): type(
                f"{os_name}_{device_type}",
                (DeviceNonExclusive,),
                dict(os_name=os_name, device_type=device_type.upper()),
            )
            # build the unique set of OS+Device-Type combinations so that we
            # can dynamically build the classes for each of these.
            for os_name, device_type in set(
                (dev["platform"]["slug"], dev["device_type"]["slug"])
                for dev in self.netbox_devices.values()
            )
        }

        # Using the built type mapping, return a list of the Device instances
        # for each of the NetBox device records.

        dev: DeviceNonExclusive

        self.devices.clear()

        for nb_dev in self.netbox_devices.values():
            dev_cls = dev_type_map[
                (nb_dev["platform"]["slug"], nb_dev["device_type"]["slug"])
            ]
            dev = dev_cls(name=nb_dev["name"])
            pri_intf = dev.interfaces["primary_interface"]
            pri_intf.profile = InterfaceL3(
                if_ipaddr=IPv4Interface(nb_dev["primary_ip"]["address"])
            )
            dev.set_primary_ip_interface(pri_intf)
            self.devices.add(dev)

        return self.devices

    # -------------------------------------------------------------------------
    #
    #                                   DUNDER METHODS
    #
    # -------------------------------------------------------------------------

    def __len__(self):
        """returns the number of devices currently in the inventory."""
        return len(self.netbox_devices)

    # -------------------------------------------------------------------------
    #                           Context Manager Methods
    #
    #   The purpose of the context manager is to automatically call the
    #   build_inventory method once the Caller has completed their "fetch"
    #   methods.  For example:
    #
    #   async with NetBoxDynamicInventory() as dyninv:
    #       await dyninv.fetch_devices(site="HQ")
    #
    #  Upon exiting the context manager, the inventory will be built into the
    #  'devices' attribute.  The Caller must then add those devices to the
    #  design.
    # -------------------------------------------------------------------------

    async def __aenter__(self):
        """returns the instance when entering the context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """create the inventory when exiting the context manager."""
        self.build_inventory()
