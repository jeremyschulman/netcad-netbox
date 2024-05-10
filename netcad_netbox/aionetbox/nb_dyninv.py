# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Sequence

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.device import Device

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
        self._netbox_devices = dict()

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

    async def fetch_devices(self, **params) -> Sequence[Device]:
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

        for rec in records:
            self._netbox_devices[rec["name"]] = rec

        return records

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
        self._netbox_devices.update({dev["name"]: dev for dev in devices})
        return devices

    def build_inventory(self) -> Sequence[Device]:
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
                (Device,),
                dict(os_name=os_name, device_type=device_type.upper()),
            )
            # build the unique set of OS+Device-Type combinations so that we
            # can dynamically build the classes for each of these.
            for os_name, device_type in set(
                (dev["platform"]["slug"], dev["device_type"]["slug"])
                for dev in self._netbox_devices.values()
            )
        }

        # Using the built type mapping, return a list of the Device instances
        # for each of the NetBox device records.

        return [
            dev_type_map[(dev["platform"]["slug"], dev["device_type"]["slug"])](
                name=dev["name"]
            )
            for dev in self._netbox_devices.values()
        ]

    # -------------------------------------------------------------------------
    #
    #                                   DUNDER METHODS
    #
    # -------------------------------------------------------------------------

    def __len__(self):
        """returns the number of devices currently in the inventory."""
        return len(self._netbox_devices)
