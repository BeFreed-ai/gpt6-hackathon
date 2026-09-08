"""Render a geographic reference from San Francisco's official street centerlines."""

from __future__ import annotations

import json
import math
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
WEST, EAST, SOUTH, NORTH = -122.431, -122.393, 37.7505, 37.787
WIDTH, HEIGHT = 1080, 1290
COS_LAT = math.cos(math.radians((NORTH + SOUTH) / 2))
SCALE = min(960 / ((EAST - WEST) * COS_LAT), 1060 / (NORTH - SOUTH))
MAP_WIDTH = (EAST - WEST) * COS_LAT * SCALE
MAP_HEIGHT = (NORTH - SOUTH) * SCALE
LEFT, TOP = (WIDTH - MAP_WIDTH) / 2, 132


def project(lon: float, lat: float) -> tuple[float, float]:
    return LEFT + (lon - WEST) * COS_LAT * SCALE, TOP + (NORTH - lat) * SCALE


def main() -> None:
    ring = f"{WEST} {SOUTH},{EAST} {SOUTH},{EAST} {NORTH},{WEST} {NORTH},{WEST} {SOUTH}"
    query = urlencode(
        {
            "$where": f"active=true AND intersects(line, 'POLYGON (({ring}))')",
            "$select": "cnn,streetname,line,layer,data_as_of",
            "$order": "cnn",
            "$limit": 5000,
        }
    )
    print("Fetching official DataSF active street geometry...", flush=True)
    with urlopen(f"https://data.sfgov.org/resource/3psu-pn9h.json?{query}", timeout=45) as response:
        streets = json.load(response)
    if not streets or len(streets) >= 5000:
        raise RuntimeError("Empty or potentially truncated street response")
    cache = ROOT / ".data/maps"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "soma-mission-streets.json").write_text(json.dumps(streets), encoding="utf-8")
    print(f"Rendering {len(streets)} active street segments...", flush=True)
    parts = [
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
viewBox="0 0 {WIDTH} {HEIGHT}">
<title>San Francisco: SoMa and Mission geographic reference</title>
<desc>Actual active street centerlines from DataSF. North is up.
Landmark pins and neighborhood labels are approximate, not boundaries.
Road strokes are diagrammatic widths, not walkable surfaces.</desc>
<defs><clipPath id="map"><rect x="{LEFT}" y="{TOP}" width="{MAP_WIDTH}"
height="{MAP_HEIGHT}" rx="8"/></clipPath></defs>
<style>
text{{font-family:Arial,sans-serif}}
.road-label{{font-size:12px;font-weight:600;fill:#665f52;paint-order:stroke;
stroke:#f7f4eb;stroke-width:4px;stroke-linejoin:round}}
.place{{font-size:13px;font-weight:600;fill:#25463b;paint-order:stroke;
stroke:#f7f4eb;stroke-width:5px}}
.district{{font-size:23px;font-weight:700;letter-spacing:3px;fill:#9b927f;
paint-order:stroke;stroke:#f7f4eb;stroke-width:7px}}
</style>
<rect width="1080" height="1290" fill="#f7f4eb"/>
<text x="64" y="52" font-size="29" font-weight="700" fill="#263e36">SAN FRANCISCO</text>
<text x="64" y="84" font-size="19" fill="#647168">SoMa + Mission / geographic base map</text>
<text x="64" y="110" font-size="12" fill="#817c70">
Real street geometry. No fictional blocks. Simulation design reference, not a navigation map.</text>
<rect x="{LEFT}" y="{TOP}" width="{MAP_WIDTH}" height="{MAP_HEIGHT}" fill="#eae5d8" rx="8"/>
<g clip-path="url(#map)">'''
    ]
    main_roads = {
        "MARKET ST",
        "MISSION ST",
        "VALENCIA ST",
        "DOLORES ST",
        "CHURCH ST",
        "SOUTH VAN NESS AVE",
        "FOLSOM ST",
        "HARRISON ST",
        "HOWARD ST",
        "BRYANT ST",
        "16TH ST",
        "24TH ST",
        "18TH ST",
        "20TH ST",
        "DIVISION ST",
        "13TH ST",
        "03RD ST",
        "04TH ST",
        "06TH ST",
        "08TH ST",
        "09TH ST",
        "11TH ST",
    }
    paths = []
    for street in streets:
        geometry = street["line"]
        lines = (
            [geometry["coordinates"]]
            if geometry["type"] == "LineString"
            else geometry["coordinates"]
        )
        name = street["streetname"]
        for line in lines:
            points = [project(*point[:2]) for point in line]
            path = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points)
            freeway = "FWY" in name or "RAMP" in name
            width = (
                7 if name == "MARKET ST" else 4.8 if name in main_roads else 3.4 if freeway else 2
            )
            color = "#c69d61" if name == "MARKET ST" else "#b9bdc0" if freeway else "#faf9f4"
            paths.append((path, width, color))
    for path, width, _ in paths:
        parts.append(
            f'<path d="{path}" fill="none" stroke="#d3cbbd" stroke-width="{width + 1.4}"/>'
        )
    for path, width, color in paths:
        parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}"/>')
    labels = [
        ("MARKET STREET", -122.4131, 37.7786, -43),
        ("HOWARD", -122.4075, 37.7779, -43),
        ("FOLSOM", -122.4100, 37.7739, -43),
        ("HARRISON", -122.4059, 37.7741, -43),
        ("4TH STREET", -122.3995, 37.7792, 47),
        ("6TH STREET", -122.4054, 37.7780, 47),
        ("9TH STREET", -122.4134, 37.7737, 47),
        ("DIVISION / 13TH", -122.4165, 37.7693, 0),
        ("16TH STREET", -122.4143, 37.7652, 0),
        ("18TH STREET", -122.4180, 37.7615, 0),
        ("20TH STREET", -122.4085, 37.7585, 0),
        ("24TH STREET", -122.4147, 37.7524, 0),
        ("VALENCIA", -122.4214, 37.7584, -86),
        ("MISSION", -122.4189, 37.7582, -86),
        ("SOUTH VAN NESS", -122.4166, 37.7585, -86),
        ("FOLSOM", -122.4146, 37.7586, -86),
        ("HARRISON", -122.4129, 37.7587, -86),
    ]
    for label, lon, lat, angle in labels:
        x, y = project(lon, lat)
        parts.append(
            '<text class="road-label" text-anchor="middle" '
            f'transform="translate({x:.1f},{y:.1f}) rotate({angle})">{escape(label)}</text>'
        )
    for label, lon, lat in [
        ("WESTERN SOMA", -122.4161, 37.7754),
        ("CENTRAL SOMA", -122.4020, 37.7807),
        ("MISSION", -122.4167, 37.7633),
    ]:
        x, y = project(lon, lat)
        parts.append(
            f'<text class="district" text-anchor="middle" x="{x:.1f}" y="{y:.1f}">{label}</text>'
        )
    pins = [
        ("Dolores Park", -122.4269, 37.7597, "#54916b", 12),
        ("Yerba Buena Gardens", -122.4023, 37.7849, "#54916b", 12),
        ("Victoria Manalo Draves Park", -122.4067, 37.7771, "#54916b", 12),
        ("16th / Mission BART", -122.4197, 37.7650, "#357d9a", -12),
        ("24th / Mission BART", -122.4185, 37.7523, "#357d9a", -12),
        ("4th / King Caltrain", -122.3959, 37.7764, "#357d9a", -12),
    ]
    for label, lon, lat, color, dx in pins:
        x, y = project(lon, lat)
        anchor = "start" if dx > 0 else "end"
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{color}" '
            'stroke="#fff" stroke-width="2"/>'
            f'<text class="place" text-anchor="{anchor}" x="{x + dx:.1f}" '
            f'y="{y - 9:.1f}">{escape(label)}</text>'
        )
    parts.append("</g>")
    parts.append(
        '<path d="M990,1160 L990,1110 M982,1122 L990,1110 L998,1122" fill="none" '
        'stroke="#34483e" stroke-width="3"/>'
        '<text x="990" y="1097" text-anchor="middle" font-size="15" fill="#34483e">N</text>'
    )
    bar = 500 / 111320 * SCALE
    parts.append(
        f'<path d="M90,1170 h{bar:.1f}" stroke="#34483e" stroke-width="4"/>'
        '<text x="90" y="1157" font-size="12" fill="#34483e">500 m (approx.)</text>'
    )
    parts.append(f"""<text x="64" y="1220" font-size="12" fill="#647168">
Source: City and County of San Francisco / DataSF,
Streets - Active and Retired (3psu-pn9h).</text>
<text x="64" y="1242" font-size="12" fill="#647168">
Retrieved {date.today().isoformat()} · {len(streets)} active segments ·
local geographic projection; north up.</text>
<text x="64" y="1264" font-size="12" fill="#817c70">
Landmark pins / labels are approximate.
No parcel, park boundary, road width or transit routing is implied.</text>
</svg>""")
    output = ROOT / "docs/maps/soma-mission-reference.svg"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts), encoding="utf-8")
    print(f"Saved {output}", flush=True)


if __name__ == "__main__":
    main()
