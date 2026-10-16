"""Actual CitationQueryEngine/GoogleGenAI/google-genai HTTP, no stub model."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest

from research_brief import research as research_module
from research_brief import runtime
from research_brief.research import ResearchBriefService

CORPUS=Path(__file__).parents[1]/'fixtures/sources.json'
QUESTION='What Helio support themes appeared in Q3?'
USAGE={'promptTokenCount':10,'candidatesTokenCount':5,'totalTokenCount':15}
BODY={'candidates':[{'content':{'role':'model','parts':[{'text':'Setup confusion was the leading onboarding support theme in the sample [1].'}]},'finishReason':'STOP'}],
    'modelVersion':'gemini-2.5-flash-synthetic','responseId':'response-synthetic','usageMetadata':USAGE,'unknown_marker':{'original':True}}


@pytest.fixture(autouse=True)
def key(monkeypatch,isolated_output):
    monkeypatch.setenv('GOOGLE_API_KEY','synthetic-not-a-provider-key')
    monkeypatch.setenv('GEMINI_MODEL','gemini-2.5-flash')


class Script(httpx.AsyncBaseTransport):
    def __init__(self,items):self.items=iter(items);self.requests=[];self.closed=False
    async def handle_async_request(self,request):
        self.requests.append({'method':request.method,'path':request.url.path,'body':json.loads(request.content)})
        value=next(self.items)
        if isinstance(value,int):return httpx.Response(value,json={'error':{'code':value,'message':'Synthetic provider unavailable'},'usageMetadata':deepcopy(USAGE)},headers={'x-request-id':'req-failed'})
        if isinstance(value,bytes):return httpx.Response(200,content=value,headers={'content-type':'application/json','x-request-id':'req-malformed'})
        return httpx.Response(200,json=value,headers={'x-request-id':'req-synthetic'})
    async def aclose(self):self.closed=True


def run(script,source=CORPUS,**options):return ResearchBriefService(source).brief(QUESTION,transport=script,**options)


def test_actual_native_citation_engine_scopes_context_and_records_original_response():
    script=Script([BODY]);result=run(script);data=json.loads(Path(result['receipt_path']).read_text())
    assert result['status']=='draft' and result['source_ids']==['SUPPORT-041'] and result['cited_source_ids']==['SUPPORT-041']
    assert result['source_identity_errors']==[] and result['unobserved_context_nodes']==[]
    assert script.closed and len(script.requests)==1 and script.requests[0]['method']=='POST'
    assert script.requests[0]['path'].endswith('gemini-2.5-flash:generateContent')
    config=script.requests[0]['body']['generationConfig'];assert config['maxOutputTokens']==4096 and config['candidateCount']==1
    prompt=json.dumps(script.requests[0]['body']['contents'])
    assert 'Compare source methods' in prompt and '41 Q3 support tickets' in prompt and '300 paid Helio' not in prompt
    assert all(r['question']==QUESTION for r in data['retrievals']) and len(data['retrievals'])==2
    assert data['source_nodes'][0]['source_id']=='SUPPORT-041' and data['source_nodes'][0]['context_sha256']
    raw=data['provider_observations'][0];assert raw['body']==BODY and raw['request_id']=='req-synthetic' and raw['response_model']==BODY['modelVersion']
    assert data['reported_usage']['fields']==USAGE and data['reported_usage']['complete'] is True and data['reported_usage']['cost_usd'] is None
    assert data['status']=='completed' and data['initial_source']['sha256']==data['final_source']['sha256']==result['corpus_sha256']
    assert 'synthetic-not-a-provider-key' not in json.dumps(data)
    assert Path(result['receipt_path']).stat().st_mode&0o777==0o600 and Path(result['receipt_path']).parent.stat().st_mode&0o777==0o700


@pytest.mark.parametrize('finish',['MAX_TOKENS','SAFETY','OTHER',None])
def test_native_nonstop_generation_never_releases_a_brief(finish):
    body=deepcopy(BODY);body['candidates'][0]['finishReason']=finish;script=Script([body])
    with pytest.raises(Exception) as error:run(script)
    data=error.value.evidence
    assert script.closed and len(script.requests)==1 and data['status']=='failed' and data['result'] is None
    assert data['provider_observations'][0]['finish_reason']==finish and data['provider_observations'][0]['body']==body
    assert data['reported_usage']['fields']['totalTokenCount']==15


@pytest.mark.parametrize('kind',['missing','partial','zero','invalid'])
def test_native_usage_presence_is_not_inferred_from_sdk_defaults(kind):
    body=deepcopy(BODY)
    if kind=='missing':body.pop('usageMetadata')
    elif kind=='partial':body['usageMetadata']={'totalTokenCount':0}
    elif kind=='zero':body['usageMetadata']=dict.fromkeys(USAGE,0)
    else:body['usageMetadata']={**USAGE,'promptTokenCount':True}
    script=Script([body])
    try:result=run(script);data=json.loads(Path(result['receipt_path']).read_text())
    except Exception as error:data=error.evidence
    assert data['provider_observations'][0]['body']==body and script.closed
    assert data['reported_usage']['complete'] is (kind=='zero')
    assert data['reported_usage']['fields']['promptTokenCount']==(0 if kind=='zero' else None)


@pytest.mark.parametrize('kind',['empty','multiple','blocked','function','invalid-json','oversized'])
def test_malformed_or_unsupported_native_output_is_visible_without_a_result(kind):
    body=deepcopy(BODY)
    if kind=='empty':body['candidates'][0]['content']['parts']=[{'text':'  '}]
    elif kind=='multiple':body['candidates'].append(deepcopy(body['candidates'][0]))
    elif kind=='blocked':body['promptFeedback']={'blockReason':'SAFETY'}
    elif kind=='function':body['candidates'][0]['content']['parts'].append({'functionCall':{'name':'external_action','args':{}}})
    elif kind=='invalid-json':body=b'{synthetic-invalid-json'
    else:body=(json.dumps(body)+' '*1_048_576).encode()
    script=Script([body])
    with pytest.raises(Exception) as error:run(script)
    assert len(script.requests)==1 and script.closed and error.value.evidence['result'] is None
    assert error.value.evidence['provider_observations'][0]['body'] is not None


def test_native_http_failure_has_one_attempt_and_retains_failed_measurements():
    script=Script([503])
    with pytest.raises(Exception) as error:run(script)
    data=error.value.evidence
    assert len(script.requests)==1 and script.closed
    assert data['provider_observations'][0]['http_status']==503 and data['provider_observations'][0]['request_id']=='req-failed'
    assert data['reported_usage']['fields']['totalTokenCount']==15


@pytest.mark.parametrize('kind',['cancel','deadline'])
def test_cancellation_and_deadline_close_both_owned_clients(kind,monkeypatch):
    clients=[];original=research_module.create_clients
    def factory(*args):
        values=original(*args);clients.extend(values);return values
    monkeypatch.setattr(research_module,'create_clients',factory)
    async def exercise():
        entered=asyncio.Event();closed=[];cancelled=[]
        class Pending(httpx.AsyncBaseTransport):
            async def handle_async_request(self,request):
                entered.set()
                try:await asyncio.Event().wait()
                finally:cancelled.append(True)
            async def aclose(self):closed.append(True)
        task=asyncio.create_task(ResearchBriefService(CORPUS).brief_async(QUESTION,transport=Pending(),timeout_seconds=0.15 if kind=='deadline' else 120))
        await asyncio.wait_for(entered.wait(),timeout=3)
        if kind=='cancel':task.cancel()
        with pytest.raises(TimeoutError if kind=='deadline' else asyncio.CancelledError) as error:await task
        assert closed and cancelled and all(client.is_closed for client in clients)
        assert error.value.evidence['status']=='failed' and error.value.evidence['provider_observations'][0]['status']=='failed'
        assert error.value.evidence['reported_usage']['fields']['totalTokenCount'] is None
    asyncio.run(exercise())


def test_startup_failure_closes_both_clients_without_a_provider_request(monkeypatch):
    clients=[];original=research_module.create_clients;script=Script([])
    def factory(*args):
        values=original(*args);clients.extend(values);return values
    def broken(*_):raise RuntimeError('synthetic model startup failure')
    monkeypatch.setattr(research_module,'create_clients',factory);monkeypatch.setattr(research_module,'create_llm',broken)
    with pytest.raises(RuntimeError,match='startup failure'):run(script)
    assert script.closed and all(client.is_closed for client in clients) and script.requests==[]


@pytest.mark.parametrize('variable,value',[('GOOGLE_GENAI_USE_VERTEXAI','true'),('GOOGLE_GENAI_USE_VERTEXAI','False'),('GOOGLE_GENAI_USE_ENTERPRISE','1')])
def test_ambient_cloud_backend_is_rejected_before_any_provider_client(variable,value,monkeypatch):
    monkeypatch.setenv(variable,value);script=Script([])
    with pytest.raises(ValueError,match='Developer API') as error:run(script)
    assert script.requests==[] and error.value.evidence['provider_observations']==[]


def test_actual_refinement_failure_preserves_the_prior_response(tmp_path,monkeypatch):
    from llama_index.core.utils import GlobalsHelper
    def no_download(*_):raise AssertionError('application chunking must not require NLTK asset downloads')
    monkeypatch.setattr(GlobalsHelper,'wait_for_nltk_check',no_download)
    rows=json.loads(CORPUS.read_text());template=rows[-1]
    rows=[]
    for index in range(5):
        rows.append({**template,'source_id':f'LONG-{index}','title':f'Helio support evidence {index}','text':' '.join(['1','2','3','4','5','6','7','8','9','0']*790)})
    file=tmp_path/'long.json';file.write_text(json.dumps(rows));script=Script([BODY,503])
    with pytest.raises(Exception) as error:run(script,source=file)
    data=error.value.evidence
    assert len(script.requests)==2 and script.closed and data['result'] is None,data['error']
    assert data['provider_observations'][0]['body']==BODY and data['provider_observations'][1]['http_status']==503
    assert data['reported_usage']['fields']['totalTokenCount']==30


def test_sdk_validation_error_cannot_be_swallowed_into_an_empty_draft():
    body=deepcopy(BODY);body['candidates'][0]['index']='not-an-integer';script=Script([body])
    with pytest.raises(Exception) as error:run(script)
    data=error.value.evidence
    assert len(script.requests)==1 and script.closed and data['result'] is None
    assert data['provider_observations'][0]['body']==body
    assert data['sdk_events'][-1]['status']=='failed' and data['sdk_events'][-1]['error']


def test_actual_refinement_loop_cannot_exceed_four_generation_requests(tmp_path):
    template=json.loads(CORPUS.read_text())[-1]
    rows=[{**template,'source_id':f'BUDGET-{index}','title':f'Helio support evidence {index}','text':' '.join(['1','2','3','4','5','6','7','8','9','0']*790)} for index in range(20)]
    file=tmp_path/'budget.json';file.write_text(json.dumps(rows));script=Script([BODY]*8)
    with pytest.raises(Exception) as error:run(script,source=file,top_k=20)
    assert len(script.requests)==4 and script.closed and error.value.evidence['result'] is None,error.value.evidence['error']
    assert error.value.evidence['reported_usage']['fields']['totalTokenCount']==60
