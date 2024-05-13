# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Sequence, AsyncGenerator, Callable
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

# For the 'cutom_fetch' method, we define a type hint for the custom fetching
# function.  The function will yield lists of NetBox device records (dict).

YieldsNetBoxDeviceList = AsyncGenerator[list[dict], None]
CustomFetchFuncType = Callable[[NetboxClient, ...], YieldsNetBoxDeviceList]


class NetBoxDynamicInventory:
    """
    This class is used to create a NetCAD list of Device instances using Netbox
    device records as the source of truth.  The Devices are "non-exclusive" in
    so that actions can be performed in a partial-merge configuration mode.

    The NetBoxDynamicInventory supports a context manager; it is to
    automatically call the build_inventory method once the Caller has completed
    their "fetch" methods.  For example:

    async with NetBoxDynamicInventory() as dyninv:
        await dyninv.fetch_devices(site="HQ")

    Upon exiting the context manager, the inventory will be built into the
    'inventory' attribute.  The Caller must then add those inventory to the design.
    """

    def __init__(self):
        """Constructor for the NetBoxDynamicInventory class."""

        # Uses the NetBox device record "id" field as the key into the
        # dictionary so that we have a unique set of device recoreds.  This
        # handles the case where the Caller might have made multiple fetch
        # calls that results in duplicate device records.

        self.netbox_devices: dict[int, dict] = dict()

        # The resulting set of Device instances that are created from the
        # NetBox records.  This set is created by the `build_inventory` method.

        self.inventory: set[DeviceNonExclusive] = set()

    # -------------------------------------------------------------------------
    #
    #                                   Public Methods
    #
    # -------------------------------------------------------------------------

    async def fetch_devices(self, **params) -> Sequence[dict]:
        """
        This function is used to retrieve a list of device records.  The caller
        must provide the API parameters that will be used in the call to GET
        /dcim/inventory.  The resulting device records are added to the
        internally managed list of NetBox inventory.

        Parameters
        ----------
        params
            The NetBox /dcim/inventory query parameters.

        Returns
        -------
        The list of retrieve device records
        """
        async with NetboxClient() as api:
            records = await Pager(api).all(api.op.dcim_devices_list, params=params)

        self.add_netbox_devices(records)

        return records

    async def custom_fetch(self, fetching_func: CustomFetchFuncType, *args, **kwargs):
        """
        This function is used to call a custom fetching function that will retrieve
        the device records.  The Caller must provide the function and any additional
        arguments that are needed for the function to execute.

        The fetching_func must yield the device records as they are retrieved.
        This enables the Caller to process the records as they are retrieved,
        rather than waiting for all records to be collected into a list.

        The fetching_func will be pass a NetBoxClient instance as the first
        argument. The remaining *args and **kwargs are passed as provided by
        the Caller.

        Parameters
        ----------
        fetching_func
            The custom fetching function that will retrieve the device records.

        args
            The list of positional arguments for the fetching function.

        kwargs
            The list of keyword arguments for the fetching function.
        """
        async with self.api() as api:
            async for nb_recs in fetching_func(api, *args, **kwargs):
                self.add_netbox_devices(nb_recs)

    async def fetch_devices_by_name(self, names: Sequence[str]):
        """
        This function is used to retrieve a list of device records by name.  The caller must provide
        the list of device names.  The resulting device records are added to the internally managed list
        of NetBox inventory.

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

    def build_inventory(self):
        """
        This function is used to create list of Device instances based on the
        device records retrieved from NetBox.  The resulting Device inventory
        is stored in the 'inventory' attribute.
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

        self.inventory.clear()

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
            self.inventory.add(dev)

        return self.inventory

    def api(self, **kwargs) -> NetboxClient:  # noqa
        """
        This function is used to return an API client instance to NetBox so
        that the Caller can make direct calls as needed to retrieve device
        records.  This method exists should the Caller want to sublcass and
        customize the NetBoxClient instance.

        Other Parameters
        ----------------
        Any parameters supported by the NetboxClient constructor.

        Returns
        -------
        The NetboxClient instance.
        """
        return NetboxClient(**kwargs)

    def add_netbox_devices(self, records: dict):
        """
        Helper function to add device records to the internal list of NetBox
        inventory.  Uses the NetBox device record "id" field as the key into the
        dictionary so that we have a unique set of device recoreds.  This
        handles the case where the Caller might have made multiple fetch calls
        that results in duplicate device records.
        """
        self.netbox_devices.update({rec["id"]: rec for rec in records})

    # -------------------------------------------------------------------------
    #
    #                                   DUNDER METHODS
    #
    # -------------------------------------------------------------------------

    def __len__(self):
        """returns the number of inventory currently in the inventory."""
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
    #  'inventory' attribute.  The Caller must then add those inventory to the
    #  design.
    # -------------------------------------------------------------------------

    async def __aenter__(self):
        """returns the instance when entering the context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """create the inventory when exiting the context manager."""
        self.build_inventory()
