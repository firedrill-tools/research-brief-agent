"""LlamaIndex retrieval, synthesis and source-set checks."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from llama_index.core import QueryBundle
from llama_index.core.query_engine import CitationQueryEngine
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.llms.google_genai import GoogleGenAI


STOPWORDS = {"a", "about", "and", "are", "do", "for", "in", "is", "of", "on", "say", "the", "what"}


def terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold())) - STOPWORDS


class LexicalSourceRetriever(BaseRetriever):
    def __init__(self, sources: list[dict], top_k: int = 5):
        super().__init__()
        self.top_k = top_k
        self.nodes = [TextNode(
            id_=item["source_id"],
            text=item["text"],
            metadata={key: item[key] for key in ("source_id", "title", "published", "topic", "claim_key", "claim_value")},
        ) for item in sources]
        self.search_text = {
            item["source_id"]: terms(" ".join([item["title"], item["topic"], *item["tags"], item["text"]]))
            for item in sources
        }

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        query_terms = terms(query_bundle.query_str)
        ranked = []
        for node in self.nodes:
            score = len(query_terms & self.search_text[node.metadata["source_id"]])
            if score:
                ranked.append(NodeWithScore(node=node, score=float(score)))
        ranked.sort(key=lambda item: (-item.score, item.node.metadata["source_id"]))
        return ranked[:self.top_k]


def conflicts(sources: list[dict]) -> dict[str, dict[str, list[str]]]:
    by_claim: dict[str, dict[str, list[str]]] = {}
    for item in sources:
        by_claim.setdefault(item["claim_key"], {}).setdefault(item["claim_value"], []).append(item["source_id"])
    return {claim: positions for claim, positions in by_claim.items() if len(positions) > 1}


class ResearchBriefService:
    def __init__(self, source_path: str | Path, engine_factory=None):
        self.sources = json.loads(Path(source_path).read_text())
        ids = [item["source_id"] for item in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate source ID")
        self.by_id = {item["source_id"]: item for item in self.sources}
        self.retriever = LexicalSourceRetriever(self.sources)
        self.engine_factory = engine_factory

    def brief(self, question: str, model: str | None = None) -> dict:
        candidates = self.retriever.retrieve(question)
        if not candidates:
            return {"status": "insufficient", "brief": None, "source_ids": [],
                    "conflicts": {}, "reason": "No source matched the question."}
        if self.engine_factory:
            engine = self.engine_factory(self.retriever)
        else:
            if not os.environ.get("GOOGLE_API_KEY"):
                raise RuntimeError("GOOGLE_API_KEY is required for a live Gemini brief")
            model_name = model or os.environ.get("GEMINI_MODEL", "gemini-3.7-flash")
            llm = GoogleGenAI(model=model_name, api_key=os.environ["GOOGLE_API_KEY"], temperature=0)
            engine = CitationQueryEngine(retriever=self.retriever, llm=llm, citation_chunk_size=1024)
        response = engine.query(
            "Prepare a concise sourced research brief for this question: " + question +
            " Compare source methods and sample sizes. If sources disagree, explain the disagreement "
            "rather than selecting one number. Do not add claims unsupported by the listed sources."
        )
        citation_map = [node.node.metadata["source_id"] for node in response.source_nodes
                        if node.node.metadata.get("source_id") in self.by_id]
        used_ids = sorted(set(citation_map))
        if not used_ids:
            return {"status": "insufficient", "brief": None, "source_ids": [],
                    "conflicts": {}, "reason": "The generated response had no known source nodes."}
        selected = [self.by_id[source_id] for source_id in used_ids]
        disagreements = conflicts(selected)
        markers = {int(value) for value in re.findall(r"\[(\d+)\]", str(response))}
        valid_markers = bool(markers) and all(1 <= value <= len(citation_map) for value in markers)
        cited_ids = sorted({citation_map[value - 1] for value in markers}) if valid_markers else []
        review_reasons = []
        if disagreements:
            review_reasons.append("Conflicting values for the same claim need review.")
        if not valid_markers:
            review_reasons.append("The generated prose has no valid numbered source citations.")
        return {
            "status": "review_required" if review_reasons else "draft",
            "brief": str(response),
            "source_ids": used_ids,
            "citation_map": {str(index): source_id for index, source_id in enumerate(citation_map, 1)},
            "cited_source_ids": cited_ids,
            "sources": [{key: item[key] for key in ("source_id", "title", "published", "claim_key", "claim_value")}
                        for item in selected],
            "conflicts": disagreements,
            "reason": " ".join(review_reasons) if review_reasons else None,
        }
