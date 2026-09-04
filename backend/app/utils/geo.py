import math
from typing import Optional, Tuple


def haversine_distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great-circle distance between two points on the Earth's surface
    in kilometers using the Haversine formula.
    """
    earth_radius_km = 6371.0

    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance = earth_radius_km * c

    return round(distance, 2)


def clamp(val: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max bounds."""
    return max(min_val, min(max_val, val))


def round_safe(val: Optional[float], digits: int = 2) -> Optional[float]:
    """Safely round a number, returning None if None or invalid."""
    if val is None or not math.isfinite(val):
        return None
    return round(val, digits)
