"""All the necessary code for retrieving addresses in Flanders."""

from pathlib import Path
from unittest import TestCase

import geopandas
import requests
from shapely.geometry import Point, Polygon


class Address:
    """Class for to look up an adress in Flanders, Belgium."""

    def __init__(
        self,
        street: str,
        number: str,
        municipality: str = None,
        zipcode: int = None,
    ):
        """Create a new Address instance. Missing data will be filled in using the
        basisregisters.vlaanderen.be API.

        :param street: Street name
        :param number: house number
        :param zipcode: Zipcode (postal code)
        :param municipality: municipality (city)
        """
        self.zipcode = zipcode
        self.streetname = street
        self.housenumber = number
        self.municipality = municipality

        # Find adress with API and supplement missing data
        params = {
            name: self.__dict__[key]
            for key, name in [
                ("streetname", "straatnaam"),
                ("zipcode", "postcode"),
                ("housenumber", "huisnummer"),
                ("municipality", "gemeentenaam"),
            ]
            if key in self.__dict__
        }
        result = requests.get(
            "https://api.basisregisters.vlaanderen.be/v1/adresmatch",
            params=params,
        )
        if result.ok:
            # select result with best score
            best_result = result.json()["adresMatches"][0]
            if len(best_result["adresseerbareObjecten"]) == 0:
                # A result was returned, but no concrete address
                raise RuntimeError(
                    "API returned a result, but no concrete address. Check whether you specified your request correctly."
                )
            self.basisregisters_id = best_result["identificator"]["objectId"]
            # Warn user if more than one option
            if len(result.json()["adresMatches"]) > 1:
                raise RuntimeWarning(
                    f"More than one possible address found. Selected best match with a score of {result.json()['adresMatches'][0]['score']}."
                )
        else:
            raise RuntimeError(
                f"API error status {result.status_code}: {result.json()['title']}"
            )

        # fill in missing data
        if not self.municipality:
            self.municipality = best_result["gemeente"]["gemeentenaam"][
                "geografischeNaam"
            ]["spelling"]
        if not self.zipcode:
            self.zipcode = best_result["postinfo"]["objectId"]
        if not self.streetname:
            self.streetname = best_result["straatnaam"]["geografischeNaam"]["spelling"]
        if not self.housenumber:
            self.housenumber = best_result["huisnummer"]

        # get position
        self.lambert = best_result["adresPositie"]["point"]["coordinates"]

        # get building units
        self.building_units = [
            ob["objectId"]
            for ob in best_result["adresseerbareObjecten"]
            if ob["objectType"] == "gebouweenheid"
        ]

    @classmethod
    def from_search(cls, q: str):
        """Create a new adress from a general search string.

        This uses the Geopunt Suggestion API to select an address and collect its data.
        The first match is automatically selected, so be aware to provide sufficient
        detail to avoid ambiguity.

        :param q: The search query.
        """
        result = requests.get(
            "https://loc.geopunt.be/geolocation/location", params={"q": q}
        )
        if result.ok:
            res = result.json()["LocationResult"][0]
            addr = cls(
                zipcode=res["Zipcode"],
                municipality=res["Municipality"],
                street=res["Thoroughfarename"],
                number=res["Housenumber"],
            )
            # Check if Address is formatted the same
            assert str(addr) == res["FormattedAddress"]

            # save Id for this API in case it is needed in the future
            addr.geopunt_id = res["ID"]

            # Save Lambert coordinates
            addr.lambert = (
                res["Location"]["X_Lambert72"],
                res["Location"]["Y_Lambert72"],
            )
            return addr
        else:
            raise RuntimeError(f"No address found, responde code {result.status_code}.")

    def __str__(self) -> str:
        """Get adress in standard Belgian format ‘<Street name> <num>, <zipcode> <Place>’."""
        return (
            f"{self.streetname} {self.housenumber}, {self.zipcode} {self.municipality}"
        )

    def get_building_shape(self) -> geopandas.GeoSeries:
        """Retrieves the polygon shapes of the outline of the buildings on this address
        with a series of subsequent API requests. A GeoSeries is returned containing all
        polygons.

        Most addresses point to a single building, but to account for some edges cases,
        we still collect all building units. To avoid to much API requests this method
        saves the result in the attribute building_polygons."""

        # check if already present
        if hasattr(self.building_polygons):
            return self.building_polygons

        # First, get building ids.
        building_ids = set()  # using a set avoids double values
        for bu in self.building_units:
            result = requests.get(
                f"https://api.basisregisters.vlaanderen.be/v1/gebouweenheden/{bu}"
            )
            if result.ok:
                building_ids.add(result.json()["gebouw"]["objectId"])
            else:
                raise RuntimeError(
                    f"Problem retrieving building unit {bu}: status {result.status_code}"
                )
        # get the polygon shapes from the building ids
        building_polygons = []
        for bid in building_ids:
            result = requests.get(
                f"https://api.basisregisters.vlaanderen.be/v1/gebouwen/{bid}"
            )
            if result.ok:
                building_polygons.append(
                    Polygon(
                        result.json()["geometriePolygoon"]["polygon"]["coordinates"][0]
                    )
                )
            else:
                raise RuntimeError(
                    f"Problem retrieving building unit {bid}: status {result.status_code}"
                )
        # convert to GeoSeries with correct crs
        self.building_polygons = geopandas.GeoSeries(
            building_polygons, crs="EPSG:31370"
        )
        return self.building_polygons


