"""Measure how common each dosha is under THIS app's own rules (§76.6).

A newcomer told "you have Kala Sarpa Dosha" deserves to know whether that is a
rare finding or one in three charts. Rather than quote a figure from a forum,
this samples birth moments and runs the app's own `get_doshas` on each, so the
number shown next to a dosha is a property of the rules the app actually uses.

Sample: births uniformly 1940-01-01 .. 2015-12-31 at a uniformly random minute,
in one of a spread of world cities; fixed seed so the result is reproducible.
Default ayanamsa (True Chitra), as the app uses by default.

    cd web/backend && venv/bin/python scripts/dosha_prevalence.py [N]

Writes dosha_prevalence.json next to this package. Re-run after changing a dosha
rule — tests/test_dosha_prevalence.py fails if a dosha has no measured figure.

Also measures the Compatibility tab's Mangal dosha (§83.3/§84) under
"compatibility", with the placement-before-cancellations figure the tab shows,
measured with compute_match._mangal_dosha on the same sampled charts. Since §86
the Birth Chart's "manglik" is that same function, so the two percents match.
"""
import json
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astrology import AstrologyCompute  # noqa: E402
from astrology.compute_match import _mangal_dosha  # noqa: E402
from astrology.engine import charts, drik, swe  # noqa: E402

# (place, lat, lon, standard UTC offset). Offsets are the zone's standard time;
# a sample needs plausible local times, not historical DST precision.
CITIES = [
    ("Delhi", 28.61, 77.21, 5.5), ("Mumbai", 19.08, 72.88, 5.5),
    ("Chennai", 13.08, 80.27, 5.5), ("Kolkata", 22.57, 88.36, 5.5),
    ("Kathmandu", 27.72, 85.32, 5.75), ("Dhaka", 23.81, 90.41, 6.0),
    ("London", 51.51, -0.13, 0.0), ("New York", 40.71, -74.01, -5.0),
    ("Los Angeles", 34.05, -118.24, -8.0), ("Sydney", -33.87, 151.21, 10.0),
    ("Singapore", 1.35, 103.82, 8.0), ("Johannesburg", -26.20, 28.05, 2.0),
    ("Sao Paulo", -23.55, -46.63, -3.0), ("Toronto", 43.65, -79.38, -5.0),
]
START, END = date(1940, 1, 1), date(2015, 12, 31)
SEED = 76


def main(n: int = 5000) -> None:
    rng = random.Random(SEED)
    span = (END - START).days
    counts, valid = {}, 0
    mangal = {"manglik": 0, "placement": 0}
    names = {}
    for _ in range(n):
        d = START + timedelta(days=rng.randrange(span + 1))
        minute = rng.randrange(24 * 60)
        place, lat, lon, tz = rng.choice(CITIES)
        res = AstrologyCompute.get_doshas(
            dob=d.isoformat(), tob=f"{minute // 60:02d}:{minute % 60:02d}:00",
            place=place, lat=lat, lon=lon, tz=tz)
        if res.get("status") != "success":
            continue
        valid += 1
        for dz in res.get("doshas", []):
            key = dz.get("key")
            names[key] = dz.get("name")
            counts[key] = counts.get(key, 0) + (1 if dz.get("present") else 0)
        # Same birth moment through the Compatibility tab's rule (no extra rng draws,
        # so the figures above stay reproducible).
        pp = charts.rasi_chart(swe.julday(d.year, d.month, d.day, minute / 60),
                               drik.Place(place, lat, lon, tz))
        m = _mangal_dosha(pp)
        mangal["manglik"] += m["manglik"]
        mangal["placement"] += m["status"] != "none"
    out = {
        "method": "Share of sampled birth moments where get_doshas reports the dosha present. "
                  "Births uniform 1940-2015, uniform minute, 14 world cities, default ayanamsa.",
        "samples": valid,
        "seed": SEED,
        "computed": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "doshas": {k: {"name": names[k], "percent": round(100 * c / valid, 1)}
                   for k, c in sorted(counts.items())},
        "compatibility": {
            "mangal": {
                "name": "Mangal (Kuja) Dosha — Compatibility tab",
                "percent": round(100 * mangal["manglik"] / valid, 1),
                # Mars in a dosha house from the Lagna, before cancellations.
                "placement_percent": round(100 * mangal["placement"] / valid, 1),
            },
        },
    }
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "dosha_prevalence.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    for k, v in out["doshas"].items():
        print(f"{v['percent']:5.1f}%  {v['name']}")
    c = out["compatibility"]["mangal"]
    print(f"{c['percent']:5.1f}%  {c['name']} ({c['placement_percent']}% before cancellations)")
    print(f"({valid} charts)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5000)
