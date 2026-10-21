"""Locate a frozen quote for editing without geocoding or remeasuring it."""
import math

def measurement_bounds(payload):
    snap = payload.get('quote') or {}
    points = []
    collections = [snap.get('areaPoints') or [], snap.get('linearPoints') or []]
    collections += [a.get('points') or [] for a in snap.get('commercialAreas') or []]
    collections += [a.get('points') or [] for a in snap.get('manualPlanes') or []]
    collections += [a.get('outline') or [] for a in snap.get('structures') or []]
    for ring in collections:
        for point in ring:
            try:
                lat, lng = (point['lat'], point['lng']) if isinstance(point, dict) else point[:2]
                lat, lng = float(lat), float(lng)
                if math.isfinite(lat) and math.isfinite(lng) and -85 <= lat <= 85 and -180 <= lng <= 180:
                    points.append((lat, lng))
            except (KeyError, TypeError, ValueError):
                pass
    if not points:
        raise ValueError('This estimate has no saved measurement coordinates to edit.')
    south, north = min(p[0] for p in points), max(p[0] for p in points)
    west, east = min(p[1] for p in points), max(p[1] for p in points)
    return [[south, west], [north, east]]
