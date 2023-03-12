# NetBox integration with NetCAD/CAM system

---
This repository contains the integration package for NetBox.  At this time,
NetBox 3.3+ was tested.  This is a work-in-progress.
---

The following design elements are syndicated to NetBox:
 * device properties such as role, deviec-type, site, primary IP
 * device interfaces
 * device lags, associations to interfaces
 * device interface IP addresss
 * device cabling

# Installation

```shell
poetry install netcad-netbox
```

# NetCAD configuration

Add the following to your `netcad.toml` configuration file:

```toml
[[netcad.plugins]]
    name = 'NetBox'
    package = "netcad_netbox"

    config.netbox_url = "$NETBOX_ADDR"
    config.netbox_token = "$NETBOX_TOKEN"
    config.timeout = 60
```

The following enviornment variables can be used in place of the configuration:

   * NETBOX_ADDR - the URL to your NetBox server in the form `https://<your-url>`
   * NETBOX_TOKEN - the NetBox API token

