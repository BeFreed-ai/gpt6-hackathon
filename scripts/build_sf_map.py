"""Build the compact playable map offline from the official reference cache.

Run with --source .data/maps/soma-mission-streets.json to reimport the cache,
or without arguments to reproducibly rebuild the checked-in selected geometry.
No network access, credentials, or third-party geometry packages are needed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/sf_map.json"
STREETS = {
    "MARKET ST",
    "MISSION ST",
    "VALENCIA ST",
    "DOLORES ST",
    "GUERRERO ST",
    "SOUTH VAN NESS AVE",
    "FOLSOM ST",
    "HARRISON ST",
    "HOWARD ST",
    "BRYANT ST",
    "BRANNAN ST",
    "KING ST",
    "DIVISION ST",
    "13TH ST",
    "14TH ST",
    "15TH ST",
    "16TH ST",
    "17TH ST",
    "18TH ST",
    "19TH ST",
    "20TH ST",
    "21ST ST",
    "22ND ST",
    "23RD ST",
    "24TH ST",
    "03RD ST",
    "04TH ST",
    "05TH ST",
    "06TH ST",
    "07TH ST",
    "08TH ST",
    "09TH ST",
    "10TH ST",
    "11TH ST",
    "POTRERO AVE",
    "CHURCH ST",
    "DUBOCE AVE",
    "ALAMEDA ST",
    "BERRY ST",
    "BERRY EXTENSION ST",
    "CHANNEL ST",
    "CHINA BASIN ST",
    "GENE FRIEND WAY",
    "MISSION BAY BLVD NORTH",
    "MISSION BAY BLVD SOUTH",
    "MISSION BAY CIR",
    "MISSION BAY DR",
    "NELSON RISING LN",
    "OWENS ST",
    "MARIPOSA ST",
    "ILLINOIS ST",
    "TERRY A FRANCOIS BLVD",
}
BOUNDS = [-122.431, 37.7505, -122.381, 37.787]


def build(source: list[dict], provenance: dict) -> dict:
    segments = []
    for row in source:
        if row["streetname"] not in STREETS or row.get("layer") != "STREETS":
            continue
        geometry = row["line"]
        lines = (
            [geometry["coordinates"]]
            if geometry["type"] == "LineString"
            else geometry["coordinates"]
        )
        for index, points in enumerate(lines):
            segments.append(
                {
                    "id": row.get("_segment_id", f"{row['cnn']}:{index}"),
                    "name": row["streetname"],
                    "coordinates": [[round(p[0], 7), round(p[1], 7)] for p in points],
                }
            )
    segments.sort(key=lambda row: row["id"])
    return {
        "schema_version": 1,
        "id": "sf-soma-mission-bay-v2",
        "bounds": BOUNDS,
        "source": provenance,
        "projection": {
            "type": "north_up_affine",
            "world_width": 1400,
            "world_height": 820,
            "padding": 40,
            "note": "Longitude and latitude independently fit the play area; "
            "east-west distances are exaggerated. Not a scale map.",
        },
        "limitations": [
            "Selected official street centerlines, rounded to seven decimal places; "
            "omitted alleys, private roads, freeways, parks and paper streets.",
            "Road widths and tile connections are gameplay approximations, "
            "not surveyed rights-of-way or pedestrian routing.",
            "Neighborhood labels are approximate locations, not official neighborhood boundaries.",
            "All simulated buildings and entrances are synthetic street-adjacent placements, "
            "not actual parcels or verified addresses.",
        ],
        "segments": segments,
        "landmarks": [
            {"name": "Dolores Park", "coordinates": [-122.4269, 37.7597], "kind": "park"},
            {"name": "Yerba Buena Gardens", "coordinates": [-122.4023, 37.7849], "kind": "park"},
            {
                "name": "Victoria Manalo Draves Park",
                "coordinates": [-122.4067, 37.7771],
                "kind": "park",
            },
            {"name": "16th / Mission BART", "coordinates": [-122.4197, 37.7650], "kind": "transit"},
            {"name": "24th / Mission BART", "coordinates": [-122.4185, 37.7523], "kind": "transit"},
            {"name": "4th / King Caltrain", "coordinates": [-122.3959, 37.7764], "kind": "transit"},
            {"name": "Mission Bay", "coordinates": [-122.389, 37.770], "kind": "district"},
        ],
        "landmark_status": "Approximate reference pins copied from scripts/draw_sf_reference.py; "
        "not surveyed footprints or transit routes.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.source:
        print(f"Reading cached official centerlines: {args.source}", flush=True)
        raw = args.source.read_bytes()
        source = json.loads(raw)
        provenance = {
            "publisher": "City and County of San Francisco / DataSF",
            "dataset": "Streets - Active and Retired",
            "dataset_id": "3psu-pn9h",
            "url": "https://data.sfgov.org/Geographic-Locations-and-Boundaries/Streets-Active-and-Retired/3psu-pn9h",
            "retrieved": "2026-09-08",
            "data_as_of": max(r["data_as_of"] for r in source),
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "input_records": len(source),
            "query": "active=true; intersects bounding box; ordered by cnn; limit=5000",
            "reference_generator": "scripts/draw_sf_reference.py",
        }
    else:
        print("Rebuilding from checked-in source geometry (offline).", flush=True)
        previous = json.loads(OUTPUT.read_text())
        provenance = previous["source"]
        source = [
            {
                "cnn": row["id"].split(":")[0],
                "_segment_id": row["id"],
                "streetname": row["name"],
                "layer": "STREETS",
                "line": {"type": "LineString", "coordinates": row["coordinates"]},
            }
            for row in previous["segments"]
        ]
    result = build(source, provenance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":"), ensure_ascii=False) + "\n")
    print(f"Saved {len(result['segments'])} selected segments to {args.output}", flush=True)


if __name__ == "__main__":
    main()
