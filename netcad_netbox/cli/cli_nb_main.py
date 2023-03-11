import click
from netcad.cli import cli as netcad_cli


@netcad_cli.group("netbox")
def clig_netbox_main():
    """
    NetBox integration commands ...
    """
    pass
