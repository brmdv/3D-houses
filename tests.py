from unittest import TestCase

import requests
from lidar import Address, HeightDataImage, get_zone

##############
# UNIT TESTS #
##############
class TestAddressLookups(TestCase):
    """Some unit tests for retrieving addresses.

    The addresses are randomly picked for privacy reasons.
    """

    def setUp(self):
        self.random_address = Address(street="Grote Markt", number=5, zipcode=2000)

    def test_create_address(self):
        """Create addresses with missing data to check if they're completed correctly."""
        with self.subTest("No municipity"):
            self.assertEqual(str(self.random_address), "Grote Markt 5, 2000 Antwerpen")
        with self.subTest("No zipcode"):
            self.assertEqual(
                str(Address(street="Bist", number=2, municipality="Antwerpen")),
                "Bist 2, 2610 Antwerpen",
            )
        # with self.subTest("Multiple possibilities"):
        #     # There is more than one Statiestraat in Antwerpen, so it should warn the user about this
        #     self.assertRaises(
        #         RuntimeWarning,
        #         Address,
        #         "Statiestraat",
        #         "10",
        #         "Antwerpen",
        #     )

    def test_lookup_address(self):
        """Lookup a vague adresses using the Geopunt API."""
        self.assertEqual(
            str(Address.from_search("Bist 2 wilrijk")), "Bist 2, 2610 Antwerpen"
        )

    def test_building_shape(self):
        """Test if a polygon for the buildings is found."""
        self.assertFalse(all(self.random_address.get_building_shape().is_empty))

    def test_kaartblad_selection(self):
        """Test whether for a given coordinate, the correct zone is selected."""
        self.assertEqual(get_zone(*self.random_address.lambert), 15)


class TestTiffHandling(TestCase):
    """Tests for the GeoTiff class."""

    def setUp(self):
        self.dsm_file = HeightDataImage(15, "DSM", resolution="5m")

    def test_link(self):
        """Check if correct download link is generated."""
        self.assertEqual(
            self.dsm_file.get_download_link(),
            "https://downloadagiv.blob.core.windows.net/dhm-vlaanderen-ii-dsm-raster-5m/DHMVIIDSMRAS5m_k15.zip",
        )

    def test_link_exists(self):
        """Check if generated download link can be accessed."""
        response = requests.head(self.dsm_file.get_download_link())
        self.assertLess(response.status_code, 400)

    def test_complement_creation(self):
        """Test whether correct DTM equivalent is created."""
        dtm_file = self.dsm_file.complement()
        self.assertEqual(dtm_file.data_type, "DTM")