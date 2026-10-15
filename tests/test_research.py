import json
from pathlib import Path

from llama_index.core.llms import MockLLM
from llama_index.core.query_engine import CitationQueryEngine

from research_brief.research import ResearchBriefService, conflicts


SOURCE_PATH = Path(__file__).parents[1] / "fixtures/sources.json"


class Response:
    def __init__(self, text, nodes):
        self.text = text
        self.source_nodes = nodes

    def __str__(self):
        return self.text


def engine_for(text, chosen_ids):
    def factory(retriever):
        nodes = {node.node.metadata["source_id"]: node for node in retriever.retrieve("Helio Q3 adoption support")}

        class Engine:
            def query(self, prompt):
                assert "Compare source methods" in prompt
                return Response(text, [nodes[source_id] for source_id in chosen_ids])

        return Engine()

    return factory


def test_retriever_surfaces_both_disagreeing_surveys():
    service = ResearchBriefService(SOURCE_PATH)
    ids = [node.node.metadata["source_id"] for node in service.retriever.retrieve("Helio Q3 adoption")]
    assert {"SURVEY-301", "SURVEY-077"}.issubset(set(ids))
    assert conflicts([service.by_id[source_id] for source_id in ids])["q3-2026-paid-user-adoption"] == {
        "42 percent": ["SURVEY-301"], "58 percent": ["SURVEY-077"]
    }


def test_conflicting_brief_needs_review_even_with_citations():
    service = ResearchBriefService(SOURCE_PATH, engine_for(
        "The surveys disagree: 42% [1] versus 58% [2].", ["SURVEY-301", "SURVEY-077"]
    ))
    result = service.brief("What do Helio Q3 adoption surveys show?")
    assert result["status"] == "review_required"
    assert result["cited_source_ids"] == ["SURVEY-077", "SURVEY-301"]
    assert result["citation_map"] == {"1": "SURVEY-301", "2": "SURVEY-077"}


def test_single_sourced_claim_can_be_draft():
    service = ResearchBriefService(SOURCE_PATH, engine_for(
        "Onboarding tickets often mention setup confusion [1].", ["SUPPORT-041"]
    ))
    result = service.brief("What Helio support themes appeared in Q3?")
    assert result["status"] == "draft"
    assert result["source_ids"] == ["SUPPORT-041"]


def test_unsupported_citation_marker_requires_review():
    service = ResearchBriefService(SOURCE_PATH, engine_for(
        "A claim with a missing source [9].", ["SUPPORT-041"]
    ))
    result = service.brief("What Helio support themes appeared in Q3?")
    assert result["status"] == "review_required"
    assert result["cited_source_ids"] == []


def test_unknown_question_does_not_call_a_model():
    result = ResearchBriefService(SOURCE_PATH).brief("What is the cafeteria menu?")
    assert result["status"] == "insufficient"
    assert result["brief"] is None


def test_duplicate_source_id_rejected(tmp_path):
    sources = json.loads(SOURCE_PATH.read_text())
    sources.append(dict(sources[0]))
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(sources))
    try:
        ResearchBriefService(path)
    except ValueError as error:
        assert "duplicate" in str(error)
    else:
        raise AssertionError("duplicate source ID accepted")


def test_real_llamaindex_citation_engine_path_without_network():
    service = ResearchBriefService(SOURCE_PATH, lambda retriever: CitationQueryEngine(
        retriever=retriever, llm=MockLLM(max_tokens=80), citation_chunk_size=1024
    ))
    result = service.brief("What do Helio Q3 adoption surveys show?")
    assert {"SURVEY-301", "SURVEY-077"}.issubset(set(result["source_ids"]))
    assert result["status"] == "review_required"  # MockLLM has no valid cited brief.
