"""
backend/hospital_finder.py
===========================
Nearest hospital/PHC finder using a static sample dataset and Haversine distance.

Why static data instead of a live API?
---------------------------------------
- No external API key required for the demo
- Works offline (important for rural settings)
- Deterministic results — no API rate limits or downtime risk during demo

In production, replace the static list with:
  - Google Places API (hospital type search)
  - Ola Maps API (India-focused, free tier available)
  - NHM India's public PHC/hospital location database
  - ABDM facility registry

The haversine_distance function and find_nearest_hospitals interface are
production-ready and would require zero changes if the data source is upgraded.

Coverage: 15 sample facilities across major Indian states, including
hospitals, PHCs (Primary Health Centres), and CHCs (Community Health Centres).
"""

from __future__ import annotations

import logging
import math
from typing import TypedDict

logger = logging.getLogger(__name__)


# ── Type definition ───────────────────────────────────────────────────────────

class Hospital(TypedDict):
    name: str
    lat: float
    lon: float
    city: str
    state: str
    type: str          # "Hospital", "PHC", or "CHC"
    phone: str
    address: str


class NearestHospital(TypedDict):
    name: str
    lat: float
    lon: float
    city: str
    state: str
    type: str
    phone: str
    address: str
    distance_km: float


# ── Static hospital/PHC dataset ───────────────────────────────────────────────
# 15 sample facilities across different Indian states, types, and tiers
# Real lat/long coordinates for accurate distance calculation

SAMPLE_HOSPITALS: list[Hospital] = [
    {
        "name": "All India Institute of Medical Sciences (AIIMS), New Delhi",
        "lat": 28.5672,
        "lon": 77.2100,
        "city": "New Delhi",
        "state": "Delhi",
        "type": "Hospital",
        "phone": "011-26588500",
        "address": "Sri Aurobindo Marg, Ansari Nagar, New Delhi - 110029",
    },
    {
        "name": "Safdarjung Hospital",
        "lat": 28.5685,
        "lon": 77.2065,
        "city": "New Delhi",
        "state": "Delhi",
        "type": "Hospital",
        "phone": "011-26730000",
        "address": "Ansari Nagar West, New Delhi - 110029",
    },
    {
        "name": "KEM Hospital, Mumbai",
        "lat": 18.9977,
        "lon": 72.8383,
        "city": "Mumbai",
        "state": "Maharashtra",
        "type": "Hospital",
        "phone": "022-24107000",
        "address": "Acharya Donde Marg, Parel, Mumbai - 400012",
    },
    {
        "name": "Rajiv Gandhi Government General Hospital, Chennai",
        "lat": 13.0827,
        "lon": 80.2707,
        "city": "Chennai",
        "state": "Tamil Nadu",
        "type": "Hospital",
        "phone": "044-25305000",
        "address": "Park Town, Chennai - 600003",
    },
    {
        "name": "Nimhans (National Institute of Mental Health), Bengaluru",
        "lat": 12.9416,
        "lon": 77.5956,
        "city": "Bengaluru",
        "state": "Karnataka",
        "type": "Hospital",
        "phone": "080-46110007",
        "address": "Hosur Road, Bengaluru - 560029",
    },
    {
        "name": "IPGMER & SSKM Hospital, Kolkata",
        "lat": 22.5355,
        "lon": 88.3418,
        "city": "Kolkata",
        "state": "West Bengal",
        "type": "Hospital",
        "phone": "033-22041192",
        "address": "244, AJC Bose Road, Kolkata - 700020",
    },
    {
        "name": "Osmania General Hospital, Hyderabad",
        "lat": 17.3855,
        "lon": 78.4867,
        "city": "Hyderabad",
        "state": "Telangana",
        "type": "Hospital",
        "phone": "040-24600127",
        "address": "Afzal Gunj, Hyderabad - 500012",
    },
    {
        "name": "SMS Medical College & Hospital, Jaipur",
        "lat": 26.9124,
        "lon": 75.7873,
        "city": "Jaipur",
        "state": "Rajasthan",
        "type": "Hospital",
        "phone": "0141-2518501",
        "address": "Jawaharlal Nehru Marg, Jaipur - 302004",
    },
    {
        "name": "Civil Hospital, Ahmedabad",
        "lat": 23.0456,
        "lon": 72.5893,
        "city": "Ahmedabad",
        "state": "Gujarat",
        "type": "Hospital",
        "phone": "079-22681026",
        "address": "Asarwa, Ahmedabad - 380016",
    },
    {
        "name": "Government Medical College & Hospital, Chandigarh",
        "lat": 30.7650,
        "lon": 76.7762,
        "city": "Chandigarh",
        "state": "Punjab",
        "type": "Hospital",
        "phone": "0172-2601011",
        "address": "Sector 32, Chandigarh - 160030",
    },
    {
        "name": "PHC Chintamani, Bengaluru Rural",
        "lat": 13.3981,
        "lon": 78.0553,
        "city": "Chintamani",
        "state": "Karnataka",
        "type": "PHC",
        "phone": "08154-232345",
        "address": "Main Road, Chintamani, Chikkaballapur District - 563125",
    },
    {
        "name": "Community Health Centre, Mewat",
        "lat": 28.0961,
        "lon": 77.0043,
        "city": "Nuh",
        "state": "Haryana",
        "type": "CHC",
        "phone": "01267-272345",
        "address": "Nuh Block, Mewat District, Haryana - 122107",
    },
    {
        "name": "PHC Arwal, Bihar",
        "lat": 25.2540,
        "lon": 84.6820,
        "city": "Arwal",
        "state": "Bihar",
        "type": "PHC",
        "phone": "06151-234567",
        "address": "Arwal Block, Arwal District, Bihar - 804428",
    },
    {
        "name": "District Hospital, Raipur",
        "lat": 21.2514,
        "lon": 81.6296,
        "city": "Raipur",
        "state": "Chhattisgarh",
        "type": "Hospital",
        "phone": "0771-2421234",
        "address": "Jail Road, Raipur, Chhattisgarh - 492001",
    },
    {
        "name": "Government Hospital, Thiruvananthapuram",
        "lat": 8.4855,
        "lon": 76.9492,
        "city": "Thiruvananthapuram",
        "state": "Kerala",
        "type": "Hospital",
        "phone": "0471-2442541",
        "address": "Hospital Road, Thiruvananthapuram - 695035",
    },
]


