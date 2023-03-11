import importlib.metadata as importlib_metadata
from .netbox_plugin_init import plugin_init

plugin_version = importlib_metadata.version("netcad-netbox")
plugin_description = "NetBox device integration"
