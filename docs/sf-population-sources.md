# San Francisco synthetic resident population

`generate_population(count: int, seed: int = 17) -> dict` in `app/population.py`
returns `profiles` (exactly `count`) and a JSON-compatible `report`. It reads a
checked-in aggregate snapshot, makes no network or LLM calls, and never increases
the number of active agents. Zero is supported; negative counts and noninteger
counts/seeds (including booleans) are rejected.

## Sources, vintage, and geography

Retrieved **2026-09-08**. The resident calibration uses **2019–2023 ACS five-year
estimates** published by [DataSF, San Francisco Population and Demographic Census
Data](https://data.sfgov.org/d/4qbq-hvtt). The JSON retains the exact filtered API
query, all 24 source rows, table/cell codes, estimates, margins of error, and source
timestamps. The source rows were calculated by DataSF on January 2, 2025. This is a
period estimate, **not a current 2026 population count**.

An API inventory grouped by geography, end_year, and demographic_category found
2023 to be the latest exposed neighborhood age/total vintage. The Census Bureau
has released [2020–2024 ACS](https://www.census.gov/acs/www/data/data-tables-and-tools/data-profiles/2024/),
but this implementation chooses the latest accessible **published DataSF
neighborhood aggregation**, as opposed to claiming that 2023 is the latest Census
release. Updating to 2024 requires a verified tract crosswalk and a fresh
aggregation, including uncertainty. A direct 2024 Census API query did not return
usable JSON during this research. No newer neighborhood count was invented.

The names are the official **Analysis Neighborhoods**: Mission and South of
Market. Planning's [2020 tract-to-neighborhood mapping](https://data.sfgov.org/d/sevw-6tgi)
documents how tract boundaries map to these statistical neighborhoods. They are
not plan-area boundaries, ZIP codes, or the simulation's viewport. South of Market
does not absorb separately named Mission Bay or Financial District/South Beach;
Mission is separate from Outer Mission. This implementation uses DataSF's existing
aggregation and does not perform an undocumented spatial overlap calculation.

The [Planning Department neighborhood-profile repository](https://github.com/sfcpc/san-francisco-neighborhood-profiles)
and [2012–2016 profile methodology](https://default.sfplanning.org/publications_reports/SF_NGBD_SocioEconomic_Profiles/2012-2016_ACS_Profile_Neighborhoods_Final.pdf)
were also checked. Their older population numbers were not mixed into the age
calibration; employment uses a separately labeled older proxy, detailed below.
The source age labels follow Census [B06001](https://api.census.gov/data/2023/acs/acs5/groups/B06001.html);
all-population totals use B01001_001E. B06001's **total** age cells 002–012 are used,
not its place-of-birth subgroups.

| Geography | All residents | Excluded ages 0–17 | Adults 18+ |
| --- | ---: | ---: | ---: |
| Mission | 54,431 | 6,787 | 47,644 |
| South of Market | 24,698 | 1,774 | 22,924 |
| Combined target | 79,129 | 8,561 | 70,568 |

These are sums of published estimates. All-age neighborhood margins of error are
approximately ±2,367 and ±1,567 respectively; exact source precision remains in
the JSON. The same-vintage **citywide context** is 836,321 for San Francisco
County, also from DataSF B01001_001E. It is never used as a neighborhood sampling
denominator. Employers, job sites, commuters, and visitors add no residents.

## Adult age targets and default realization

The four broad age groups are sums of disjoint published age cells. This grouping
keeps a 12-person simulation interpretable while preserving the original finer
age estimates in the snapshot. Adult neighborhood shares are 47,644/70,568 and
22,924/70,568. Each neighborhood's age shares use its own adult denominator.

| Neighborhood | Adult age | Estimated residents | Default agents (12, seed 17) |
| --- | --- | ---: | ---: |
| Mission | 18–34 | 16,016 | 3 |
| Mission | 35–54 | 19,425 | 3 |
| Mission | 55–64 | 5,353 | 1 |
| Mission | 65+ | 6,850 | 1 |
| South of Market | 18–34 | 9,759 | 2 |
| South of Market | 35–54 | 6,839 | 1 |
| South of Market | 55–64 | 2,460 | 0 |
| South of Market | 65+ | 3,866 | 1 |

Allocation uses Hamilton/largest remainder first for neighborhoods and then for
age within each neighborhood. Remainders use exact integer arithmetic; ties and
final ordering use a private seeded RNG. The report gives unconditional expected
sample counts as well as the conditional age targets after neighborhood rounding.
It does not promise that both global age margins and neighborhood margins can be
rounded independently and exactly at every small sample size.

Within a broad band, a published finer age cell is drawn proportionally to its
count, then an integer age uniformly within that cell. This exact-age distribution
is an **assumption**, not a Census measurement. The open-ended 75+ cell uses the
explicitly assumed range 75–100. Its entire source mass is retained, but the
simulation cannot express ages above 100. This does not assert that nobody is
older than 100.

## Circumstances, privacy, and uncertainty

Every profile contains neighborhood, age, age_band, housing_status,
employment_status, occupation_sector, and English background statements. Housing
is `"unspecified"`. A household-tenure percentage is not the fraction of individual
adults renting. Employment and occupation use the explicit proxy below; callers
must label added housing, income, or family circumstances as scenario assumptions.

Residence duration and mundane past experiences are explicitly invented facts
about synthetic people, marked in `assumed_metadata`. They are sampled independently
of demographic identity. No personal microdata, real names, addresses, permanent
goals, personality labels, values, or race-to-behavior mapping are included.
Unique synthetic IDs identify generated profiles, not real residents. Different
seeds create different ages, experiences, durations, and ordering; profiles are
not copies of a fixed cast.

The report retains source uncertainty and labels root-sum-square combinations
of source margins as approximate 90% margins: covariance is unavailable. It does
not propagate uncertainty into target proportions or treat generated precision
as statistical confidence. As the [Census guidance](https://www.census.gov/programs-surveys/acs/guidance/estimates.html)
explains, five-year estimates trade temporal currency for precision at small
geographies. Nonresponse, coverage error, and boundary definitions remain limits.

Each represented stratum has an expansion weight equal to its adult estimate
divided by its realized agent count. Empty strata have `null` weights, never
infinite or silently redistributed weights. At the default 12 agents, the 2,460
estimated SoMa adults aged 55–64 are unrepresented; weights sum to **68,108**
represented adults, not the full 70,568. These descriptive weights are not
survey inclusion probabilities and must not multiply API calls, purchases,
resources, or simulated actions. The model is an illustrative adult population,
not a probability survey, household reconstruction, or behavioral forecast.

## Employment and occupation proxy

Resident employment comes from SF Planning's
[Neighborhood_profiles_by_geo_2020.csv](https://raw.githubusercontent.com/sfcpc/san-francisco-neighborhood-profiles/main/output/Neighborhood_profiles_by_geo_2020.csv),
using **2016–2020 ACS five-year estimates**. The
[construction notebook](https://github.com/sfcpc/san-francisco-neighborhood-profiles/blob/main/Master%20Table%20Constructor.ipynb)
sets year=2020 and its [attribute lookup](https://raw.githubusercontent.com/sfcpc/san-francisco-neighborhood-profiles/main/lookup_tables/attribute_lookup.csv)
specifies each numerator and denominator. Direct newer Census API requests
redirected to a missing-key page; no credentials were accessed. No neighborhood
employment dimensions are exposed in the DataSF snapshot used for age.

| Published metric | Mission | South of Market | Denominator |
| --- | ---: | ---: | --- |
| Labor force participation | 0.792694469663312 | 0.6979664552011818 | Residents age 16+ |
| Column labeled Unemployment Rate | 0.0407966157352856 | 0.02672286434344312 | Residents age 16+ |
| Civilian employed residents | 38,922 | 15,406 | Count of civilian employed residents 16+ |

**The published unemployment label is misleading:** its lookup defines
B23025_005 / B23025_001, not the conventional unemployed / civilian-labor-force
rate. The implementation uses that actual definition. Synthetic status shares
are participation minus unemployed for `employed`, the published unemployed
share for `unemployed`, and one minus participation for `not_in_labor_force`.
The source 16+ denominator count is not supplied in this extract and is not
fabricated. B23025 participation includes Armed Forces, so the employed proxy
includes that group; it is not an exact civilian employment rate.

Among employed profiles, five **occupation groups** use C24050 cells 015, 029,
043, 057, 071 divided by C24050_001: management/business/science/arts; service;
sales/office; natural resources/construction/maintenance; and
production/transportation/material moving. Despite the API field name
`occupation_sector`, these are occupations, **not industries or workplace job
counts**. Non-employed profiles have a null occupation. Exact source fractions
remain in the JSON; no industry or named employer is invented.

These older 16+ marginals are explicitly **proxies** applied to the 18+ sample.
Employment is assigned independently of age within neighborhood, and occupation
independently of age among the synthetic employed profiles. This transfers
civilian occupation shares to an employed proxy that also includes Armed Forces.
These choices are scenario assumptions, not a measured joint distribution or
current labor-market forecast; in particular, they cannot reproduce age-specific
retirement. No margins of error are supplied in the Planning extract. Source
values, denominators, target shares, realized counts, and assumptions are exposed
under `report.employment_calibration` and each profile's `assumed_metadata`.

Largest remainder separately assigns employment and occupation counts, using a
seeded RNG isolated from age generation. The default sample has nine employed
profiles; very small unemployment shares can round to zero and the report shows
that outcome. Age expansion weights do **not** also calibrate employment or
occupation. Backgrounds add the assigned present work circumstance without
permanent goals or behavioral traits.

## Validation and refresh

Run `python -m pytest tests/test_population.py`. Tests cover exact counts,
reproducibility without global RNG side effects, official denominator
reconciliation, largest-remainder quota bounds, weights and uncovered strata,
adult ranges, explicitly unmeasured fields, and varied synthetic backgrounds.

For a refresh, inspect the DataSF vintage inventory, retrieve matching total/age
rows for both neighborhoods, retain the exact query and margins, and verify all
age cells sum to each total. Update this document and the source-anchor tests
together. Do not relabel the historical snapshot as current or combine its
neighborhood totals with a newer citywide denominator.
