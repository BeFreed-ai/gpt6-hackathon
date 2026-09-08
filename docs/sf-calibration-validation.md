# SF calibration validation — September 8, 2026

## Implemented and checked

- Offline population generation and immutable checked-in source snapshots.
- Default resident sample: 8 Mission, 4 South of Market; 9 employed proxies,
  3 outside the labor force. Zero unemployed in this tiny rounded realization
  does not mean the source unemployment share is zero.
- Private synthetic backgrounds reach only the citizen's model context and
  click-only observer detail. Starting memories are stored individually.
- Resident age targets, employment proxies and scenario employer allocations
  have separate denominators and assumptions.
- 19 employer reference sites across eight sectors; four are contextual sites
  outside the resident geography. Two historical SF-city reported estimates,
  17 unknown local headcounts, and no measured company-staffing allocation.
- Existing jobs require assignment before work pays; citizen-founded companies
  remain separate from externally funded reference workplaces.
- SF mode no longer injects prototype layoffs, street fairs or rent rumors.
- 103 automated tests passed. Ruff, JavaScript syntax and diff checks passed.
- Desktop browser verified the calibration panel, two population denominators,
  source vintage, employer scopes and unknown counts, plus click-only biographies.
  The smoke script also captures a mobile view.

## Initial Astra API test: blocked, not passed

A separate preview on port 8003 was observed for 60 seconds without interventions
or staged goals. Its clock advanced to 60.0 seconds, but **zero Astra decisions
succeeded**. A separate minimal request with retries disabled returned HTTP 429,
`code=credit_balance_exhausted`, `type=insufficient_quota`, and no Retry-After.
No credentials or raw provider responses were logged.

The preview was paused after the observation. Earlier worlds on other ports were
not reset or paused. No provider/model substitution, billing action or credential
rotation was attempted during that test. API account funding is required before
repeating the Astra test:

```sh
uv run --with playwright python scripts/smoke_sf_population.py --seconds 60
```

## Novita follow-up

At the user's request, a separate Novita DeepSeek V3.2 preview on port 8004 was
observed for 60 seconds. It produced 25 real LLM decisions across all 12 residents,
including two completed paid shifts and conversations, with no observed provider
or browser errors. It was paused after the bounded observation. Earlier worlds
were left untouched. Credentials were loaded from AWS Secrets Manager.

The user subsequently requested a stronger DeepSeek model. The configuration now
selects `deepseek/deepseek-v4-pro-0813`, verified in Novita's live model catalog.
Its API rejects `json_schema` despite the catalog feature listing; V4 requests
therefore use `json_object`, a schema in the prompt, and the same mandatory local
schema validator. Default reasoning is retained with an 8,192-token completion
budget. Reasoning text is not treated as a world action or public self-report.
The V3.2 observation above is not evidence of V4 simulation performance.

A separate V4 preview on port 8005 passed the browser integration smoke test:
30 wall-clock seconds, 29.8 simulated seconds, one completed real LLM decision,
and no observed provider or browser errors. It was paused after the test. This
confirms basic compatibility, not all-resident progress or acceptable throughput;
the scheduler and simulation time scale need a longer latency-aware evaluation.
The updated automated suite passed all 118 tests.

These checks do not validate long-run survival, demographic realism of behavior,
emergence or consciousness. The actual street reference is still separate from
the schematic playable layout. Real housing, salary distributions, commuting,
company staffing and multi-project life planning remain uncalibrated or unimplemented.
