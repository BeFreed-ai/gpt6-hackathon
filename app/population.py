"""Offline synthetic adults with separately attributed public career references."""

from __future__ import annotations

import json
import math
import random
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.sf_economy import economic_profiles

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sf_population.json"
_PAST_EXPERIENCES = (
    "Previously learned to prepare a meal from a written recipe.",
    "Previously helped carry groceries for someone they knew.",
    "Previously used a public library to find information.",
    "Previously repaired a loose button on a piece of clothing.",
    "Previously waited for a delayed bus during a routine trip.",
    "Previously shared a meal with a neighbor.",
    "Previously found an unfamiliar destination using a street map.",
    "Previously kept a written record of household purchases.",
)


def _apportion(count: int, sizes: dict[str, int | Fraction], rng: random.Random) -> dict[str, int]:
    """Hamilton allocation, with exact integer remainders and seeded tie breaking."""
    if type(count) is not int or count < 0:
        raise ValueError("Allocation count must be a nonnegative integer")
    if not sizes or any(size < 0 for size in sizes.values()) or sum(sizes.values()) <= 0:
        raise ValueError("Allocation weights must be nonnegative with a positive total")
    total = sum(sizes.values())
    quotas = {key: divmod(count * size, total) for key, size in sizes.items()}
    result = {key: int(quotient) for key, (quotient, _) in quotas.items()}
    tie_order = list(sizes)
    rng.shuffle(tie_order)
    ranked = sorted(tie_order, key=lambda key: quotas[key][1], reverse=True)
    for key in ranked[: count - sum(result.values())]:
        result[key] += 1
    return result


def _combined(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "estimate": sum(row["estimate"] for row in rows),
        "moe_90_approx": math.sqrt(sum(row["moe"] ** 2 for row in rows)),
    }


def _assign_employment(profiles: list[dict], data: dict, seed: int) -> dict:
    """Assign measured older marginals independently, with explicit proxy metadata."""
    source = data["employment_calibration"]
    rng = random.Random(f"employment:{seed}")
    report = {key: value for key, value in source.items() if key != "source_rows"}
    report["neighborhoods"] = {}
    for key, name in data["geography"]["neighborhoods"].items():
        row = next(row for row in source["source_rows"] if row["Neighborhood"] == name)
        participation = Fraction(row["Labor Force Participation Rate"])
        unemployed = Fraction(row["Unemployment Rate"])
        shares = {
            "employed": participation - unemployed,
            "unemployed": unemployed,
            "not_in_labor_force": 1 - participation,
        }
        residents = [profile for profile in profiles if profile["neighborhood"] == key]
        counts = _apportion(len(residents), shares, rng)
        statuses = [status for status, number in counts.items() for _ in range(number)]
        rng.shuffle(statuses)
        occupation_shares = {
            sector: Fraction(row[column]) for sector, column in source["occupation_columns"].items()
        }
        sectors = _apportion(counts["employed"], occupation_shares, rng)
        occupations = [sector for sector, number in sectors.items() for _ in range(number)]
        rng.shuffle(occupations)
        for profile, status in zip(residents, statuses, strict=True):
            profile["employment_status"] = status
            occupation = occupations.pop() if status == "employed" else None
            profile["occupation_sector"] = occupation
            profile["assumed_metadata"]["employment_basis"] = source["assumption"]
            if occupation:
                statement = f"Currently works in a {occupation.replace('_', ' ')} occupation."
            elif status == "unemployed":
                statement = "Currently has no paid job and is available for work."
            else:
                statement = "Currently is outside the labor force."
            profile["background"].append(statement)
        report["neighborhoods"][key] = {
            "source_values": row,
            "status_target_shares_proxy": {k: float(v) for k, v in shares.items()},
            "status_target_sample_counts": {
                k: len(residents) * float(v) for k, v in shares.items()
            },
            "status_realized_counts": {
                status: Counter(p["employment_status"] for p in residents)[status]
                for status in shares
            },
            "occupation_target_shares": {k: float(v) for k, v in occupation_shares.items()},
            "occupation_realized_counts": sectors,
            "weights_calibrate_employment": False,
        }
    return report


