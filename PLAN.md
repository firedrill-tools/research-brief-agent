# Research brief requirement audit

## Completed standalone audit

1. **Citation identity:** preserve actual LlamaIndex source ordinals; unknown, out-of-scope, forged or unsupported attribution requires review. Valid partial citations survive. Exact file/canonical record/context hashes are inspectable.
2. **Retrieval fidelity:** raw question goes to a fresh lexical retriever; synthesis directions live in LlamaIndex templates. Highest lexical topic ties retain explicitly requested topics. Methods, sample sizes, periods and different denominators remain source content. This is bounded lexical retrieval, not exhaustive semantic search.
3. **Native Gemini:** actual CitationQueryEngine, async refinement, GoogleGenAI and google-genai HTTP. One STOP text candidate; explicit Developer API config, owned transports, four prepared generations, one SDK attempt per call, declared input/output budgets and 120-second deadline. Original failures survive the library's refinement fallback.
4. **Observations/data:** private per-run raw request/response, SDK lifecycle, source/retrieval/chunk, usage and error evidence. Source mutation and recording failures refuse output. Ten versioned/hash-bound cases across starter/busy/ambiguous/boundary; busy 24 sources/eight topics. Read-only selection and exclusive private copies.
5. **Distribution:** noninteractive async CLI including loopback HTTP and SIGINT/SIGTERM checks; pinned runtime/lock; bundled datasets; fresh locked wheel/sdist checks outside checkout; CI runs these gates.

## Reproduced regressions

- Dropping an unknown first node shifted [1] onto SUPPORT-041 and falsely marked a draft. Preserve original ordinals.
- Synthesis instructions in the retrieval query and shared Helio/Q3 terms pulled adoption conflicts into support-only questions. Scope topics with the original question.
- Native Gemini missing finishReason could become a draft. The original native MAX_TOKENS/SAFETY responses already failed; preserve that behavior. Explicit completion checks retain raw evidence.
- LlamaIndex refinement catches ValueError/TypeError/SDK validation exceptions and can return empty synthesis. Public LLM callbacks raise a RuntimeError with the original cause and a per-run failure latch; real multi-call refinement failures and the four-call budget are covered.
- A source changed during generation left a draft in a failed receipt. Failed runs now retain raw evidence with result null.
- CI exposed a pre-dispatch long-context cold-start failure. The default sentence splitter's NLTK asset dependency was reproduced with an empty cache/denied download; public TokenTextSplitter now provides citation chunks and the native refinement regression forbids that download path.

## Parked gates

- Owner-supplied Gemini credentials, enabled model and budget for live ordinary/conflicting/weak-evidence/injection proofs and human entailment review.
- New official Firedrill release/contract, persisted ordinary and negative/recovery runs, exact-release CI.
- Publication/license ownership. Repository remains private; no license has been selected.
