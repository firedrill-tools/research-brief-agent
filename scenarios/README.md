# Research brief scenarios

All source files and product names are synthetic. Use a fresh CLI invocation for each scenario; this application does not write state.

| Case | Prompt | Expected result |
|---|---|---|
| Conflicting surveys | `What do Helio Q3 adoption surveys show?` | Retrieve both survey sources; compare sample methods and report the 42% versus 58% conflict. Status stays `review_required`. |
| Single-source theme | `What Helio support themes appeared in Q3?` | Use the ticket review for setup confusion and avoid calling ticket count an adoption rate. |
| Missing evidence | `What is the cafeteria menu?` | Return `insufficient` without a model call. |
| Unsupported claim | Ask the model to add an unrecorded market-size estimate. | Do not add it. Any narrative claim still requires human verification because numbered citations alone do not prove entailment. |
| Invalid citation | A generated answer cites `[9]` with only one source node. | Return `review_required` with no cited source IDs. |

The seven offline checks exercise retrieval, conflict detection, source marker validation, and a real LlamaIndex citation-engine run with `MockLLM`. They are not a live Gemini quality test.
