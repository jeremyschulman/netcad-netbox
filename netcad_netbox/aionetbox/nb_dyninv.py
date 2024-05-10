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

    async def fetch_device_by_name(self, name: str) -> Device:
        """
        This function is used to retrieve a device record by name.  The caller must provide
        the device name.  The resulting device record is added to the internally managed list
        of NetBox devices.

        Parameters
        ----------
        name
            The name of the device to retrieve.

        Returns
        -------
        The device record.
        """
        async with NetboxClient() as api:
            res = await api.op.dcim_devices_list(params=dict(name=name))
            res.raise_for_status()
            if not (body := res.json()["results"]):
                raise ValueError(f"Device {name} not found")

            rec = body[0]
            self._netbox_devices[rec["name"]] = rec

        return rec

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

    @property
    def inventory(self) -> Sequence[Device]:
        """
        This property is used to return the list of Device instances that have been
        retrieved from NetBox.

        Returns
        -------
        The list of Device instances.
        """
        return []
