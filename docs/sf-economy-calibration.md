# SF economy calibration and feedback

The SF scenario now uses one coherent budget scale for earnings, housing and purchases, with explicit source levels and synthetic distributions. This is an illustrative adult resident sample, not a forecast, benefits calculator, housing market model or representation of any real company's finances. The prototype scenario keeps its existing economy rules.

## Official evidence, checked September 8, 2026

| Source | Observations used | Scope and use |
| --- | --- | --- |
| [Census QuickFacts, SF city](https://www.census.gov/quickfacts/sanfranciscocitycalifornia) | ACS 2020–2024 median household income $140,970; median gross monthly rent $2,476; owner-occupied share 38.2%; 2.21 persons per household | Citywide household/housing-unit anchors. Household income is never assigned to every individual as salary. Owner share and household size remain context; the adult sample cannot reproduce family composition. |
| [BLS May 2024 metro occupational wages](https://www.bls.gov/regions/west/news-release/2025/occupationalemploymentandwages_sanfrancisco_20250501.htm) | Occupational mean hourly wages, including computer/mathematical $78.40, food preparation $22.30, healthcare support $21.70 | SF–Oakland–Fremont employer jobs, not SF-city jobs or Mission/SoMa resident workers. Selected occupational levels are proxies for broad scenario roles. Individual spread and occupation-to-industry mapping are assumptions. |
| [SF OLSE wage history](https://media.api.sf.gov/documents/2026_Historical_San_Francisco_Minimum_Wage_Rates_M9ynRNo.pdf) | Standard minimum $19.61/hour effective July 1, 2026 | Baseline wage floor; exceptions and specialized wage rules are outside this model. |
| [SF 2024 PIT report](https://media.api.sf.gov/documents/2024_San_Francisco_Point-in-Time_Count_Report_8_13_24.pdf) | 8,323 people counted on January 30, 2024 | Context only. A one-night citywide count is neither annual prevalence nor an adult neighborhood household rate. It is never divided by the resident denominator or used to force an unhoused quota. |

The original [SF Planning employment source](https://raw.githubusercontent.com/sfcpc/san-francisco-neighborhood-profiles/main/output/Neighborhood_profiles_by_geo_2020.csv) and DataSF population source remain in `sf_population.json`. Resident age counts use ACS 2019–2023; employment proxies use ACS 2016–2020 age 16+ marginals. This intentionally mixed-vintage calibration does not claim a current measured joint distribution. All newly used source values and assumptions are checked into `data/sf_economy.json`; runtime makes no network calls.

## Budget mapping

One credit represents $25 of purchasing power, and one game day represents one calendar budget day. The simulation clock compresses that day; the mapping does not equate a short animation to an hourly timesheet.

- Annual gross salary = hourly proxy × 40 assumed hours/week × 52 weeks.
- Daily net wage credits = annual gross salary × 0.78 assumed take-home fraction ÷ 365 ÷ 25.
- Daily household rent credits = monthly gross rent × 12 ÷ 365 ÷ 25.
- A $2,476 monthly rental costs about 3.26 credits per household per budget day. Residents of the same synthetic household share the exact cents; a large visual apartment building can contain several households.
- Two completed baseline work shifts earn one daily wage. Starting, canceling, repeating completion, or reaching midnight does not also pay salary. The daily count covers all baseline employers combined; starting a company retains the original treasury-funded per-batch contracts.
- Market food costs an assumed $10, or 0.40 credits. Free community meals remain available while stocked.

The take-home fraction is a flat scenario approximation, not a tax calculation. Wage levels are gross 2024 occupational proxies with a 2026 floor; no inflation series is inferred. The household median is a reference for comparing aggregate sample circumstances, not a target forcibly matched in a small sample.

## Starting circumstances and privacy

`economic_profiles(profiles, seed)` provides reproducible wage, liquid reserve and nonlabor support fields. Wages have a bounded lognormal multiplier around occupational levels; rent has a separate bounded spread around the citywide median. Households contain one to three synthetic adult residents grouped within the available map housing, with a fresh household for each voluntary solo rental. Neither family ties nor actual property capacities are inferred.

Liquid reserves range from zero to 120 days of assumed income; non-employed profiles may receive zero or varying recurring support. These distributions are deliberately labeled assumptions, including zero support; they are not measured savings, benefit eligibility, retirement income or claims about specific groups. Income, savings and housing do not set personality, values, intelligence, dangerousness, goals or ambitions. The generator preserves its source age/employment weights; weights never multiply physical money or work actions.

Initially all residents with sample rooms have rental tenancy; there is no forced homelessness share. Some have little cash or a high rent burden. Failure to earn, insufficient support, voluntary household changes and actual workplace closure can create arrears. Sustained unpaid costs may end a tenancy after a documented 60-budget-day scenario threshold, not a claim about SF legal eviction timing. Debt persists across moves and roommate acceptance. Payments use available cash, cannot make balances negative, and first-day rental prepayment is credited at the next settlement.

`context_for(agent)` exposes only that citizen's economic ledger and current affordability. `report()` exposes aggregate sample counts and source metadata, without individual balances, household membership or employer payroll. Raw per-agent finance state is private checkpoint material.

## Operational feedback

Baseline employers pay completed shifts from an explicitly counted external monetary inflow. This is not represented as a negative spendable city treasury. Nonlabor support is separately counted; rent and shop receipts go to the existing city account. Company materials, payroll, investment, sales and dividends retain the existing reservation and transfer rules.

Fictional companies pay a small explicit daily overhead from available treasury. A company that cannot fund materials and makes no sales for three budget days closes, provided no production reservation is active. Recent sales or adequate working capital reset that condition. Closure clears employee contracts, removes matching workplace assignments, rejects new trades/work/offers and emits a real event. Remaining treasury is retained in the closed company's record; bankruptcy liquidation and creditor priority are not modeled. Real catalog firms have no invented treasury or profitability: only an actual closure flag/removal causes their assigned workers to lose jobs.

Food and retail shifts add consumable meals to open outlets. Public-service shifts improve a toilet or kitchen's condition. Healthcare shifts replenish finite clinic care units; `rest` targeting a clinic consumes a unit and restores health/energy. Care is a simple game resource, not clinical treatment. Shops receive a documented finite daily external food supply, scaled to physical sample size; service work adds supply and external restocking preserves stock up to capacity. Basic aid, clinics, toilets and open-shift locations are initially known so essential survival does not depend on finding hidden resources.

## Employer counts and commuters

The catalog retains unknown site/local staffing as null. Existing Salesforce/Google 2025 citywide reported estimates remain historical contextual estimates, never site staffing or resident employment shares. Normal allocation retains the existing 25% named-example ceiling and sector matching without headcount weighting.

`allocate_supplied_local_counts(profiles, observations, seed)` is an optional explicit path for a supplied resident-worker or inbound-commuter cross-tab. Each row requires `employer_id`, integer `count`, matching `population_role` and `scope`, positive `denominator`, `source_url` and `as_of`. Resident rows require scope `resident_workers`; commuter rows require `inbound_commuters`. Citywide/global scope, missing counts, duplicate employers, incompatible denominators and overfull totals are rejected. Quotas are floored and sector matched, with unfilled/residual agents kept generic and reported. Supplied evidence is trusted caller input, not automatically verified by this helper. No commuters are created by default, and commuter observations cannot change the resident expansion denominator.

## Integration and persistence

1. After `seed_sf_scenario` finishes agents, objects and map placement, call `apply_sf_economy(world, seed)`. Repeated calls are idempotent and do not reset balances.
2. Root's daily hook calls `world.urban.new_day()` once, then `world.sf_economy.new_day()` instead of the legacy rent block. The latter is idempotent per budget day.
3. `Economy.tick()` invokes `world.sf_economy.tick()` to observe actual workplace closure. `UrbanSystem` owns shift completion and service supply.
4. Add `world.sf_economy.context_for(agent)` to private decision/inspector context and `world.sf_economy.report()` to public calibration summaries. Explain clinic rest and daily shift caps in action help.
5. Persist `world.economy.sf_state` as plain JSON plus Company/Offer fields. Restore with `world.sf_economy = SFEconomy(world)` after Economy exists; do not call the seeding helper on restore. The facade has no mutable state beyond its world reference.
6. Disable scripted SF layoffs/rent-news if present; these economics do not need predetermined adverse events.

## Verification and remaining limits

The focused suite covers currency consistency, spread/floors, idempotent seeding and JSON restoration, completion-only capped wages, cancellation, nonnegative balances, exact shared household charges, partial payments and debt recovery, prepaid moves, closure/job loss, consumable care/food and private context. Population and employer tests verify unchanged resident weights and separation of supplied commuter denominators. Existing prototype economy tests remain part of the regression run. No model calls, servers, credentials, environment changes or commits are needed for these tests.

Validation: `.venv/bin/python -m pytest tests/test_sf_economy.py tests/test_economy.py tests/test_population.py tests/test_employers.py tests/test_sf_scenario.py -q` passes 79 tests. Ruff passes for all eight owned Python/test files, and `git diff --check` passes. The SF integration check also caught an existing authorization check occurring after travel; assigned-workplace eligibility is now checked before routing, including on the new entrance-based map.

Remaining limits: household tenure/size and income-rent joint distributions are not fitted; the sample is adults only; subsidies and outside demand are stylized; support is not means-tested; no commuting journeys, actual company wage bills, mortgage assets, landlord budgets, taxes or housing supply response are modeled. Clinic and food capacity are game assumptions. The model exposes tradeoffs and responds to actual actions but does not guarantee either prosperity or dramatic decline.
