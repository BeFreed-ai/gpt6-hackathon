# SoMa and Mission employer evidence

Verified on September 8, 2026. The checked-in catalog contains 19 actual workplace
locations across eight sectors. It is a curated set of examples, not a complete
business registry, neighborhood employment estimate, current attendance count,
or list of where real residents work. Code uses only the standard library and
reads the local JSON; no network, credentials, geocoder or external API is needed.

## Geography and schema

`load_employers()` returns independent dictionaries with `id`, `name`,
`neighborhood`, `sector`, `address`, `latitude`, `longitude`, `local_headcount`,
`headcount_scope`, `headcount_year`, `sources`, and `confidence`.

- Neighborhood labels are `soma` and `mission`. The population's reference area
  is the official Mission and South of Market analysis neighborhoods, while the
  employer catalog has a broader catchment. A point-in-polygon check against
  [DataSF Analysis Neighborhoods](https://data.sfgov.org/resource/j2bu-swwd.geojson)
  places Salesforce, Google Spear, SFMOMA and YBCA in Financial District/South
  Beach. These four retain a broad `soma` display label and explicitly have
  `within_resident_reference_area: false`. Their locations cannot support
  census-footprint-matched employment allocation. All records include the actual
  analysis-neighborhood name in `reference_geography` and the check's basis.
  Rainbow and Costco's map points fall in Mission and use `mission`; their common
  association with SoMa does not override this check. ZSFG is also in Mission.
  Classifications use the listed, mostly approximate points, not verified
  parcel locations; near-boundary sites merit rechecking with a precise geocode.
  Mission Bay is a separate neighborhood, not interchangeable with Mission.
- Sectors describe the workplace's principal activity, not every employee's
  occupation: a hospital also employs administrators and maintenance workers.
  The eight sectors are technology, healthcare, food_service, retail, education,
  arts, public_service, and professional_services.
- All map points are manually approximate, explicitly marked by
  `coordinate_precision` and `confidence.coordinates`, except the CCSF Mission
  point published in its official campus map. They are not verified entrances,
  parcel centroids, property boundaries or navigational coordinates.
- `sources` is a list of `{url, title, supports, accessed_on}` dictionaries.
  `confidence` separates address, headcount and coordinate confidence. An official
  address does not imply that the number of workers is known. `verified_on` is the
  research date, never a substitute for the count's `headcount_year`.
- `local_headcount: null`, `headcount_scope: "unknown"`, and
  `headcount_year: null` mean the research did not establish a numeric local
  workforce. Null does not mean zero or closed. For the two supported citywide
  counts, scope is `san_francisco_city`, with explicit `site_headcount: null`.
  Consumers must show count and scope together; these counts never represent
  occupancy at the listed address.
- `headcount_status` is `estimate` for the two republished city figures and
  `unknown` elsewhere; none is claimed to be an audited payroll count.

## Sources and findings

| Workplace | Verified local address | Workforce evidence |
| --- | --- | --- |
| [Salesforce](https://www.salesforce.com/company/locations/) | 415 Mission Street | 8,500 in SF city, January 2025; office count unknown. |
| [Google](https://about.google/company-info/locations/) | 345 Spear Street | 4,000 in SF city, January 2025; office count unknown. Official directory also lists other SF offices. |
| [Adobe](https://www.adobe.com/about-adobe/contact/offices.html) | 601 Townsend Street | Unknown locally; directory also lists 100 Hooper, so even an SF total would not be Townsend occupancy. |
| [Airbnb](https://www.sec.gov/Archives/edgar/data/1559720/000155972025000010/abnb-20241231.htm) | 888 Brannan Street | 2024 Form 10-K establishes principal executive offices and approximately 7,300 employees **globally** at December 31, 2024. Local count stays null. |
| [Rainbow Grocery](https://rainbow.coop/) | 1745 Folsom Street | Unknown exact dated count; worker-owned cooperative. |
| [Costco](https://www.costco.com/warehouse-locations/warehouse-144.html) | 450 10th Street | Warehouse workforce unknown. |
| [Bi-Rite Market](https://biritemarket.com/visit-us/) | 3639 18th Street | Store workforce unknown; do not assign a group total to one store. |
| [Dandelion Chocolate](https://www.dandelionchocolate.com/pages/valencia-street) | 740 Valencia Street | Cafe workforce unknown; other locations are not counted here. |
| [Tartine Bakery](https://tartinebakery.com/san-francisco/bakery) | 600 Guerrero Street | Bakery workforce unknown; no Bay Area or brand-wide total imported. |
| [SFMOMA](https://www.sfmoma.org/about/contact-us/) | 151 Third Street | Workforce unknown; arts workers include visitor services and operations. |
| [Yerba Buena Center for the Arts](https://ybca.org/campus/) | 701 Mission Street | Workforce unknown; campus also has theater entrance at 700 Howard. |
| [Brava for Women in the Arts](https://www.brava.org/support) | 2781 24th Street | Workforce unknown; performer and volunteer counts would not establish employees. |
| [ZSFG](https://www.zuckerbergsanfranciscogeneral.org/about-us/) | 1001 Potrero Avenue | Current exact site workforce unknown. Hospital, UCSF and SFDPH populations must not be conflated. |
| [Mission Mental Health](https://media.api.sf.gov/documents/Provider_Directory_MH_Part_1_-_Program_Info_English_Dec_2025.pdf) | 2712 Mission Street | December 2025 SF provider directory, printed p. 16; clinic workforce unknown. |
| [Equity Health / South of Market Health Center](https://hcai.ca.gov/facility/south-of-market-health-center/) | 229 7th Street | HCAI lists an open clinic. Workforce unknown; [clinic consortium](https://www.sfccc.org/equity-health) confirms current operating name. |
| [CCSF Mission Center](https://www.ccsf.edu/about/our-locations/mission-center) | 1125 Valencia Street | Workforce unknown; enrollment is not staff. [Official map](https://www.ccsf.edu/about/our-locations/map/mission) supplies coordinates. Homepage's 94110 postal code takes precedence over map's inconsistent 94112. |
| [SFPL Mission temporary branch](https://sfpl.org/locations/mission) | 1234 Valencia Street | Official page says 300 Bartlett is closed for renovation; branch workforce unknown. |
| [SFFD Station 1](https://sf-fire.org/fire-station/san-francisco-fire-station-1) | 935 Folsom Street | Station workforce unknown; a shift crew would not be total employees. |
| [La Raza Centro Legal](https://www.lrcl.org/) | 474 Valencia Street, Suite 295 | Legal-services nonprofit workforce unknown. |

The SF-city figures above come from the city's [2025B bond disclosure, Appendix
A-5, PDF page 109](https://media.api.sf.gov/documents/City__County_of_San_Francisco_IRFDNo.1_TIRB_Ser2025B_POS.pdf).
The city republishes the San Francisco Business Times January 3, 2025 table; it
is not a new official payroll enumeration. The disclosure warns that subsequent
announced workforce reductions are excluded. Accordingly confidence in these
historical city figures is medium, and neither is presented as a current building
count. The same table gives Sutter Health 6,000 across SF: it does not establish
staffing at a particular hospital. No city totals are summed into neighborhood jobs.

[Rainbow's own history](https://rainbow.coop/about-rainbow/) describes growth to
more than twice roughly 85 workers after its 1996 move. This establishes a
substantial non-tech workplace, but cannot justify an exact current count of
170, 250, or any other integer. Its local count remains null.

Airbnb's SEC global workforce observation is retained separately in
`headcount_observations`, marked `scope: "global"` and
`used_for_allocation: false`. Its approximately 11,000 third-party support workers
are a different global population and are not added to its employees or assigned
to San Francisco. Global, Bay Area/metro, SF city, and site figures are different
geographies. None can be substituted for another without evidence.

## Establishments, jobs, and residents

The [SF Registered Business Locations dataset](https://data.sfgov.org/Economy-and-Community/Registered-Business-Locations-San-Francisco/g8m3-pdis)
records one row per registered location, and one business can have several rows.
These are registrations, not workers. A count of active rows does not measure
jobs, a registered mailing address does not prove daily attendance, and an
establishment count cannot weight employers by staffing. Administrative closures,
location closures, dates and coverage require care before deriving even an
establishment total. This catalog does not claim to exhaust that registry.

Resident demographics and workplace demographics have different denominators.
People can live in the Mission and work in SoMa, elsewhere in SF, outside SF, or
at home; commuters can work here without living here. A neighborhood's resident
employment rate is not its share of local jobs. The Census [LODES/OnTheMap
documentation](https://lehd.ces.census.gov/applications/help/onthemap.html) and
[commuting program](https://www.census.gov/topics/employment/commuting.html)
distinguish residence and work locations. A future calibrated allocator needs
compatible geography/year residence-workplace flows and workplace employment
data, with coverage and remote-work limitations disclosed. This catalog does not
claim that calibration.

## Offline allocation and integration

`allocate_workplaces(profiles, seed=17)` returns a same-length list of IDs or
`None`. Only exact `employment_status == "employed"` is eligible. It reads
`occupation_sector`, falling back to `sector`; missing sectors become `other`.
Sector labels are normalized to lowercase ASCII words separated by underscores.
Unrepresented sectors keep their own generic ID, such as `sector_construction`.

The allocator initially gives each employed profile `sector_<sector>`. It then
selects at most `floor(0.25 * sector_matched_employed_profiles)` profiles and
assigns each a uniformly sampled named site from the same sector. The 25% ceiling
and uniform selection of examples are **scenario assumptions**, recorded in JSON
and the report helper. They are not measured market shares, estimates of worker
counts, or conclusions drawn from the number of catalog entries. Fewer than four
matched employed profiles therefore produce no named assignments. Residential
neighborhood does not constrain a work location. Unknown headcounts are eligible
on the same basis as known ones, without fabricating staff numbers.

No company receives a per-company guessed headcount or global/metro count as a
weight. Even the documented SF-city counts are excluded: there is no defensible
complete, comparable set of site counts for these named locations. Preserving
generic workplaces for at least 75% avoids claiming the short catalog contains
most residents' employers. The sampling is for illustrating workplaces only;
it does not estimate employment distribution, vacancies, hiring or capacity.

The main-world adapter should create `sector_` workplaces as generic sector
facilities and named IDs as these catalog sites. Simulation worker assignments
must remain separate from published headcounts and from agent-founded companies.
No real person is identified or asserted to work for an employer here.

`catalog_report()` (also `employer_report()`) and `python -m app.employers` report
coverage by neighborhood/sector and count scope, contextual sites and limitations,
without summing incompatible totals. `python -m pytest tests/test_employers.py`
checks deterministic eligibility, sector matching, generic coverage, evidence
schema, input immutability, null handling, and independence from global or city
headcount values.
