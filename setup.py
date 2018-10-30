from distutils.core import setup

from os.path import join

scripts = [ join( 'bin', filename ) for filename in [ 'wtemulatorpoc5' ] ]

setup(
    # Application name:
    name="WirelessTransportEmulatorPoc5",

    # Version number (initial):
    version="0.1.1",

    # Application author details:
    author="Alex Stancu",
    author_email="alex.stancu@radio.pub.ro",

    # Packages
    packages=["wireless_emulator_poc5"],

    # Include additional files into the package
    #include_package_data=True,

    # Details
    url="https://github.com/Melacon/WTE_Poc5",

    #
    license="LICENSE",
    description="Wireless Transport topology emulator with OpenYuma NETCONF server, based on ONF TR-532, used for the 5th ONF WT SDN PoC",

    # long_description=open("README.txt").read(),

    # Dependent packages (distributions)
    #install_requires=[],
    scripts=scripts,
)