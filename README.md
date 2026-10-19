# Research brief agent

A standalone LlamaIndex/Gemini application that retrieves controlled fictional documents and drafts a sourced brief. It uses an actual CitationQueryEngine with async refinement and the GoogleGenAI integration. Local lexical retrieval needs no embedding service. Source disagreements, invalid attribution and missing evidence remain visible.

## Run

Python 3.12+ and uv:

```sh
uv sync --locked --extra test
uv run --locked research-brief --list-cases
uv run --locked research-brief --init-case busy --sources /tmp/my-research-sources.json
uv run --locked research-brief --case no-match
```

These commands need no model key. A live brief requires explicit Developer API credentials and a model enabled for your account. Export `GOOGLE_API_KEY` and `GEMINI_MODEL`, then:

```sh
uv run --locked research-brief --case starter
uv run --locked research-brief --case contradictory-surveys
uv run --locked research-brief 'Summarize Helio support evidence.' --sources /tmp/my-research-sources.json --top-k 5 --timeout 60
```

`--model` overrides GEMINI_MODEL; there is no assumed default model. `--base-url` accepts an explicit HTTPS or loopback HTTP Developer API endpoint. Ambient Vertex/enterprise selection is rejected. The application never reads a production connector or web-search source. `.env.example` documents variables; the CLI does not automatically load .env files.

Custom JSON accepts a legacy array of strict source records or the versioned synthetic wrapper shown in data/cases. Fields include unique source_id, title, published ISO date, topic, nonempty tags and text; optional method/sample_size and claim_key/claim_value. Claim keys must describe the same metric, population and period if differing values should count as a conflict. Free-form contradictory text still needs human or semantic review.

## Sources and output

The original question goes to a fresh local retriever. Topics with the highest token overlap are retained, then documents are ranked and capped by top_k. The receipt exposes ties, scores and truncation; lexical selection is not exhaustive semantic retrieval. Synthesis directions live in LlamaIndex templates. Source method, sample size and date are rendered with each body; manifest focus descriptions stay outside model context.

The result exposes recognized `source_ids`, every actual source-node ordinal in `citation_map`, and valid `cited_source_ids`. Unknown nodes never shift citation numbers. Unknown/out-of-scope identities, forged chunks, invalid markers, unobserved full context or encoded conflicts require review. Valid cited evidence survives alongside errors. No match returns `insufficient` without a model call.

`draft` means the attribution checks passed and no encoded conflict was found. It does not prove that each prose claim follows from its citation. Whitespace-normalized chunk correspondence and observed prompt text are evidence for inspection, not entailment or a semantic benchmark. Live Gemini and human review must assess weak evidence, unsupported conclusions and hostile source behavior.

## Execution evidence

Every run writes a private `.runs/<uuid>/receipt.json` (new directories 0700, file 0600); `--output-root` changes the root. Receipts include actual versions, source/template/question hashes, retrieval population, original returned chunks and raw brief, prepared request bodies, decoded HTTP responses before SDK validation, model/response/request IDs, SDK lifecycle events, completion flags and reported usage. These files can contain the source and generated business text; treat them as private. Provider headers and credentials are not recorded.

Missing/partial/invalid usage is unknown; reported zero remains zero. Counts are preserved independently, including failed attempts. Cost is null. Synthetic HTTP counts are test fixtures and do not measure provider execution or billing. A source file changed during generation or an evidence-write failure refuses output. Failed receipts contain no result; raw evidence remains inspectable. Exceptions carry `receipt_path` and in-memory evidence; the CLI writes JSON errors to stderr and exits nonzero. If final persistence fails, the last file may remain running and in-memory evidence identifies the failure.

Each native run owns its sync/async HTTP transports; cleanup is covered for success, startup failure, provider failure, cancellation and deadlines. Up to four async generateContent calls are allowed, with no SDK retry per call. Only one completed STOP text candidate can produce a brief. Missing completion, blocked/partial output and SDK schema failures remain failures through native refinement. Application budgets are 32768 context and 4096 output tokens; these are not measured provider model limits. See [COMPATIBILITY.md](COMPATIBILITY.md) for bounds, library ownership and supported surfaces.

Use `await service.brief_async(...)` from async applications. `service.brief(...)` is the synchronous entry point. Concurrent read-only runs have separate clients and receipts. Caller-injected engines are trusted offline seams explicitly labeled in evidence; they do not qualify a provider run.

## Data and checks

Ten `synthetic-research-cases` v1 cases span starter, busy, ambiguous and boundary profiles. Busy contains 24 sources across eight topics. Read-only selection leaves bundled bytes unchanged; `--init-case` makes an exclusive 0600 copy and never overwrites an existing file. Each case has an exact file hash and declarative identity. No briefs, usage or cost are seeded. See [scenarios](scenarios/README.md).

```sh
uv run --locked python scripts/generate_data.py --check
uv run --locked --extra test pytest -q
uv build
uv run --locked python scripts/check_distribution.py
```

60 offline checks exercise real LlamaIndex/GoogleGenAI/SDK HTTP, multi-call refinement errors and budgets, original raw measurements, source ordinals/scope/content, durable evidence, cancellation/recovery, actual CLI HTTP/signals and dataset integrity. Some domain tests use injected engines/MockLLM and are labeled accordingly. Fresh locked wheel and sdist verification runs outside the checkout with all ten bundled cases. CI runs these gates. None of this is a live Gemini quality claim.

## Remaining gates

Live Gemini ordinary/conflicting/weak-evidence proofs need owner-supplied account access and budget. Firedrill integration and persisted ordinary/negative cases await the new qualified release. This private repo has no selected public license. [PLAN.md](PLAN.md) tracks the remaining work.

Implementation references: [LlamaIndex citation engine](https://developers.llamaindex.ai/python/framework-api-reference/query_engine/citation/), [GoogleGenAI integration](https://developers.llamaindex.ai/python/framework-api-reference/llms/google_genai/).

Explore the [Firedrill example catalog](https://github.com/firedrill-tools/firedrill-example-catalog), [Firedrill](https://firedrill.run/) and [official developer documentation](https://docs.firedrill.run/). Use documentation matching the qualified release.

## Current Firedrill connection — 2026-10-19

The [agent-first adapter and recipe](firedrill/README.md) now use exact-pinned CLI/SDK 2.2.2 and the current command envelope. This supersedes earlier notes saying the release was unavailable. Offline validation is distinct from authenticated persisted execution and live model quality, which remain pending.