def get_zone(x: float, y: float) -> int:
    """Get the number of the zone (Kaartbladversnijding) in which a given geographic point.

    :param x: x coordinate of the point (Lambert 72)
    :param y: y coordinate of the point (Lambert 72)
    """
    # Load Shapefile with the zones
    kbv = geopandas.read_file(
        "zip://./general_data/Kaartbladversnijdingen.zip!Kblo.shp"
    )
    # Put point into GeoSeries with Lambert72 coordinates
    coord_series = geopandas.GeoSeries(Point(x, y), crs=kbv.crs)
    # Find zone with GeoPandes .contains
    zone = kbv[kbv.geometry.contains(coord_series[0])]
    # The zone number is the first column, and there is probably one result
    return zone.iloc[0, 0]


class HeightDataImage:
    """Wrapper for GeoTIFFs of the Digital Height Model Flanders (DHMV) that are used in this project. """

    def __init__(
        self,
        zone: int,
        data_type: str,
        resolution="1m",
        dhmv_version="II",
        path="./tiff_data",
    ):
        """Define a GeoTIFF file, by specifying settings.

        :param zone: The number of the Kaartbladversnijdingszone.
        :param data_type: DSM or DTM
        :param resolution: pixel resolution of the image, defaults to "1m"
        :param dhmv_version: version of the DIgitaal Hoogtemodel Vlaanderen, defaults to "II"
        :param path: Base path were all the TIFFs are stored, defaults to "./tiff_data"
        """
        self.zone = zone
        if data_type.upper() not in ["DTM", "DSM"]:
            raise RuntimeWarning("Provided data_type is not DTM or DSM.")
        self.data_type = data_type.upper()
        self.res = resolution
        self.dhmv_version = dhmv_version
        self.base_path = Path(path)

    def filename(self, extension=".tif") -> str:
        """Generate base file name that is used for the data files.

        :param extension: File extension, defaults to ".tif"
        """
        return f"DHMV{self.dhmv_version}{self.data_type}RAS{self.res}_k{self.zone}{extension}"

    def download_link(self) -> str:
        """Get the link to download this dataset."""
        return f"https://downloadagiv.blob.core.windows.net/dhm-vlaanderen-{self.dhmv_version.lower()}-{self.data_type.lower()}-raster-{self.res}/{self.filename('.zip')}"

    def is_downloaded(self) -> bool:
        """Check if TIFF is downloaded, i.e. path exists."""
        return (self.base_path / self.filename()).exists()

    def complement(self):
        """"""
        if self.data_type == "DSM":
            new_type = "DTM"
        elif self.data_type == "DTM":
            new_type = "DSM"
        else:
            raise RuntimeError("Can only flip DTM ⇋ DSM.")
        return HeightDataImage(
            zone=self.zone,
            data_type=new_type,
            resolution=self.res,
            dhmv_version=self.dhmv_version,
            path=str(self.base_path),
        )

    def download(self):
        """Download the file and extract the TIFF."""
        # TODO Download FILE
        # TODO Extract ZIP

        pass


##############
# UNIT TESTS #
##############
class TestAddressLookups(TestCase):
    """Some unit tests for retrieving addresses.

    The addresses are randomly picked for privacy reasons.
    """

    def test_create_address(self):
        """Create addresses with missing data to check if they're completed correctly."""
        with self.subTest("No municipity"):
            self.assertEqual(
                str(Address(street="Grote Markt", number=5, zipcode=2000)),
                "Grote Markt 5, 2000 Antwerpen",
            )
        with self.subTest("No zipcode"):
            self.assertEqual(
                str(Address(street="Bist", number=2, municipality="Antwerpen")),
                "Bist 2, 2610 Antwerpen",
            )
        with self.subTest("Multiple possibilities"):
            # There is more than one Statiestraat in Antwerpen, so it should warn the user about this
            self.assertRaises(
                RuntimeWarning,
                Address,
                "Statiestraat",
                "10",
                "Antwerpen",
            )

    def test_lookup_address(self):
        """Lookup a vague adresses using the Geopunt API."""
        self.assertEqual(
            str(Address.from_search("Bist 2 wilrijk")), "Bist 2, 2610 Antwerpen"
        )

    def test_kaartblad_selection(self):
        """Test whether for a given coordinate, the correct zone is selected."""
        addr = Address(
            street="Mechelsestraat",
            number="77",
            municipality="Londerzeel",
        )
        self.assertEqual(get_zone(*addr.lambert), 23)


class TestTiffHandling(TestCase):
    """Tests for the GeoTiff class."""

    def setUp(self):
        self.dsm_file = HeightDataImage(15, "DSM", resolution="5m")

    def test_link(self):
        """Check if correct download link is generated."""
        self.assertEqual(
            self.dsm_file.download_link(),
            "https://downloadagiv.blob.core.windows.net/dhm-vlaanderen-ii-dsm-raster-5m/DHMVIIDSMRAS5m_k15.zip",
        )

    def test_link_exists(self):
        """Check if generated download link can be accessed."""
        response = requests.head(self.dsm_file.download_link())
        self.assertLess(response.status_code, 400)

    def test_complement_creation(self):
        """Test whether correct DTM equivalent is created."""
        dtm_file = self.dsm_file.complement()
        self.assertEqual(dtm_file.data_type, "DTM")