def generate_population(count: int, seed: int = 17, *, include_mission_bay: bool = False) -> dict:
    """Return exactly ``count`` synthetic adult profiles plus an auditable report.

    Largest remainder allocates adults across neighborhoods, then age bands within
    each neighborhood. All finer personal circumstances are marked assumptions.
    This function performs only a local data read and never scales the caller's count.
    """
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be an integer")
    if count < 0:
        raise ValueError("count must be nonnegative")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")

    data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    if include_mission_bay:
        extension = data["mission_bay_extension"]
        data["geography"]["neighborhoods"]["mission_bay"] = "Mission Bay"
        data["source_rows"].extend(extension["source_rows"])
        data["employment_calibration"]["source_rows"].append(extension["employment_row"])
    rng = random.Random(seed)
    bands = data["adult_age_bands"]
    neighborhoods = {}
    for key, name in data["geography"]["neighborhoods"].items():
        rows = [row for row in data["source_rows"] if row["geography_name"] == name]
        total = next(row for row in rows if row["demographic_category"] == "all")
        age_rows = {row["acs_code"]: row for row in rows if row["acs_table"] == "B06001"}
        if sum(row["estimate"] for row in age_rows.values()) != total["estimate"]:
            raise ValueError(f"Source age estimates do not reconcile for {name}")
        minors = _combined([age_rows["002"], age_rows["003"]])
        adult_bands = {
            band["label"]: _combined([age_rows[code] for code in band["source_codes"]])
            for band in bands
        }
        neighborhoods[key] = {
            "name": name,
            "all_residents_estimate": total["estimate"],
            "all_residents_moe_90": total["moe"],
            "excluded_minors": minors,
            "adult_residents_estimate": total["estimate"] - minors["estimate"],
            "age_bands": adult_bands,
            "age_rows": age_rows,
        }

    adult_sizes = {key: value["adult_residents_estimate"] for key, value in neighborhoods.items()}
    adult_total = sum(adult_sizes.values())
    neighborhood_counts = _apportion(count, adult_sizes, rng)
    profiles = []
    strata = []
    neighborhood_report = {}
    for key, neighborhood in neighborhoods.items():
        sample_count = neighborhood_counts[key]
        age_sizes = {label: value["estimate"] for label, value in neighborhood["age_bands"].items()}
        age_counts = _apportion(sample_count, age_sizes, rng)
        neighborhood_report[key] = {
            field: value for field, value in neighborhood.items() if field != "age_rows"
        } | {
            "target_share_of_adults": adult_sizes[key] / adult_total,
            "target_sample_count": count * adult_sizes[key] / adult_total,
            "realized_count": sample_count,
            "realized_share": sample_count / count if count else 0.0,
            "residents_per_agent": adult_sizes[key] / sample_count if sample_count else None,
        }
        for band in bands:
            label = band["label"]
            size = age_sizes[label]
            realized = age_counts[label]
            weight = size / realized if realized else None
            strata.append(
                {
                    "neighborhood": key,
                    "age_band": label,
                    "adult_residents_estimate": size,
                    "moe_90_approx": neighborhood["age_bands"][label]["moe_90_approx"],
                    "target_share_of_adults": size / adult_total,
                    "target_share_within_neighborhood": size / adult_sizes[key],
                    "target_sample_count": count * size / adult_total,
                    "conditional_target_sample_count": sample_count * size / adult_sizes[key],
                    "realized_count": realized,
                    "realized_share": realized / count if count else 0.0,
                    "residents_per_agent": weight,
                }
            )
            source_rows = [neighborhood["age_rows"][code] for code in band["source_codes"]]
            for _ in range(realized):
                source_row = rng.choices(source_rows, [row["estimate"] for row in source_rows])[0]
                lower, upper = data["source_age_ranges"][source_row["acs_code"]]
                age = rng.randint(lower, upper if upper is not None else 100)
                months = rng.randint(1, min(age * 12, 360))
                profiles.append(
                    {
                        "neighborhood": key,
                        "age": age,
                        "age_band": label,
                        "housing_status": "unspecified",
                        "employment_status": "unspecified",
                        "occupation_sector": None,
                        "background": [
                            f"Lives in {neighborhood['name']}, San Francisco.",
                            f"Has lived in this neighborhood for {months} months.",
                            *rng.sample(_PAST_EXPERIENCES, 2),
                        ],
                        "synthetic": True,
                        "sampling_weight": weight,
                        "assumed_metadata": {
                            "residence_duration_months": months,
                            "exact_age_basis": data["assumptions"]["individual_age"],
                            "background_basis": data["assumptions"]["background"],
                            "unmeasured_fields": data["assumptions"]["unmeasured_fields"],
                        },
                    }
                )

    rng.shuffle(profiles)
    for index, profile in enumerate(profiles, 1):
        profile["synthetic_id"] = f"resident_{index:05d}"

    employment_report = _assign_employment(profiles, data, seed)
    for profile, economics in zip(profiles, economic_profiles(profiles, seed), strict=True):
        profile["economic_profile"] = economics

    all_residents = sum(item["all_residents_estimate"] for item in neighborhoods.values())
    uncovered = [item for item in strata if item["realized_count"] == 0]
    report = {
        "schema_version": data["schema_version"],
        "requested_count": count,
        "realized_count": len(profiles),
        "seed": seed,
        "vintage": data["vintage"],
        "retrieved_on": data["retrieved_on"],
        "source_url": data["source_url"],
        "source_query_url": data["query_url"],
        "sources": [
            {
                "name": "DataSF resident population and age",
                "url": data["source_url"],
                "vintage": data["vintage"],
                "scope": "Neighborhood resident population calibration",
            },
            {
                "name": "SF Planning resident employment and occupation profiles",
                "url": data["employment_calibration"]["source_url"],
                "vintage": data["employment_calibration"]["vintage"],
                "scope": "Older age16+ proxy; independent synthetic assignment",
            },
        ],
        "geography": data["geography"],
        "population_scope": "Adult residents aged 18+ of "
        + ", ".join(data["geography"]["neighborhoods"].values()),
        "all_residents_estimate": all_residents,
        "adult_residents_estimate": adult_total,
        "excluded_minors_estimate": all_residents - adult_total,
        "excluded_minors_share": (all_residents - adult_total) / all_residents,
        "citywide_context": data["citywide_context"],
        "current_citywide_context": data.get("current_citywide_context"),
        "employment_calibration": employment_report,
        "method": "Seeded largest remainder: neighborhood adults, then age within neighborhood",
        "neighborhoods": neighborhood_report,
        "strata": strata,
        "sampling_weights": {
            "definition": "Stratum adult estimate / realized agents; null for an empty stratum",
            "unrepresented_adults_estimate": sum(
                item["adult_residents_estimate"] for item in uncovered
            ),
            "represented_adults_estimate": sum(
                item["adult_residents_estimate"] for item in strata if item["realized_count"]
            ),
            "unrepresented_strata": [
                {"neighborhood": item["neighborhood"], "age_band": item["age_band"]}
                for item in uncovered
            ],
            "probability_sample": False,
        },
        "assumptions": data["assumptions"],
        "latest_accessible_note": data["latest_accessible_note"],
        "limitations": data["limitations"],
    }
    if include_mission_bay:
        report["additional_source_queries"] = [data["mission_bay_extension"]["query_url"]]
    return {"profiles": profiles, "report": report}


