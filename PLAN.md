# Research brief requirement audit

1. **Citation identity:** preserve every actual LlamaIndex source-node ordinal, reject unknown/out-of-range attribution and retain valid partial evidence. Do not turn citation syntax into a claim of entailment.
2. **Retrieval fidelity:** keep synthesis instructions out of the retrieval query, scope ordinary topical questions coherently, and identify exact source/chunk bytes. Preserve conflicting methods/sample sizes and uncertainty.
3. **Native Gemini:** exercise real CitationQueryEngine/GoogleGenAI/SDK HTTP, completion flags, request/retry/output/time bounds, model metadata behavior and owned client/cancellation cleanup. Explicit credentials/backend/endpoint; no ambient production fallback.
4. **Observations/data:** preserve raw usage/model/failure/source evidence and coherent hash-bound starter/busy/ambiguous/boundary populations with private input selection/copy. Manifest/assessment expectations stay outside model context.
5. **Distribution:** actual CLI, fresh locked wheel/sdist outside checkout, exact-head CI and catalog proof; live Gemini/new Firedrill/publication/license remain parked.

The first ordinal bug was reproduced with actual LlamaIndex Response/NodeWithScore objects: an unknown node before SUPPORT-041 made [1] falsely attribute its claim to SUPPORT-041 and marked it draft. Ordinals and unknown identities are now preserved; mixed valid/invalid citations retain valid evidence and require review. Native transport/data/package work remains next.
