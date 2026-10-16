"""Actual CLI subprocess plus the real native SDK over loopback HTTP."""
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
from queue import Queue
import signal
import subprocess
import sys
from threading import Event,Thread

import pytest

from test_native import BODY


def environment():
    env={**os.environ,'GOOGLE_API_KEY':'synthetic-cli-key','GEMINI_MODEL':'gemini-2.5-flash','NO_PROXY':'127.0.0.1,localhost','no_proxy':'127.0.0.1,localhost'}
    for key in ('GOOGLE_GENAI_USE_VERTEXAI','GOOGLE_GENAI_USE_ENTERPRISE'):env.pop(key,None)
    return env


@contextmanager
def server(mode):
    requests=Queue();release=Event()
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['content-length'])));requests.put({'path':self.path,'body':body})
            if mode=='pending':release.wait(25)
            value=deepcopy(BODY)
            if mode=='incomplete':value['candidates'][0].pop('finishReason')
            if mode=='unavailable':value={'error':{'code':503,'message':'Synthetic CLI failure'},'usageMetadata':BODY['usageMetadata']}
            raw=json.dumps(value).encode()
            try:
                self.send_response(503 if mode=='unavailable' else 200);self.send_header('content-type','application/json');self.send_header('content-length',str(len(raw)));self.send_header('x-request-id','cli-synthetic');self.end_headers();self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
        def log_message(self,*_):pass
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler);http.daemon_threads=True
    thread=Thread(target=http.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{http.server_port}',requests
    finally:release.set();http.shutdown();http.server_close();thread.join(3)


def command(*args):return [sys.executable,'-m','research_brief.cli',*args]


@pytest.mark.parametrize('mode',['success','incomplete','unavailable'])
def test_real_cli_native_http_and_failed_receipts(mode,tmp_path):
    with server(mode) as (endpoint,requests):
        child=subprocess.run(command('--case','starter','--base-url',endpoint),cwd=tmp_path,env=environment(),text=True,capture_output=True,timeout=30)
        request=requests.get(timeout=1);assert request['path'].endswith('gemini-2.5-flash:generateContent') and requests.empty()
    if mode=='success':
        assert child.returncode==0,child.stderr
        result=json.loads(child.stdout);assert result['status']=='draft' and result['cited_source_ids']==['SUPPORT-041']
        receipt=json.loads(Path(result['receipt_path']).read_text());assert receipt['status']=='completed'
        assert 'Ordinary support synthesis' not in json.dumps(request['body'])
    else:
        assert child.returncode==1 and child.stdout==''
        error=json.loads(child.stderr);receipt=json.loads(Path(error['receipt_path']).read_text())
        assert receipt['status']=='failed' and receipt['result'] is None
    assert receipt['provider_observations'][0]['request_id']=='cli-synthetic'
    assert receipt['reported_usage']['fields']['totalTokenCount']==15
    assert 'synthetic-cli-key' not in json.dumps(receipt)


@pytest.mark.parametrize('sig',[signal.SIGINT,signal.SIGTERM])
def test_real_cli_signal_cancels_native_request_and_finishes_receipt(sig,tmp_path):
    with server('pending') as (endpoint,requests):
        child=subprocess.Popen(command('--case','starter','--base-url',endpoint),cwd=tmp_path,env=environment(),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            requests.get(timeout=20);child.send_signal(sig);out,err=child.communicate(timeout=10)
        finally:
            if child.poll() is None:child.kill();child.communicate()
    assert child.returncode==130 and out==''
    data=json.loads(Path(json.loads(err)['receipt_path']).read_text())
    assert data['status']=='failed' and data['result'] is None
    assert data['provider_observations'][0]['status']=='failed' and data['reported_usage']['fields']['totalTokenCount'] is None


def test_real_cli_model_free_selection_copy_and_no_match(tmp_path):
    env=environment();env.pop('GOOGLE_API_KEY');env.pop('GEMINI_MODEL')
    def invoke(*args):return subprocess.run(command(*args),cwd=tmp_path,env=env,text=True,capture_output=True,timeout=20)
    cases=invoke('--list-cases');assert cases.returncode==0 and len(json.loads(cases.stdout)['cases'])==10
    destination=tmp_path/'private.json';copied=invoke('--init-case','busy','--sources',str(destination));assert copied.returncode==0
    assert destination.stat().st_mode&0o777==0o600
    again=invoke('--init-case','busy','--sources',str(destination));assert again.returncode==1
    answer=invoke('--case','no-match');assert answer.returncode==0
    result=json.loads(answer.stdout);assert result['execution_kind']=='model_free_no_match' and result['reported_usage']['prepared_attempts']==0
    failed=invoke('--case','starter');assert failed.returncode==1
    data=json.loads(Path(json.loads(failed.stderr)['receipt_path']).read_text());assert data['status']=='failed' and data['provider_observations']==[]