# Occupational histories describe work already done, not personalities or future goals.
_ROLE_PATHS = {
    "management_business_science_arts": (
        ("project assistant", "operations analyst", "prepared schedules and project reports"),
        ("design assistant", "communications specialist", "edited accessible public materials"),
        ("accounts assistant", "budget analyst", "reconciled invoices and spending records"),
        ("technical trainee", "systems analyst", "tested tools and documented recurring faults"),
    ),
    "service": (
        ("service trainee", "facilities attendant", "prepared shared spaces for daily use"),
        ("kitchen assistant", "food preparation worker", "prepared meals and checked supplies"),
    ),
    "sales_office": (
        ("office assistant", "administrative coordinator", "maintained appointments and records"),
        (
            "customer service trainee", "customer service representative",
            "answered service inquiries",
        ),
    ),
    "natural_resources_construction_maintenance": (
        (
            "maintenance helper", "maintenance technician",
            "repaired fixtures and logged inspections",
        ),
    ),
    "production_transportation_material_moving": (
        ("stockroom assistant", "materials handler", "received deliveries and tracked inventory"),
    ),
}


def _earlier_life_events(
    age: int, first_age: int, current_age: int, junior: str, rng: random.Random
) -> list[dict]:
    """Write connected fictional episodes, with age-safe chronology and no assigned values."""
    childhood_age = rng.randint(8, 12)
    teen_age = rng.randint(15, 17)
    childhood = rng.choice((
        "my class made a small neighborhood exhibition. I collected descriptions of everyday "
        "places, copied them onto cards, and helped arrange the display. One card went missing "
        "before the opening, so a classmate and I reconstructed it from our rough notes",
        "a relative showed me how to use a library catalog. We searched for a book that was "
        "already checked out, reserved it, and returned the following week. I used its pictures "
        "for a school assignment and kept the handwritten list of other books we found",
        "a school group planned an afternoon field trip. I helped check the list of supplies "
        "and carried a shared notebook. Rain changed the route, and we finished the activity "
        "indoors by drawing the places we had managed to visit",
        "I helped prepare a neighborhood potluck with adults from my household. I copied labels "
        "for the dishes and counted the cups. After more guests arrived than expected, we "
        "rearranged the tables and washed an extra set of dishes together",
    ))
    adolescence = rng.choice((
        "I worked on a group assignment that needed several revisions. My part was to gather "
        "the notes and keep track of the latest version. We missed an early practice deadline, "
        "then divided the remaining work into smaller pieces and delivered the final presentation",
        "I joined a short community workshop where participants repaired donated objects. My "
        "first repair did not hold, so an instructor helped me work out which step I had skipped. "
        "I repeated the repair and wrote down the sequence before returning the tools",
        "I helped organize materials for a small local event. A late delivery meant the original "
        "setup would not work, so the group changed the layout. I spent the afternoon moving "
        "boxes, checking labels and telling arriving participants where the activities had moved",
        "I took part in a school oral-history assignment. I arranged a conversation with an "
        "adult I knew, took notes, and checked the draft with them afterward. They corrected "
        "several dates before I submitted the final account to the teacher",
    ))
    practical_age = rng.randint(first_age, age)
    practical = rng.choice((
        "I compared the receipts from several weeks of ordinary purchases. A duplicate charge "
        "took two conversations to resolve, and I kept copies of the receipts until the correction "
        "arrived. That folder later became the place where I stored other household paperwork",
        "a routine trip was disrupted by a missed connection. I asked for directions, used a "
        "different route and arrived later than planned. Afterward I wrote down both routes "
        "and the transfer points so the same trip would not require starting from scratch",
        "I spent a weekend helping an acquaintance move. We underestimated how long packing "
        "would take and had to make an additional trip. I labeled the last boxes, returned "
        "the borrowed equipment and helped check that nothing remained in the old room",
        "I shared responsibility for a set of recurring household errands. We tried a paper "
        "calendar after two tasks were accidentally duplicated. Over several weeks we changed "
        "the arrangement, crossed off completed work and moved unfinished items to later dates",
    ))
    events = [
        {"age": childhood_age, "event": f"When I was {childhood_age}, {childhood}."},
        {"age": teen_age, "event": f"At {teen_age}, {adolescence}."},
        {"age": practical_age, "event": f"At age {practical_age}, {practical}."},
    ]
    if current_age > first_age:
        events.append({"age": first_age, "event": (
            f"At {first_age}, before my present situation, I had a short {junior} placement. "
            "An experienced coworker showed me the daily handover process. During the first "
            "week I had to correct an incomplete record; by the end of the placement I could "
            "complete the routine and explain the remaining work to the next person."
        )})
    else:
        events.append({"age": first_age, "event": (
            f"At {first_age}, I was still at the beginning of adult working life. I practiced "
            "following written instructions in a supervised introductory activity, asked for "
            "clarification when a step was unclear, and revised my first attempt after feedback. "
            "This was early practical exposure, not years of professional experience."
        )})
    return events


