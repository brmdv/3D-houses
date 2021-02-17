import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import rasterio
import re
import os.path

matplotlib.use("WebAgg")


class DHMVFile:
    """This is a class to encapsulate a GeoTIFF file provided by AGIV. It """

    def __init__(self, filename):
        """TODO"""

        self.file_name = os.path.basename(filename)
        self.file_path = os.path.abspath(filename)
        if not os.path.exists(self.file_path):
            raise FileNotFoundError
        match_filename = re.match(
            r"DHMV(?P<version>[IVX]*?)(?P<type>DTM|DSM)RAS(?P<res>[0-9]+)m_k(?P<areacode>[0-9]{2}).tif",
            self.file_name,
        )
        if match_filename is None:
            raise RuntimeError(
                f"Filename ‘{self.file_name}’ does not comply with the standardized format."
            )
        self.dhmv_version = match_filename.group("version")
        self.data_type = match_filename.group("type")
        self.resolution = int(match_filename.group("res"))
        self.area_code = int(match_filename.group("areacode"))


class Parcel:
    """A piece of land, derived from an address in Flanders."""

    def __init__(self, address):
        pass

    def plot3D(self, filename=None):
        """Render a 3D plot of the parcel. Default Matplotlib target will be used, unless filename is specified.

        :param filename: File to write plot as an image. If empty, default mpl output is used.
        """
        pass