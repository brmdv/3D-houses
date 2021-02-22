import unittest
import requests
from requests.api import request
from unittest import TestCase

from typing_extensions import runtime_checkable


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
        """Get adress in standard format ‘<Street name> <num>, <zipcode> <Place>’."""
        return (
            f"{self.streetname} {self.housenumber}, {self.zipcode} {self.municipality}"
        )


class TestAddressLookups(TestCase):
    """Some unit tests for retrieving addresses."""

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
            self.assertRaises(
                RuntimeWarning,
                Address,
                "Statiestraat",
                "10",
                "Antwerpen",
            )