def _cast_public_figures(profiles: list[dict], allocation: dict) -> list[dict]:
    """Replace two existing adult slots; never fabricate private facts about real people."""
    if len(profiles) != 100:
        return []
    path = _DATA_PATH.parent / "public_figure_backgrounds.json"
    packet = json.loads(path.read_text(encoding="utf-8"))
    figures = [dict(figure, notice=packet["notice"]) for figure in packet["figures"]]
    if len(figures) != 2 or len({f["id"] for f in figures}) != 2:
        raise ValueError("The 100-person preview requires two distinct public-figure records")
    assignments = allocation["assignments"]
    selected = set()
    audit = []
    for figure in figures:
        candidates = [
            i for i, p in enumerate(profiles)
            if i not in selected and p["age_band"] == "35-54"
            and p["employment_status"] == "employed"
            and p.get("occupation_group") == "management_business_science_arts"
        ]
        donors = [
            i for i, employer_id in enumerate(assignments)
            if i not in selected and employer_id == figure["employer_id"]
        ]
        if not candidates or not donors:
            raise ValueError(
                "Public-figure casting needs an adult management slot and employer seat"
            )
        index = next((i for i in candidates if i in donors), candidates[0])
        donor = index if index in donors else donors[0]
        assignments[index], assignments[donor] = assignments[donor], assignments[index]
        profiles[index]["occupation_sector"], profiles[donor]["occupation_sector"] = (
            profiles[donor]["occupation_sector"], profiles[index]["occupation_sector"]
        )
        age = figure.get("age", profiles[index]["age"])
        if type(age) is not int or not 35 <= age <= 54:
            raise ValueError("Public-figure age must remain in the selected adult age stratum")
        profiles[index]["age"] = age
        profiles[index]["public_figure"] = figure
        selected.add(index)
        audit.append({
            "synthetic_id": profiles[index]["synthetic_id"], "public_figure_id": figure["id"],
            "display_name": figure["name"],
            "employer_id": figure["employer_id"],
            "basis": "Intentional public-figure casting; not an observed neighborhood resident",
        })
    for index, employer_id in enumerate(assignments):
        if employer_id and employer_id.startswith("sector_"):
            profile = profiles[index]
            assignments[index] = (
                f"sector_{profile['occupation_sector']}_{profile['neighborhood']}"
            )
    allocation["report"]["workplace_counts"] = dict(
        sorted(Counter(employer_id for employer_id in assignments if employer_id).items())
    )
    return audit


