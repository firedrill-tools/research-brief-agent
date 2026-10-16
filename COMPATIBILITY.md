# Exercised runtime contract

Python 3.12; llama-index-core **0.14.25**, llama-index-llms-google-genai **0.11.3**, google-genai **2.31.0**, HTTPX **0.28.1**. Exact dependency resolution is in uv.lock. Qualification covers local JSON generateContent, not streaming, Vertex, enterprise/ADC, embeddings, web search or external retrieval.

The application uses normal CitationQueryEngine with a public response synthesizer, PromptHelper derived from the model metadata, and async query/refinement. GoogleGenAI receives supported explicit `max_tokens=4096` and `context_window=32768`, so its constructor does not make a model-metadata GET. These are application budgets, not measured provider capacity. Account model availability and actual maximum context require live qualification.

Citation chunks use LlamaIndex's public TokenTextSplitter (1024 tokens, overlap 20, preserved whitespace). The default SentenceSplitter's first long input can load/download NLTK stopwords/punkt resources. A clean-cache failure was reproduced before model dispatch; token splitting removes that hidden asset dependency without patching library globals. Library token counting still uses its bundled tiktoken assets and cache behavior. Sentence boundary optimization is not promised.

The integration's plain `http_options` dictionary preserves injected HTTP clients. Its HttpOptions-model serialization would omit runtime-only client fields. Owned sync/async HTTPX clients are scoped around a run; unexpected sync operations fail. The library creates its SDK wrapper and intentionally does not close caller-injected HTTP clients; the application closes all opened transports. No private client root access, vendor code or global callback patch is used.

LlamaIndex async refinement catches ValueError, TypeError and Pydantic ValidationError and may substitute an empty response. A per-run public LLM callback handler preserves the original cause and raises NativeModelFailure (RuntimeError); a failure latch rejects later calls or release. CallbackManager is shared with the response synthesizer; LLM is a leaf event in this pinned version. Real refinement and SDK validation failures are exercised.

Both SDK and LlamaIndex retry layers are bounded (SDK attempts=1, LlamaIndex max_retries=0). At most four async POST generateContent requests are prepared per brief. Timeout: 30 seconds per HTTP operation, five-second connect, at most 120 seconds for synthesis; CLI supports a smaller positive deadline. Request JSON is limited to 1 MiB before dispatch. Response evidence is capped at 1 MiB after HTTP buffering; this is not a network or memory streaming limit. Over-limit/error/blocked/absent finish/partial/multiple/nontext outputs fail.

Receipts preserve raw decoded HTTP JSON before SDK validation, unknown response fields and independent prompt/candidate/total counts. Missing, malformed, partial and reported-zero usage remain distinct; totals are never guessed from component sums. Counts from synthetic HTTP fixtures demonstrate observation, not real provider execution or billing. HTTP observation count and SDK lifecycle count differ when validation or the request budget fails before dispatch.

Sources are bounded to 4 MiB, 1–1000 strict records, and 16000 characters per body; top_k is 1–20. Corpus records are immutable and retrieved nodes are fresh per run. The corpus file is rehashed before work and release. Topic scoring, candidate truncation and actual chunk bytes are recorded. Whitespace-normalized chunk correspondence and presence in prepared prompts do not prove a prose claim follows from a source; split/omitted context requires review.

Synchronous service calls cannot run inside an event loop; use brief_async. Concurrent read-only runs own independent evidence/clients and can recover after cancellation or failure. Injected engines are trusted caller-owned test seams and are labeled separately. The CLI is qualified on macOS/Linux signal APIs; Windows signal behavior is unqualified.

Firedrill is pending the new released interface. No retired API or private platform implementation is used. Live Gemini, semantic/human evaluation, public publication and licensing remain pending.