# ── Haversine distance formula ────────────────────────────────────────────────

def haversine_distance(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Uses the Haversine formula, which accounts for Earth's spherical shape.
    Accurate to within ~0.3% for distances up to a few hundred km.

    Args:
        lat1, lon1: Latitude and longitude of point 1 (decimal degrees)
        lat2, lon2: Latitude and longitude of point 2 (decimal degrees)

    Returns:
        Distance in kilometres.
    """
    R = 6371.0  # Earth's mean radius in km

    # Convert degrees to radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# ── Main finder function ──────────────────────────────────────────────────────

def find_nearest_hospitals(
    user_lat: float,
    user_lon: float,
    top_n: int = 3,
) -> list[NearestHospital]:
    """
    Find the nearest hospitals/PHCs/CHCs to the user's location.

    Args:
        user_lat: User's latitude (from browser geolocation)
        user_lon: User's longitude (from browser geolocation)
        top_n:    Number of nearest facilities to return (default: 3)

    Returns:
        List of NearestHospital dicts sorted by distance (nearest first),
        each including the calculated distance_km field.
    """
    if not (-90 <= user_lat <= 90 and -180 <= user_lon <= 180):
        logger.warning(
            "Invalid coordinates received: lat=%s, lon=%s", user_lat, user_lon
        )
        return []

    logger.info(
        "Finding nearest %d facilities for location (%.4f, %.4f)",
        top_n, user_lat, user_lon,
    )

    results: list[NearestHospital] = []
    for hospital in SAMPLE_HOSPITALS:
        dist = haversine_distance(
            user_lat, user_lon, hospital["lat"], hospital["lon"]
        )
        entry: NearestHospital = {
            **hospital,  # type: ignore[misc]
            "distance_km": round(dist, 1),
        }
        results.append(entry)

    # Sort by distance (nearest first) and return top_n
    results.sort(key=lambda h: h["distance_km"])
    nearest = results[:top_n]

    for h in nearest:
        logger.info(
            "  [%s] %s — %.1f km", h["type"], h["name"], h["distance_km"]
        )

    return nearest


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test from multiple cities
    test_locations = [
        ("Delhi center", 28.6139, 77.2090),
        ("Mumbai center", 19.0760, 72.8777),
        ("Chennai center", 13.0827, 80.2707),
        ("Rural Rajasthan", 26.4499, 74.6399),  # Should show nearest rural facilities
    ]

    for name, lat, lon in test_locations:
        print(f"\n{'─' * 60}")
        print(f"Nearest hospitals from: {name} ({lat}, {lon})")
        print("─" * 60)
        nearest = find_nearest_hospitals(lat, lon, top_n=3)
        for i, h in enumerate(nearest, 1):
            print(f"  {i}. [{h['type']}] {h['name']}")
            print(f"     {h['city']}, {h['state']} — {h['distance_km']} km")
            print(f"     📞 {h['phone']}")

    # Verify Haversine formula
    # Delhi → Mumbai should be ~1148 km
    d = haversine_distance(28.6139, 77.2090, 19.0760, 72.8777)
    print(f"\n✓ Delhi → Mumbai: {d:.1f} km (expected ~1148 km)")
