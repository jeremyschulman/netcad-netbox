# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Sequence, Callable, Type, Coroutine
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

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["NetBoxDynamicInventory"]

# -----------------------------------------------------------------------------
#
#                             CODE BEGINS
#
# -----------------------------------------------------------------------------

# For the 'custom_fetch' method, we define a type hint that yield lists of
# NetBox device records (dict).  That function is an async generator that
# returns a list of dict.  The custom fetching function takes as an argument an
# instance of the NetBoxClient API so that it can fetch records from NetBox.

CustomFetchFuncType = Callable[
    ["NetBoxDynamicInventory", NetboxClient, ...],  # function signature
    Coroutine[None, None, None],  # is a coroutine that does not yield,send,return
]


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

        # Uses the NetBox device record "id" field (int) as the key into the
        # dictionary so that we have a unique set of device recoreds.  This
        # handles the case where the Caller might have made multiple fetch
        # calls that results in duplicate device records.

        self.netbox_devices: dict[int, dict] = dict()

        # The resulting set of Device instances (partial mode) that are created
        # from the NetBox records.  The inventory is stored as a dictionary
        # where the keys are the device instances and the values are the NetBox
        # device record "id" field.  This mechanism is defined so that the
        # Caller can "back reference" to the NetBox device record if needed.

        self.inventory: dict[DeviceNonExclusive, int] = dict()

        # The 'device_types' dictionary is used to map the NetBox device type
        # values to the Device class that will be created.

        self.device_types: dict[str, type] = dict()

    # -------------------------------------------------------------------------
    #
    #                                   Private Methods
    #
    # -------------------------------------------------------------------------

    def _get_device_type(self, device_type: str) -> Type[DeviceNonExclusive]:
        """
        This function is used to retrieve the Device class based on the NetBox
        device record device_type slug value.  The Device class is created if
        it does not already exist in the 'device_types' dictionary.

        Parameters
        ----------
        device_type:
            The NetBox device record device_type slug value.

        Returns
        -------
        The Device class that is associated with the device_type value.
        """

        if device_type not in self.device_types:
            self.device_types[device_type] = type(
                device_type,
                (DeviceNonExclusive,),
                dict(device_type=device_type.upper()),
            )

        return self.device_types[device_type]

    # -------------------------------------------------------------------------
    #
    #                                   Public Methods
    #
    # -------------------------------------------------------------------------

    async def fetch_devices(self, **params) -> Sequence[dict]:
        """
        This function is used to retrieve a list of device records via the
        NetBox API GET /dcim/devices.  The Caller must provide the API
        parameters to filter the GET request, for example the "site" value. The
        resulting device records are added to the inventory.

        Parameters
        ----------
        params
            The NetBox /dcim/device query parameters.

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
        This function is used to call a custom fetching function that will
        retrieve the NetBox device records.  The Caller must provide the
        function any additional arguments that are needed for the function to
        execute.

        The fetching_func must yield the NetBox device records as they are
        retrieved. This enables the Caller to process the records as they are
        retrieved, rather than waiting for all records to be collected into a
        list.

        The fetching_func will be pass a NetBoxClient instance as the first
        argument. The remaining *args and **kwargs are passed as provided by
        the Caller.  For example:

        await dyninv.custom_fetch(fetch_service_inventory, service_name=service)

        async def fetch_service_inventory(api: NetboxClient, service_name: str):
            ...


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
            await fetching_func(self, api, *args, **kwargs)

    def api(self, **kwargs) -> NetboxClient:  # noqa
        """
        This helper function is used to return an API client instance to NetBox
        so that the Caller can make direct calls as needed to retrieve device
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

        for nb_dev_rec in records:
            # if the device record already exists in the inventory, skip it.
            if (nb_id := nb_dev_rec["id"]) in self.netbox_devices:
                continue

            # create the Device instance based on the dynamically created
            # device_type associated with the device_type slug value.

            self.netbox_devices[nb_id] = nb_dev_rec
            device_type = self._get_device_type(nb_dev_rec["device_type"]["slug"])
            device = device_type(
                name=nb_dev_rec["name"], os_name=nb_dev_rec["platform"]["slug"]
            )

            # create the primary IP interface so that the device can be reached
            # using NetCAM.

            pri_intf = device.interfaces["primary_interface"]
            pri_intf.profile = InterfaceL3(
                if_ipaddr=IPv4Interface(nb_dev_rec["primary_ip"]["address"])
            )
            device.set_primary_ip_interface(pri_intf)

            self.inventory[device] = nb_id

    # -------------------------------------------------------------------------
    #
    #                                   DUNDER METHODS
    #
    # -------------------------------------------------------------------------

    def __len__(self):
        """returns the number of netbox currently in the inventory."""
        return len(self.inventory)