def _attach_person_references(profiles: list[dict]) -> dict:
    """Assign distinct public counterparts without changing demographic or job margins."""
    if len(profiles) != 100:
        return {"count": 0, "basis": "The curated counterpart roster applies to 100-person runs"}
    packet = json.loads((_DATA_PATH.parent / "sf_person_references.json").read_text())
    available = list(packet["people"])
    if len(available) != 98 or len({p["id"] for p in available}) != 98:
        raise ValueError("The 100-person cast requires 98 distinct professional references")
    domains = {
        "technology": "tech", "food_service": "food_hospitality", "retail": "retail_personal",
        "public_service": "public_admin", "arts": "arts_recreation",
    }
    # Reserve the two requested OpenAI counterparts before assigning other domains.
    ordered = sorted(profiles, key=lambda p: (
        not bool(p.get("public_figure")),
        p.get("workplace_assignment") != "openai_mission_bay",
        p["employment_status"] != "employed",
    ))
    for profile in ordered:
        if figure := profile.get("public_figure"):
            reference = {
                "id": figure["id"], "name": figure["name"], "sources": figure["sources"],
                "public_career_facts": figure["biography"],
                "matching_basis": "Explicitly requested public-figure simulation",
                "notice": packet["notice"],
            }
        else:
            sector = profile.get("occupation_sector")
            domain = domains.get(sector, sector)
            preferred = [r for r in available if r.get("preferred_workplace")
                         and r["preferred_workplace"] == profile.get("workplace_assignment")]
            matching = [r for r in available if r["domain"] == domain]
            selected = (preferred or matching or available)[0]
            available.remove(selected)
            reference = dict(selected, sources=[packet["sources"][selected["source_id"]]])
            reference["matching_basis"] = (
                "Published employer affiliation; simulated role and private life differ"
                if preferred else "Broad industry analogy; role and seniority can differ"
                if matching else "Public career context only; simulated employment differs"
            )
            reference["notice"] = packet["notice"]
        profile["person_reference"] = reference
        profile["name"] = reference["name"]
    return {
        "count": 100, "unique_people": len({p["person_reference"]["id"] for p in profiles}),
        "source_catalog": "data/sf_person_references.json",
        "selection_basis": packet["selection_basis"], "notice": packet["notice"],
        "matching_counts": dict(Counter(p["person_reference"]["matching_basis"] for p in profiles)),
    }


