"""Place search for autocomplete and final lookup. TomTom Search when a key is configured,
otherwise Photon (komoot), which is built for search-as-you-type (Nominatim forbids it)."""

import hashlib
import logging
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote

import httpx
from django.conf import settings
from django.core.cache import cache

from .http import ProviderError, get_json

logger = logging.getLogger(__name__)

# Geographic centre of the contiguous US: results are biased here, not filtered.
US_BIAS = (39.83, -98.58)
MAX_RESULTS = 6
CACHE_TTL_S = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class Place:
    label: str
    lat: float
    lon: float


def _us_first(places: list[tuple[str, Place]]) -> list[Place]:
    """Stable sort that keeps the provider's relevance order but lists US matches first."""
    ordered = sorted(places, key=lambda item: item[0] != "US")
    seen: set[str] = set()
    unique = []
    for _, place in ordered:
        if place.label not in seen:
            seen.add(place.label)
            unique.append(place)
    return unique[:MAX_RESULTS]


# --- Photon ----------------------------------------------------------------------------------


def photon_label(props: dict[str, Any]) -> str:
    parts = [props.get("name")]
    if props.get("housenumber") and props.get("street"):
        parts = [f"{props['housenumber']} {props['street']}"]
    elif props.get("street") and props.get("street") != props.get("name"):
        parts.append(props["street"])
    for key in ("city", "state"):
        value = props.get(key)
        if value and value not in parts:
            parts.append(value)
    if props.get("countrycode") and props["countrycode"] != "US":
        parts.append(props["countrycode"])
    return ", ".join(p for p in parts if p)


async def search_photon(client: httpx.AsyncClient, query: str) -> list[Place]:
    params = {"q": query, "limit": 10, "lang": "en", "lat": US_BIAS[0], "lon": US_BIAS[1]}
    data = await get_json(client, "photon", "https://photon.komoot.io/api/", params)
    places = []
    for feature in data.get("features", []):
        props, coords = (
            feature.get("properties", {}),
            feature.get("geometry", {}).get("coordinates"),
        )
        if not coords or (not props.get("name") and not props.get("street")):
            continue
        place = Place(label=photon_label(props), lat=float(coords[1]), lon=float(coords[0]))
        places.append((props.get("countrycode", "").upper(), place))
    return _us_first(places)


# --- TomTom ----------------------------------------------------------------------------------


async def search_tomtom(client: httpx.AsyncClient, query: str, api_key: str) -> list[Place]:
    url = f"https://api.tomtom.com/search/2/search/{quote(query, safe='')}.json"
    params = {
        "key": api_key,
        "typeahead": "true",
        "limit": 10,
        "lat": US_BIAS[0],
        "lon": US_BIAS[1],
        "idxSet": "Geo,PAD,Addr,Str,POI",
    }
    data = await get_json(client, "tomtom", url, params)
    places = []
    for result in data.get("results", []):
        address, position = result.get("address", {}), result.get("position")
        label = address.get("freeformAddress")
        if not position or not label:
            continue
        if result.get("type") == "POI" and result.get("poi", {}).get("name"):
            label = f"{result['poi']['name']}, {label}"
        country = address.get("countryCode", "")
        if country and country != "US":
            label = f"{label}, {country}"
        places.append((country, Place(label=label, lat=position["lat"], lon=position["lon"])))
    return _us_first(places)


# --- Entry point -----------------------------------------------------------------------------


async def geocode(client: httpx.AsyncClient, query: str) -> list[Place]:
    normalized = " ".join(query.lower().split())
    key = "geo:" + hashlib.sha1(normalized.encode()).hexdigest()
    cached = await cache.aget(key)
    if cached is not None:
        return [Place(**p) for p in cached]

    places: list[Place] | None = None
    if settings.TOMTOM_API_KEY:
        try:
            places = await search_tomtom(client, normalized, settings.TOMTOM_API_KEY)
        except ProviderError as exc:
            logger.warning("TomTom search failed, falling back to Photon: %s", exc)
    if places is None:
        places = await search_photon(client, normalized)

    await cache.aset(key, [asdict(p) for p in places], CACHE_TTL_S)
    return places
