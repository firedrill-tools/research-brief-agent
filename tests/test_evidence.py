import asyncio
import json
from pathlib import Path

import httpx
import pytest

from research_brief import evidence as evidence_module
from research_brief.research import ResearchBriefService
from test_native import CORPUS,QUESTION,Script,BODY,run


@pytest.fixture(autouse=True)
def key(monkeypatch,isolated_output):
    monkeypatch.setenv('GOOGLE_API_KEY','synthetic-not-real');monkeypatch.setenv('GEMINI_MODEL','gemini-2.5-flash')


def test_no_match_uses_no_key_and_records_model_free_outcome(monkeypatch):
    monkeypatch.delenv('GOOGLE_API_KEY',raising=False)
    result=ResearchBriefService(CORPUS).brief('What is the cafeteria menu?')
    data=json.loads(Path(result['receipt_path']).read_text())
    assert result['execution_kind']=='model_free_no_match' and result['status']=='insufficient'
    assert data['provider_observations']==[] and data['reported_usage']['fields']['totalTokenCount'] is None


def test_source_change_during_native_synthesis_refuses_stale_output(tmp_path):
    file=tmp_path/'sources.json';file.write_bytes(CORPUS.read_bytes());original=file.read_bytes()
    class Changing(Script):
        async def handle_async_request(self,request):
            response=await super().handle_async_request(request);file.write_bytes(original+b'\n');return response
    script=Changing([BODY])
    with pytest.raises(ValueError,match='collection changed') as error:run(script,source=file)
    data=error.value.evidence
    assert script.closed and data['result'] is None and data['raw_brief']==BODY['candidates'][0]['content']['parts'][0]['text']
    assert data['final_source']['matches_loaded_snapshot'] is False and data['reported_usage']['fields']['totalTokenCount']==15
    assert file.read_bytes()==original+b'\n'


@pytest.mark.parametrize('phase',['response','retrieval','final'])
def test_recording_failure_stops_generation_or_release_and_keeps_failure(phase,monkeypatch):
    actual=evidence_module.publish;failed=[]
    def broken(path,data):
        hit=(phase=='response' and data['provider_observations'] and data['provider_observations'][-1]['body'] is not None or
             phase=='retrieval' and bool(data['retrievals']) or phase=='final' and data['status']=='completed')
        if hit and (phase=='final' or not failed):failed.append(True);raise OSError('synthetic evidence publication failure')
        return actual(path,data)
    monkeypatch.setattr(evidence_module,'publish',broken);script=Script([BODY])
    with pytest.raises(Exception) as error:run(script)
    data=error.value.evidence
    assert failed and data['status']=='failed'
    if phase=='retrieval':assert script.requests==[]
    else:assert script.closed and len(script.requests)==1
    if phase=='response':assert data['result'] is None
    if phase=='final':assert 'publication failure' in data['evidence_error'] and json.loads(Path(error.value.receipt_path).read_text())['status']=='running'


def test_independent_concurrent_runs_and_later_recovery_do_not_share_clients_or_evidence():
    async def exercise():
        service=ResearchBriefService(CORPUS);entered=asyncio.Event();closed=[]
        class Pending(httpx.AsyncBaseTransport):
            async def handle_async_request(self,request):entered.set();await asyncio.Event().wait()
            async def aclose(self):closed.append(True)
        first=asyncio.create_task(service.brief_async(QUESTION,transport=Pending()))
        await asyncio.wait_for(entered.wait(),3)
        script=Script([BODY]);second=await service.brief_async(QUESTION,transport=script)
        first.cancel()
        with pytest.raises(asyncio.CancelledError) as cancelled:await first
        assert closed and script.closed and second['status']=='draft'
        assert second['run_id']!=cancelled.value.evidence['run_id'] and cancelled.value.evidence['result'] is None
        failed=Script([503])
        with pytest.raises(Exception):await service.brief_async(QUESTION,transport=failed)
        recovered=await service.brief_async(QUESTION,transport=Script([BODY]))
        assert recovered['status']=='draft' and recovered['run_id']!=second['run_id']
    asyncio.run(exercise())