_RECENT_ARCS = (
    (
        "{day} days before this run, I borrowed a book about {subject} from the library. "
        "I expected to read straight through, but stopped at a diagram I could not follow and "
        "copied it onto a loose page to work through later.",
        "Nine days before this run, I returned to the diagram and compared it with the next "
        "chapter. I discovered I had skipped a label. After redrawing it, I could explain the "
        "example without looking at the text.",
        "Two days before this run, I returned the book and kept my page of notes. On the way "
        "home I stopped for groceries, then put the notes into a folder with other completed "
        "exercises rather than leaving loose paper on the kitchen table.",
    ),
    (
        "{day} days before this run, a bus delay interrupted a routine errand. I walked to "
        "a different stop and wrote down the cross streets after finding that the route on my "
        "old paper map no longer matched the sign.",
        "Nine days before this run, I repeated the trip with the corrected directions. I "
        "noticed the transfer required crossing the street, so I added that detail to the "
        "note and arrived with enough time to finish the errand.",
        "Two days before this run, I found the old map while emptying my bag. I marked the "
        "correction clearly, folded it along its existing creases and put it back. The trip "
        "had become familiar through those two attempts, rather than through a special plan.",
    ),
    (
        "{day} days before this run, I tried making {meal} from a recipe copied onto a card. "
        "I misread the order of two steps and ended up using a second pan. The food was edible, "
        "but there was considerably more washing up than expected.",
        "Nine days before this run, I made the same dish again with the instructions laid "
        "out beside the ingredients. I used the leftover vegetables first and changed the "
        "order on the card. This time I finished with only one pan to clean.",
        "Two days before this run, I packed the remaining portion and washed its container "
        "after eating. The recipe card is now in the kitchen drawer, with a food stain and "
        "two handwritten corrections from the earlier attempts.",
    ),
    (
        "{day} days before this run, I attended a free introductory session about {subject}. "
        "The group worked through a small exercise in pairs. I wrote down an example that "
        "did not make sense yet and asked the facilitator to show the intermediate step.",
        "Nine days before this run, I tried the exercise again at home. My first result "
        "differed from the handout, so I checked each stage until I found the missing step. "
        "I kept the unsuccessful attempt beside the corrected one.",
        "Two days before this run, I sorted the handouts into a folder. I discarded duplicate "
        "pages, kept the worked example and returned a borrowed pencil. The session was a "
        "completed experience; it did not create an obligation to take another class.",
    ),
    (
        "{day} days before this run, I helped set out chairs for a neighborhood gathering. "
        "The first layout blocked the route to the refreshments, so we moved one row and "
        "tested the gap by carrying an empty tray through it.",
        "Nine days before this run, someone returned a box of supplies left from that "
        "gathering. I counted the cups, separated reusable items from damaged ones and "
        "wrote a short inventory on the inside of the lid.",
        "Two days before this run, I brought the box back to the person storing it. We "
        "checked the inventory together and found a stack of napkins tucked under the cups. "
        "I corrected the count before heading home through {neighborhood}.",
    ),
    (
        "{day} days before this run, I sorted a drawer of old photographs and postcards. "
        "Several envelopes had lost their labels. I grouped the pictures by visible places "
        "and left uncertain dates blank instead of forcing them into an order.",
        "Nine days before this run, a relative helped identify one of the locations during "
        "a phone conversation. I added the location in pencil and left the year open because "
        "neither of us could remember it confidently.",
        "Two days before this run, I put the sorted pictures into plain envelopes. I "
        "found a duplicate postcard, used it as a bookmark and returned the rest to the "
        "drawer. The uncertain photographs still have blank date fields.",
    ),
    (
        "{day} days before this run, I took a walk through {neighborhood} with a small sketchbook. "
        "I stopped to draw the outline of a building, then realized that I had placed its "
        "windows too close together and ran out of room at the edge.",
        "Nine days before this run, I passed the same building and checked the drawing. "
        "I counted the windows, made a lighter outline on a new page and added the cross "
        "street beneath it so I could distinguish the two attempts.",
        "Two days before this run, I sharpened the pencil over a wastebasket and put the "
        "sketchbook back in my bag. I kept both versions because together they recorded "
        "what I had actually seen and what I had initially missed.",
    ),
    (
        "{day} days before this run, I checked a receipt against the groceries I had brought "
        "home. One item appeared twice. I kept the packaging and receipt together rather "
        "than mixing them with the rest of the recycling.",
        "Nine days before this run, I took the receipt back during another grocery trip. "
        "The cashier checked the duplicate entry and corrected the transaction. I marked "
        "the adjustment on my household list before putting the receipt away.",
        "Two days before this run, I compared that list with what remained in the kitchen. "
        "I crossed out ingredients already used for {meal}, cleaned an empty storage "
        "container and made space for the next batch of groceries.",
    ),
    (
        "{day} days before this run, I lent a neighbor a basic household tool for a small "
        "repair. We checked which attachment was needed and placed the spare pieces in "
        "a separate bag so none would be lost in the work area.",
        "Nine days before this run, the tool came back with the spare pieces still bagged. "
        "We tested it together and talked through the completed repair. I noticed its "
        "storage case had no label and wrote the contents on a piece of tape.",
        "Two days before this run, I reorganized the shelf holding the case. I moved "
        "heavy items to the bottom, checked that the lid closed and returned a second "
        "borrowed item while passing the neighbor's doorway.",
    ),
    (
        "{day} days before this run, I tried following a printed exercise about {subject}. "
        "A coffee spill blurred the last instructions. I saved the readable pages and "
        "wrote down the title before separating the wet sheets to dry.",
        "Nine days before this run, I found another copy of the instructions through a "
        "public learning resource. The missing paragraph explained the final comparison, "
        "so I finished it and checked the result against the worked example.",
        "Two days before this run, I recycled the damaged copy and filed the completed "
        "exercise. I cleared the table, made {meal} and washed the mug that had caused "
        "the original spill. The replacement instructions stayed dry this time.",
    ),
)


