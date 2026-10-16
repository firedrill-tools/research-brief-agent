# Working rules

Use only synthetic source documents. Keep every generated brief tied to the actual LlamaIndex source nodes returned by the query engine, and expose contradictory source claims. A numbered citation marker is not proof that its claim is entailed; do not call a draft verified.

Tests using `MockLLM` are offline evidence only. Do not claim a live Gemini run without the API call and output. Add Firedrill integration only against the new qualified release.

Preserve every returned source-node ordinal before mapping citations. Unknown IDs must remain visible and require review; never drop them and renumber later known nodes. Retain valid cited evidence alongside invalid markers. Current ten checks include actual Response/NodeWithScore mapping regressions, but native Gemini completion/usage/ownership, richer hash-bound data and package qualification remain follow-up work in PLAN.md.
