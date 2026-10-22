# Internal coordinate order is (lat, lon). Conversion to GeoJSON's [lon, lat] happens only
# at the API boundary, so no geo function has to guess.
LatLon = tuple[float, float]
