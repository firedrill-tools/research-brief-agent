# Working rules

Use synthetic source documents and the actual LlamaIndex CitationQueryEngine/GoogleGenAI path. Keep retrieval queries free of synthesis instructions. Preserve every source-node ordinal, including unknown identities; never drop nodes and renumber later evidence. Retain valid citations alongside invalid markers. Validate selected source identity and chunk correspondence. A citation marker and matching chunk are not proof that prose is entailed. Never call a draft verified.

Native calls use owned public HTTPX clients, a per-run LLM callback manager and bounded async generateContent. Retain original request/response bodies and measurements, including failed attempts. Do not replace the model with a canned answer, patch vendor code, use shared Settings for a run, normalize unknown usage to zero or infer billing. LlamaIndex refinement catches ValueError/TypeError/ValidationError: errors must remain failures through the public callback handler and post-query latch. Test real refinement, not only a one-call stub.

Before release, recheck source bytes and durable evidence. Failed runs expose no result; raw output remains evidence. Close transports on success, model errors, startup errors, cancellation and deadlines. A caller-injected engine is a trusted offline/test seam, explicitly labeled in receipts; its lifecycle belongs to its caller.

Data manifest focus descriptions stay outside model input. Run `scripts/generate_data.py --check`, locked tests and fresh wheel/sdist verification after relevant changes. Ten cases span four profiles; busy has 24 sources/eight topics. No seeded provider usage, costs or model answers.

Live Gemini quality, human source entailment and released Firedrill integration remain external gates. Use only the new qualified Firedrill interface. Keep this repo private until publication and licensing are decided.

## Current Firedrill connection — 2026-10-19

The optional `firedrill/` toolchain now pins released CLI/SDK 2.2.2. Read its README, preserve the actual application entry point and run its offline tests with the existing verification gates. Earlier release-unavailability notes are historical; authenticated persisted and live model proofs remain pending. No retired API, guessed Tool binding, canned normal response or paid campaign.
