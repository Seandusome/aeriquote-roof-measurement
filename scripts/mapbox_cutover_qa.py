"""Disposable QA policy for a Mapbox cutover. This is not loaded by AeriQuote."""
from dataclasses import dataclass
from math import isfinite
from urllib.parse import urlencode


@dataclass(frozen=True)
class ProviderSettings:
    address: str = "google"
    aerial: str = "google"
    pdf_imagery: str = "current"

    def __post_init__(self):
        if self.address not in {"google", "mapbox"}:
            raise ValueError("Unknown address provider")
        if self.aerial not in {"google", "mapbox"}:
            raise ValueError("Unknown aerial provider")
        if self.pdf_imagery not in {"current", "none"}:
            raise ValueError("Mapbox PDF imagery is disabled pending rights confirmation")
        if self.aerial == "mapbox" and self.pdf_imagery != "none":
            raise ValueError("Use image-free PDFs for the Mapbox QA configuration")
        if self.address == "google" and self.aerial == "mapbox":
            raise ValueError("Google address content must not be assumed cleared for Mapbox display")


@dataclass(frozen=True)
class AddressCandidate:
    label: str
    longitude: float
    latitude: float
    warnings: tuple

    @classmethod
    def from_mapbox(cls, feature):
        props = feature["properties"]
        longitude, latitude = feature["geometry"]["coordinates"]
        if not (isfinite(longitude) and isfinite(latitude)
                and abs(longitude) <= 180 and abs(latitude) <= 85.05112878):
            raise ValueError("Invalid map pin")
        label = props["full_address"]
        match = props.get("match_code", {})
        warnings = []
        if props.get("feature_type") != "address":
            warnings.append("Result is not a street address")
        if match.get("street") != "matched":
            warnings.append("Street differs from the search")
        if match.get("address_number") != "matched":
            warnings.append("House number was not matched")
        if match.get("confidence") not in {"exact", "high"}:
            warnings.append("Address confidence is uncertain")
        if props.get("coordinates", {}).get("accuracy") != "rooftop":
            warnings.append("Pin is not a rooftop result")
        return cls(label, longitude, latitude, tuple(warnings))

    def tracing_pin(self, confirmed_candidate):
        if confirmed_candidate != self:
            raise ValueError("Confirm this address and pin before tracing")
        return self.latitude, self.longitude


def satellite_url(candidate, confirmed_candidate, token, zoom=19):
    """Server-side QA request builder. Do not log or return its URL to clients."""
    lat, lon = candidate.tracing_pin(confirmed_candidate)
    if not token or not 15 <= zoom <= 20:
        raise ValueError("A QA token and supported zoom are required")
    return (
        "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
        f"{lon},{lat},{zoom},0,0/640x640@2x?"
        + urlencode({"access_token": token, "logo": "true", "attribution": "true"})
    )
