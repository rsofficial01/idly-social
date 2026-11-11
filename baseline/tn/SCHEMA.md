# idly baseline: Tamil Nadu (schema)

The baseline is what idly already knows and has sourced about Tamil Nadu's government and politics. Every local
story is checked against it before it is written, so a fresh headline is read in context and contradictions are caught.
This repository is public: only sourced facts about public figures and public bodies. No private individuals.

All files are JSON arrays. Every item has `id` (kebab-case, unique in its file), `sources` (list of
`{"outlet": "...", "date": "YYYY-MM-DD or text", "url": "https://..."}`; at least one, copied from the report, never
invented), `as_of` ("YYYY-MM-DD"), `keywords` (lower-case words and names a news story would use for this item, in
English, Tamil script and common Latin-script Tamil; include party and person names, scheme names, nicknames of schemes),
and `status`: one of `verified` (two or more sources or a primary record), `single_source`, `disputed` (sources differ;
put every figure in `alt_values`), `alleged` (no court finding; `response` is then required).

people.json   {id, name, aliases[], role, party, portfolio, since, prior_experience, facts[] (short sourced strings), status, sources, as_of, keywords}
facts.json    {id, topic (formation|cabinet|officers|finance|deals|economy|welfare|law_order|centre_state|caste_religion|quality_of_life|elections|history_2021|history_2016|history_2011|outlook), statement (one plain sentence), value, unit, alt_values[], status, response?, sources, as_of, keywords}
promises.json {id, party, promise, promised, current, verdict (delivered|partly|started|not_started|could_not_verify), annual_cost, status, sources, as_of, keywords}
ledger.json   {id, party, showcased, followed, legal_status, response, status, sources, as_of, keywords}
watch.json    {id, when (date or window), what, why, status, sources, as_of, keywords}

Never include: any drug-trafficking claim against Sabareesan; any suggestion that a party caused the 2025 Karur stampede;
unnamed-source allegations; the names of private individuals (use roles, e.g. "a TVK district functionary" is fine only
if outlets named him as a party office-bearer; otherwise describe without a name); anything the report lists under
"What we could not verify".
After writing a file, run: python3 -c "import json;d=json.load(open('<file>'));print(len(d))" and fix any error.
