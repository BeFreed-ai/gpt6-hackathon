# Public-figure character backgrounds

`data/public_figure_backgrounds.json` is the checked-in background source packet
for simulated Sam Altman and Dario Amodei. It contains selected public career
events and paraphrased public positions, with source IDs, URLs, publication dates
where verified, and an access date of 2026-09-08. It is not a complete biography,
a scraped full-text corpus, a psychological profile, or a behavioral prediction.

The sources include Y Combinator's announcement and interview transcript,
OpenAI's founding and CEO-return announcements, Altman's own essays, Amodei's
personal biography and essay, and Anthropic's leadership page. Secondary
biographical sources are used only for age: Sam's age is calculated from his
reported birth date; Dario's age of 43 is explicitly approximate from birth year
1983 because an exact birthday was not verified.

Historical entries are labeled PUBLIC CAREER, PUBLIC EDUCATION, PUBLIC POSITION
or PUBLIC SELF-REPORT. Opinion and forecast are not promoted to objective fact.
No complete essays, private contact information, home addresses, sensitive
private history or real-person financial balances are stored. No authenticated
social-profile scraping is required.

The characters occupy two of the 100 slots, not two additional agents. This
intentional casting and the selected employer quotas are scenario assumptions,
not representative sampling or measured company staffing. Sam's workplace role
is OpenAI; Dario's is Anthropic. Game housing, finances and physical conditions
remain fictional. Their historical backgrounds do not give them control over
real companies, special powers, mandatory goals or access to unseen world events.

`AgentBackground.public_figure` preserves source metadata through typed world
checkpoints. The click-only inspector displays a PUBLIC-FIGURE SIMULATION notice
and source links. Their future dialogue and behavior are fictional outputs and
must not be attributed to the actual people.

The source file is intentionally data-only. The population generator owns role
casting and assignment, and the same private-history runtime used by other
citizens governs subsequent experience. No LLM call is needed to seed these
backgrounds.
