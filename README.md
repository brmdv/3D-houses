# 3D houses from LiDAR data

## About the data
The data that is used is sourced from 

* **Versnijdingen**: https://download.vlaanderen.be/Producten/Detail?id=111&title=Kaartbladversnijdingen_NGI_klassieke_reeks#
  [[https://download.vlaanderen.be/Producten/getImage/4421/

## Technical details
### Retrieving the address
In order to go further, we first need to connect a coordinate to a given address.
For Flanders, there are two public APIs that provide this service: [api.basisregisters.vlaanderen.be](https://docs.basisregisters.vlaanderen.be/docs/api-documentation.html#tag/api-documentation.html) and [loc.geopunt.be/location](https://loc.geopunt.be/).
Because the former returns more detailed results about the address, which include surrounding polygons for the building, I chose that one. 
However, the Geopunt API handles arbitrary lookup strings like “_Street name 11 City_”, so I added a function so that the user can add an address starting from a search string, using this API.

All the address-related code is in the class `Address`. 
On initialization the user specifies the address 

### Preparing the LiDAR data
### Creating a 3D plot
## How to use
