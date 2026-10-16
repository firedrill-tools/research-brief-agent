# Research brief agent

A standalone LlamaIndex/Gemini application that drafts research briefs from a small synthetic source set. It uses a local lexical retriever and LlamaIndex's citation query engine, then exposes the source IDs and the numbered citation map alongside the prose. Sources that assert different values for the same claim are flagged for review.

## Run

Requires Python 3.12+, `uv`, and a Google API key for a live brief.

```sh
uv sync --extra test
uv run pytest -q
GOOGLE_API_KEY=... uv run research-brief 'What do Helio Q3 adoption surveys show?'
```

Set `GEMINI_MODEL` or pass `--model` to select an enabled Gemini model. The current package default is `gemini-3.7-flash`; verify account availability before a live run. The `GoogleGenAI` constructor checks model metadata through the provider, so a valid key is required even before generation. `--sources` accepts another JSON source set with the same fields. No embeddings service, web search or external data source is silently called.

The result includes recognized corpus `source_ids`, an ordinal-preserving `citation_map` for every returned source node, and valid `cited_source_ids` referenced in the prose. Unknown identities remain visible in their original positions; they never shift a citation onto a later known source. `unknown_source_nodes` and `invalid_citation_markers` identify review evidence, while valid citations remain inspectable alongside invalid ones. Missing, unknown or out-of-range citations require review. Conflicting values for the same claim also require review. `draft` means source markers were present and no encoded conflict was found; it **does not** mean each prose claim was proven by the cited text. Source entailment and factual quality need a live and human review.

## Evidence and limits

[Scenarios](scenarios/README.md) include ordinary synthesis, contradictory surveys, missing evidence and unsupported claims. Ten offline tests pass, including the reproduced ordinal-attribution regression; one invokes the real LlamaIndex citation engine using its `MockLLM`. They do not call Gemini. Live Gemini output, usage and source quality are pending provider access.

The application is useful without Firedrill. A thin Firedrill integration and persisted scenarios will be added against the qualified new release, not the retired interface. This repository is private and has no selected public license.

Implementation references: [LlamaIndex citation query engine](https://docs.llamaindex.ai/en/stable/api_reference/query_engine/citation/), [Google GenAI integration](https://docs.llamaindex.ai/en/stable/api_reference/llms/google_genai/).

Explore related applications in the [Firedrill example catalog](https://github.com/firedrill-tools/firedrill-example-catalog). Product and setup references: [Firedrill](https://firedrill.run/) and the [official developer documentation](https://docs.firedrill.run/). Use documentation matching the qualified release; this repository records its current integration limits above.
