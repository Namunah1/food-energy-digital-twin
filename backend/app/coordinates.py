"""
coordinates.py
--------------
Static lat/lon centroids for the 35 nodes in the ABM's trade network.

The scientific model (node_parameters.csv / network_weights.csv) does not
carry geographic coordinates -- it doesn't need them for the simulation.
This mapping exists purely so the frontend can place nodes on a map. It
carries no scientific weight and is never read by the simulation engine.

Regional blocs are centred on a representative point within the bloc.
"""

NODE_COORDINATES: dict[str, dict] = {
    "United States":                {"lat": 39.8,  "lon": -98.6,  "region": "Americas"},
    "China":                        {"lat": 35.0,  "lon": 103.0,  "region": "Asia"},
    "India":                        {"lat": 22.0,  "lon": 79.0,   "region": "Asia"},
    "Brazil":                       {"lat": -10.3, "lon": -53.2,  "region": "Americas"},
    "Russia":                       {"lat": 61.5,  "lon": 90.0,   "region": "Europe/Asia"},
    "Ukraine":                      {"lat": 48.4,  "lon": 31.2,   "region": "Europe"},
    "Argentina":                    {"lat": -35.0, "lon": -64.0,  "region": "Americas"},
    "Australia":                    {"lat": -25.0, "lon": 134.0,  "region": "Oceania"},
    "Canada":                       {"lat": 56.1,  "lon": -106.3, "region": "Americas"},
    "France":                       {"lat": 46.6,  "lon": 2.2,    "region": "Europe"},
    "Indonesia":                    {"lat": -0.8,  "lon": 113.9,  "region": "Asia"},
    "Vietnam":                      {"lat": 14.1,  "lon": 108.3,  "region": "Asia"},
    "Thailand":                     {"lat": 15.9,  "lon": 100.99, "region": "Asia"},
    "Egypt":                        {"lat": 26.8,  "lon": 30.8,   "region": "MENA"},
    "Nigeria":                      {"lat": 9.1,   "lon": 8.7,    "region": "Africa"},
    "Bangladesh":                   {"lat": 23.7,  "lon": 90.4,   "region": "Asia"},
    "Pakistan":                     {"lat": 30.4,  "lon": 69.3,   "region": "Asia"},
    "Germany":                      {"lat": 51.2,  "lon": 10.4,   "region": "Europe"},
    "Japan":                        {"lat": 36.2,  "lon": 138.3,  "region": "Asia"},
    "United Kingdom":               {"lat": 54.0,  "lon": -2.9,   "region": "Europe"},
    "Saudi Arabia":                 {"lat": 23.9,  "lon": 45.1,   "region": "MENA"},
    "West Africa (ECOWAS)":         {"lat": 10.0,  "lon": -3.0,   "region": "Africa"},
    "East Africa":                  {"lat": 1.5,   "lon": 38.0,   "region": "Africa"},
    "Southern Africa (SADC)":       {"lat": -22.0, "lon": 27.0,   "region": "Africa"},
    "Central Africa":               {"lat": 4.0,   "lon": 21.0,   "region": "Africa"},
    "MENA-other":                   {"lat": 31.0,  "lon": 38.0,   "region": "MENA"},
    "Central Asia":                 {"lat": 45.0,  "lon": 68.0,   "region": "Asia"},
    "South Asia-other":             {"lat": 27.0,  "lon": 84.0,   "region": "Asia"},
    "Southeast Asia-other":         {"lat": 12.0,  "lon": 121.0,  "region": "Asia"},
    "Pacific/Oceania-other":        {"lat": -17.0, "lon": 168.0,  "region": "Oceania"},
    "Caribbean & Central America":  {"lat": 15.5,  "lon": -83.0,  "region": "Americas"},
    "Andean & Southern Cone-other": {"lat": -20.0, "lon": -66.0,  "region": "Americas"},
    "Eastern Europe-other":         {"lat": 47.0,  "lon": 25.0,   "region": "Europe"},
    "EU-other":                     {"lat": 47.5,  "lon": 14.0,   "region": "Europe"},
    "Nordics":                      {"lat": 62.0,  "lon": 15.0,   "region": "Europe"},
}


def get_coordinates(node_name: str) -> dict:
    return NODE_COORDINATES.get(node_name, {"lat": 0.0, "lon": 0.0, "region": "Unknown"})