def _complete_recent_history(profile: dict, index: int, seed: int) -> None:
    """Fictional connected recent episodes, never assertions about a counterpart's life."""
    rng = random.Random(f"recent-history:{seed}:{index}")
    objects = ("desk lamp", "canvas bag", "kitchen timer", "folding chair", "umbrella",
               "bicycle basket", "bookshelf", "coat hook", "travel mug", "window blind")
    objects_fixed = ("tightened its fitting", "replaced a small missing piece",
                     "cleaned and adjusted it", "found an appropriate replacement part")
    item = rng.choice(objects)
    repair = rng.choice(objects_fixed)
    # Each repetition of a narrative arc has a different starting date in the 100-person cast.
    day = 19 + (index // 11) % 10
    reference = profile.get("person_reference")
    recent = [
        {"age": profile["age"], "days_before_start": day, "event": (
            f"{day} days before this run, my {item} stopped working properly while I was "
            "rearranging the room. I drew the part that needed attention on a scrap of paper, "
            "compared it with the item, and put both beside my keys so I could take another look."
        )},
        {"age": profile["age"], "days_before_start": 9, "event": (
            f"Nine days before this run, I returned to the {item} and {repair}. "
            "The first attempt did not fit, so I checked the sketch and tried again. "
            "It worked on the second attempt; I kept the scrap of paper with my household receipts."
        )},
        {"age": profile["age"], "days_before_start": 2, "event": (
            "Two days before this run, I sorted those receipts while waiting for laundry. "
            f"I found the sketch of the {item}, crossed the repair off the old list, and "
            "copied the remaining household errands onto a clean page. I put the laundry away "
            "and checked which ingredients were already in the kitchen before making dinner."
        )},
    ]
    if index % 11:
        context = {
            "day": day,
            "neighborhood": profile["neighborhood"].replace("_", " ").title(),
            "subject": rng.choice(("basic photography", "spreadsheet formulas", "bookbinding",
                                   "map reading", "container gardening", "local architecture")),
            "meal": rng.choice(("vegetable soup", "rice and beans", "a tray of roasted vegetables",
                                "noodles with greens", "a lentil stew", "a potato omelet")),
        }
        recent = [
            {"age": profile["age"], "days_before_start": days, "event": text.format(**context)}
            for days, text in zip((day, 9, 2), _RECENT_ARCS[index % 11 - 1], strict=True)
        ]
    if profile.get("public_figure"):
        # These are explicitly invented alternate-life scenes, not a reconstructed childhood.
        profile["life_history"] = [
            {"age": 10, "event": (
                "At ten, I helped assemble a small booklet for a school activity. A page came "
                "out upside down, and I had to take the staples out and put the pages "
                "back in order."
            )},
            {"age": 17, "event": (
                "At seventeen, I helped a neighbor organize a box of donated books. We changed "
                "the labels after discovering that several volumes belonged to the same set."
            )},
        ]
    for event in profile["life_history"]:
        event["provenance"] = "fictional_simulation_history"
    for event in recent:
        event["provenance"] = "fictional_simulation_history"
    profile["recent_experiences"] = recent
    profile["life_history"].extend(recent)
    for event in profile["life_history"]:
        original = event["event"]
        event["event"] = f"Fictional simulation memory: {original}"
        profile["background"] = [event["event"] if s == original else s
                                 for s in profile["background"]]
    extra = profile["life_history"] if profile.get("public_figure") else recent
    profile["background"].extend(e["event"] for e in extra)
    fiction = "\n\n".join(e["event"] for e in profile["life_history"])
    if profile.get("public_figure"):
        profile["life_story"] += "\n\n" + fiction
    else:
        profile["life_story"] = fiction
        profile["background"].insert(0, "This is a fictional character with a public professional "
                                     "counterpart; all personal memories below are invented.")
    if reference:
        lines = [f"Public counterpart reference: {reference['name']}. "
                 f"{reference['matching_basis']}. These are source notes, "
                 "not my personal memories."]
        if not profile.get("public_figure"):
            lines.extend(f"Public career fact about {reference['name']}: {fact}"
                         for fact in reference["public_career_facts"])
            lines.extend(f"Public counterpart source: {s['title']} ({s['url']})."
                         for s in reference["sources"])
        profile["background"].extend(lines)
        profile["assumed_metadata"]["person_reference_id"] = reference["id"]
    profile["assumed_metadata"]["life_history_basis"] = (
        "Explicitly fictional memories; public career references are separately attributed. "
        "Not a claim to know an actual person's complete life or recent private activities."
    )


def generate_scenario_population(count: int = 100, seed: int = 17) -> dict:
    """Enrich the unchanged demographic sampler with audited workplaces and private lives.

    Identity, timelines and household circumstances are fictional. Exact employment
    and occupation margins are retained; industry uses a separately disclosed proxy.
    Housing rent and household membership are finalized by the existing world economy.
    """
    from app.employers import allocate_scenario_workplaces, load_employers

    population = generate_population(count, seed, include_mission_bay=True)
    profiles = population["profiles"]
    allocation = allocate_scenario_workplaces(profiles, seed)
    casting = _cast_public_figures(profiles, allocation)
    employers = {row["id"]: row for row in load_employers()}
    rng = random.Random(f"personal-history:{seed}")
    economics = economic_profiles(profiles, seed)
    for index, (profile, workplace_id, budget) in enumerate(
        zip(profiles, allocation["assignments"], economics, strict=True), 1
    ):
        profile["name"] = f"Citizen {index:03d}"
        profile["population_role"] = "resident"
        profile["workplace_assignment"] = workplace_id
        profile["economic_profile"] = budget
        profile["housing_status"] = "rental"
        profile["housing_basis"] = "Synthetic rental room; household sharing finalized at placement"
        profile["employer_name"] = (
            employers[workplace_id]["name"] if workplace_id in employers else
            f"{profile['neighborhood'].replace('_', ' ').title()} "
            f"{profile['occupation_sector'].replace('_', ' ').title()} Workplace"
            if workplace_id else None
        )
        if figure := profile.get("public_figure"):
            profile["name"] = figure["name"]
            profile["character_type"] = "public_figure_simulation"
            profile["occupation_title"] = figure["occupation_title"]
            profile["life_history"] = []
            profile["life_story"] = "\n\n".join(figure["biography"])
            profile["background"] = [
                "This is a clearly labeled fictional public-figure simulation, "
                "not the actual person, an endorsement, or an authorized representative. "
                "New speech, decisions and actions are fictional and must not be presented "
                "as historical statements by the real person.",
                *figure["biography"],
                "My assigned neighborhood, rental room, finances and physical circumstances "
                "are synthetic game conditions, not facts or inferences about the real person. "
                "The sourced public biography is distinct from my fictional future actions.",
            ]
            profile["background"].extend(
                f"Public history source: {source['title']} ({source['url']})."
                for source in figure["sources"]
            )
            profile["assumed_metadata"] = {
                "casting_basis": "User-requested public figure in an existing adult slot",
                "private_circumstances": "Entirely synthetic; not inferred personal information",
                "historical_sources": figure["sources"],
            }
            continue
        group = profile.get("occupation_group")
        history_group = group or rng.choice(list(_ROLE_PATHS))
        junior, role, task = rng.choice(_ROLE_PATHS[history_group])
        age = profile["age"]
        first_age = rng.randint(18, min(age, 24))
        current_age = rng.randint(max(first_age, age - 5), age)
        # Young adults stay in a junior role; no implausible decades of experience.
        role = junior if age - first_age < 2 else role
        profile["occupation_title"] = role if workplace_id else None
        learning = rng.choice((
            "practiced spreadsheet exercises through a public learning resource",
            "completed a short workplace orientation with a trainer",
            "attended an introductory evening workshop on workplace communication",
            "learned to maintain a shared calendar during a community activity",
        ))
        timeline = [
            {"age": first_age, "event": f"At age {first_age}, I {learning}."},
        ]
        if workplace_id:
            timeline.append({"age": current_age, "event": (
                f"At age {current_age}, I started my current {role} role; my work has included "
                f"tasks where I {task}."
            )})
        elif profile["employment_status"] == "unemployed":
            timeline.append({"age": current_age, "event": (
                f"At age {current_age}, a temporary {junior} placement ended; "
                "I currently have no paid job and am available for work."
            )})
        else:
            circumstance = rng.choice((
                "I currently spend time on unpaid household responsibilities",
                "I currently attend nondegree classes without a paid job",
                "I am taking a break from paid work",
            ))
            timeline.append({
                "age": current_age, "event": f"Since age {current_age}, {circumstance}."
            })
        residence_months = profile["assumed_metadata"]["residence_duration_months"]
        move_age = max(0, age - (residence_months + 11) // 12)
        move_detail = (
            "My household handled the move; I learned nearby routes as I grew older."
            if move_age < 12 else
            "I kept a notebook of nearby transit stops and household errands."
        )
        timeline.append({"age": move_age, "event": (
            f"About {residence_months} months ago, I moved to "
            f"{profile['neighborhood'].replace('_', ' ').title()}; "
            f"{move_detail}"
        )})
        timeline.extend(_earlier_life_events(age, first_age, current_age, junior, rng))
        timeline.sort(key=lambda item: item["age"])
        profile["life_history"] = timeline
        profile["life_story"] = "\n\n".join(item["event"] for item in timeline)
        profile["background"].extend(item["event"] for item in timeline)
        profile["background"].append(
            "My synthetic starting cash reserve is "
            f"{budget['initial_savings_credits']:.2f} credits; "
            f"my modeled annual gross wage is ${budget['annual_gross_wage_usd']:.2f}, "
            "and my assumed annual nonlabor support is "
            f"${budget['annual_nonlabor_support_usd']:.2f}."
        )
        profile["assumed_metadata"]["life_history_basis"] = (
            "Fictional age-bounded history; not a LinkedIn profile or a real person's life. "
            "No identity-based assignment, imposed personality, values or life goals."
        )
    population["report"]["person_references"] = _attach_person_references(profiles)
    for index, profile in enumerate(profiles):
        _complete_recent_history(profile, index, seed)
    population["report"]["workplace_allocation"] = allocation["report"]
    population["report"]["public_figure_casting"] = {
        "count": len(casting), "characters": casting,
        "basis": "Intentional scenario casting within 100 slots; not representative sampling",
        "private_circumstances": "Synthetic game housing and budget, unrelated to real people",
    }
    population["report"]["scenario_id"] = "sf_adult_residents_industry_proxy_v1"
    population["report"]["geographic_scope"] = {
        "resident_calibration": "Mission, South of Market and Mission Bay Analysis Neighborhoods",
        "runnable_map": "SoMa/Mission/Mission Bay street network with synthetic sites",
        "eastern_sf": "Broader renderer extent; only the three named resident areas are fitted",
        "citywide_representative_sample": False,
        "inbound_commuters": 0,
        "children": 0,
    }
    return population
