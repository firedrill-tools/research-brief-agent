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
                assert "Compare source methods" not in prompt
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


def response_from_nodes(text,ids):
    from llama_index.core.base.response.schema import Response as LlamaResponse
    from llama_index.core.schema import TextNode,NodeWithScore
    class Engine:
        def query(self,_prompt):
            known={node.metadata['source_id']:node for node in ResearchBriefService(SOURCE_PATH).retriever.nodes}
            return LlamaResponse(response=text,source_nodes=[NodeWithScore(node=known[source_id] if source_id in known else TextNode(text='Controlled outside source-node content',metadata={'source_id':source_id})) for source_id in ids])
    return lambda _retriever:Engine()


def test_unknown_first_source_cannot_shift_a_citation_to_the_next_known_source():
    service=ResearchBriefService(SOURCE_PATH,response_from_nodes('An outside claim [1].',['UNKNOWN','SUPPORT-041']))
    result=service.brief('What Helio support themes appeared in Q3?')
    assert result['status']=='review_required'
    assert result['citation_map']=={'1':'UNKNOWN','2':'SUPPORT-041'}
    assert result['cited_source_ids']==[] and result['invalid_citation_markers']==[1]
    assert result['unknown_source_nodes']==[{'position':1,'source_id':'UNKNOWN'}]


def test_valid_citations_survive_alongside_unknown_and_out_of_range_markers():
    service=ResearchBriefService(SOURCE_PATH,response_from_nodes('Known [2], unknown [1], absent [9].',['UNKNOWN','SUPPORT-041']))
    result=service.brief('What Helio support themes appeared in Q3?')
    assert result['status']=='review_required' and result['cited_source_ids']==['SUPPORT-041']
    assert result['invalid_citation_markers']==[1,9] and result['citation_map']['2']=='SUPPORT-041'


def test_all_unknown_source_context_is_visible_as_review_not_renamed_or_discarded():
    service=ResearchBriefService(SOURCE_PATH,response_from_nodes('An outside claim [1].',['UNKNOWN']))
    result=service.brief('What Helio support themes appeared in Q3?')
    assert result['status']=='review_required' and result['brief']=='An outside claim [1].'
    assert result['source_ids']==[] and result['citation_map']=={'1':'UNKNOWN'}
    assert result['unknown_source_nodes'] and result['invalid_citation_markers']==[1]


def test_support_only_retrieval_does_not_pull_unrelated_adoption_conflicts():
    service=ResearchBriefService(SOURCE_PATH)
    nodes=service.retriever.retrieve('What Helio support themes appeared in Q3?')
    assert [node.node.metadata['source_id'] for node in nodes]==['SUPPORT-041']
    assert conflicts([service.by_id[node.node.metadata['source_id']] for node in nodes])=={}


def test_multi_topic_question_preserves_both_requested_topics():
    service=ResearchBriefService(SOURCE_PATH)
    nodes=service.retriever.retrieve('Compare Helio adoption and support findings in Q3')
    assert {node.node.metadata['topic'] for node in nodes}=={'helio-adoption','helio-support'}


def test_returned_source_nodes_cannot_mutate_the_shared_source_snapshot():
    service=ResearchBriefService(SOURCE_PATH)
    first=service.retriever.retrieve('Helio support')[0];first.node.text='corrupted';first.node.metadata['source_id']='wrong'
    second=service.retriever.retrieve('Helio support')[0]
    assert second.node.metadata['source_id']=='SUPPORT-041' and second.node.text!='corrupted'
    import pytest
    with pytest.raises(TypeError):service.by_id['SUPPORT-041']['text']='wrong'


def test_known_id_with_forged_chunk_cannot_receive_citation_credit():
    from llama_index.core.base.response.schema import Response as LlamaResponse
    from llama_index.core.schema import NodeWithScore
    node=ResearchBriefService(SOURCE_PATH).retriever.retrieve('Helio support')[0]
    node.node.text='A forged claim that is absent from the canonical source.'
    class Engine:
        def query(self,_):return LlamaResponse(response='A claim [1].',source_nodes=[node])
    result=ResearchBriefService(SOURCE_PATH,lambda _:Engine()).brief('What Helio support themes appeared in Q3?')
    assert result['status']=='review_required' and result['cited_source_ids']==[]
    assert result['invalid_citation_markers']==[1] and result['source_identity_errors']


def test_known_but_unselected_topic_cannot_be_silently_substituted():
    from llama_index.core.base.response.schema import Response as LlamaResponse
    node=ResearchBriefService(SOURCE_PATH).retriever.retrieve('Helio adoption')[0]
    class Engine:
        def query(self,_):return LlamaResponse(response='A claim [1].',source_nodes=[node])
    result=ResearchBriefService(SOURCE_PATH,lambda _:Engine()).brief('What Helio support themes appeared in Q3?')
    assert result['status']=='review_required' and result['cited_source_ids']==[] and result['source_identity_errors']


def test_malformed_or_oversized_source_fails_before_model_use(tmp_path):
    import pytest
    from pydantic import ValidationError
    rows=json.loads(SOURCE_PATH.read_text());rows[0]['sample_size']=True
    file=tmp_path/'invalid.json';file.write_text(json.dumps(rows))
    with pytest.raises(ValidationError):ResearchBriefService(file)
    file.write_bytes(b' '*(4_194_304+1))
    with pytest.raises(ValueError,match='exceeds 4 MiB'):ResearchBriefService(file)
