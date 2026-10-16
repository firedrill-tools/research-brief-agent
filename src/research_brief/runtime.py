"""Native Gemini JSON evidence through owned public HTTP clients."""
from datetime import datetime,timezone
import json
import os
from urllib.parse import urlsplit

import httpx
from google.genai import types
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.core.callbacks.base_handler import BaseCallbackHandler
from llama_index.core.callbacks.schema import CBEventType,EventPayload

from .sources import sha

MAX_BODY=1_048_576
USAGE_FIELDS=('promptTokenCount','candidatesTokenCount','totalTokenCount')


def now():return datetime.now(timezone.utc).isoformat()


def reported_usage(body):
    raw=body.get('usageMetadata') if isinstance(body,dict) else None
    fields={key:raw.get(key) if isinstance(raw,dict) and type(raw.get(key)) is int and 0<=raw[key]<=2**53-1 else None for key in USAGE_FIELDS}
    return {'fields':fields,'complete':all(value is not None for value in fields.values()),'cost_usd':None}


def aggregate_usage(observations):
    values=[o.get('reported_usage') for o in observations]
    fields={key:sum(u['fields'][key] for u in values) if values and all(u and u['fields'][key] is not None for u in values) else None for key in USAGE_FIELDS}
    fields={key:value if value is None or value<=2**53-1 else None for key,value in fields.items()}
    return {'prepared_attempts':len(observations),'measured_attempts':sum(bool(u and u['complete']) for u in values),
        'complete':bool(values) and all(u and u['complete'] for u in values) and all(value is not None for value in fields.values()),'fields':fields,'cost_usd':None}


def validate_config(model,base_url):
    if not isinstance(model,str) or not model.startswith('gemini-') or any(c.isspace() for c in model):raise ValueError('GEMINI_MODEL must name an enabled Gemini Developer API model')
    # The pinned integration can select cloud credentials from these variables.
    # Refuse that backend instead of changing the owner's process environment.
    if os.getenv('GOOGLE_GENAI_USE_VERTEXAI','false')!='false' or os.getenv('GOOGLE_GENAI_USE_ENTERPRISE','').lower() in {'true','1'}:
        raise ValueError('this application requires the explicit Gemini Developer API backend; ambient Vertex/enterprise selection is unsupported')
    url=urlsplit(base_url)
    if not url.hostname or url.username or url.password or url.query or url.fragment or not (url.scheme=='https' or url.scheme=='http' and url.hostname in {'127.0.0.1','localhost','::1'}):raise ValueError('base_url requires HTTPS or loopback HTTP without URL credentials/query/fragment')


class NoSyncRequests(httpx.BaseTransport):
    def handle_request(self,request):raise RuntimeError('unexpected synchronous provider operation; this run owns async generateContent only')


class NativeEvidence:
    def __init__(self,publish,guard):self.observations=[];self.publish=publish;self.guard=guard;self.failure=None;self.sdk_events=[]

    def check(self):
        self.guard()
        if self.failure is not None:raise NativeModelFailure('a previous model call failed; synthesis cannot complete') from self.failure

    async def request(self,request):
        self.check()
        if request.method!='POST' or not request.url.path.endswith(':generateContent'):raise ValueError('unsupported provider operation; only async generateContent is qualified')
        if len(self.observations)>=4:raise ValueError('research generation limit (4) reached')
        raw=await request.aread()
        if len(raw)>MAX_BODY:raise ValueError('provider request exceeds 1 MiB evidence limit')
        body=json.loads(raw)
        self.observations.append({'attempt':len(self.observations)+1,'status':'started','started_at':now(),'finished_at':None,
            'path':request.url.path,'input_sha256':sha(raw),'request_body':body,'generation_config':body.get('generationConfig'),
            'http_status':None,'request_id':None,'response_id':None,'response_model':None,'finish_reason':None,
            'body':None,'reported_usage':None,'error':None})
        self.publish()

    async def response(self,response):
        item=self.observations[-1];item.update(status='received',http_status=response.status_code,request_id=response.headers.get('x-request-id') or response.headers.get('request-id'))
        try:
            raw=await response.aread();item.update(body_sha256=sha(raw),truncated=len(raw)>MAX_BODY)
            text=raw[:MAX_BODY].decode('utf8',errors='replace')
            try:body=json.loads(text)
            except ValueError:body=text
            item.update(body=body,body_source='HTTP decoded response bytes before SDK validation',reported_usage=reported_usage(body))
            if isinstance(body,dict):
                candidates=body.get('candidates');candidate=candidates[0] if isinstance(candidates,list) and candidates and isinstance(candidates[0],dict) else {}
                item.update(response_id=body.get('responseId'),response_model=body.get('modelVersion'),finish_reason=candidate.get('finishReason'))
            self.publish()
            if item['truncated']:raise ValueError('provider response exceeds 1 MiB evidence limit')
            if 200<=response.status_code<300:validate_completion(body);item['status']='accepted'
            else:item['status']='http_error'
            self.publish()
        except BaseException as error:
            self.failure=error
            item.update(status='rejected',error={'name':type(error).__name__,'message':str(error)})
            self.publish();raise
        finally:item['finished_at']=now();await response.aclose()

    def fail(self,error):
        if self.sdk_events and self.sdk_events[-1]['status']=='started':
            self.sdk_events[-1].update(status='failed',finished_at=now(),error={'name':type(error).__name__,'message':str(error)})
        if self.observations and self.observations[-1]['status'] in {'started','received'}:
            self.observations[-1].update(status='failed',finished_at=now(),error={'name':type(error).__name__,'message':str(error)})


class NativeModelFailure(RuntimeError):
    """A model/recording failure must not become a partial synthesis result."""


class NativeModelEvents(BaseCallbackHandler):
    def __init__(self,native):
        super().__init__([],[]);self.native=native

    def on_event_start(self,event_type,payload=None,event_id='',parent_id='',**kwargs):
        if event_type==CBEventType.LLM:
            self.native.check()
            self.native.sdk_events.append({'event_id':event_id,'status':'started','started_at':now(),'finished_at':None,'error':None})
            try:self.native.publish()
            except BaseException as error:
                self.native.failure=error;raise NativeModelFailure('model evidence recording failed') from error
        return event_id

    def on_event_end(self,event_type,payload=None,event_id='',**kwargs):
        if event_type!=CBEventType.LLM:return
        event=next((e for e in reversed(self.native.sdk_events) if e['event_id']==event_id),None)
        error=(payload or {}).get(EventPayload.EXCEPTION)
        if event is not None:
            event.update(status='failed' if error is not None else 'returned',finished_at=now())
            if error is not None:event['error']={'name':type(error).__name__,'message':str(error)}
        if error is not None:self.native.failure=self.native.failure or error
        try:self.native.publish()
        except BaseException as recording:
            self.native.failure=self.native.failure or recording
            raise NativeModelFailure('model evidence recording failed') from recording
        if error is not None:
            import asyncio
            if isinstance(error,asyncio.CancelledError):return
            raise NativeModelFailure(f'native model call failed: {error}') from error

    def start_trace(self,trace_id=None):return None
    def end_trace(self,trace_id=None,trace_map=None):return None


def validate_completion(body):
    if not isinstance(body,dict):raise ValueError('provider response is not a JSON object')
    feedback=body.get('promptFeedback')
    if isinstance(feedback,dict) and feedback.get('blockReason') not in {None,'BLOCK_REASON_UNSPECIFIED'}:raise ValueError('Gemini prompt was blocked')
    candidates=body.get('candidates')
    if not isinstance(candidates,list) or len(candidates)!=1 or not isinstance(candidates[0],dict):raise ValueError('expected exactly one Gemini candidate')
    candidate=candidates[0]
    if candidate.get('finishReason')!='STOP':raise ValueError(f"generation did not complete ({candidate.get('finishReason')!r})")
    if any(isinstance(r,dict) and r.get('blocked') is True for r in candidate.get('safetyRatings') or []):raise ValueError('candidate was blocked')
    content=candidate.get('content');parts=content.get('parts') if isinstance(content,dict) else None
    if not isinstance(parts,list) or not parts or any(not isinstance(part,dict) for part in parts):raise ValueError('candidate has no usable content')
    if content.get('role') not in {None,'model'}:raise ValueError('candidate has an inconsistent role')
    if any(any(part.get(key) is not None for key in ('functionCall','executableCode','codeExecutionResult','inlineData','fileData')) for part in parts):raise ValueError('research output must be text without executable/media content')
    if not any(not part.get('thought') and isinstance(part.get('text'),str) and part['text'].strip() for part in parts):raise ValueError('candidate has no final text')


def create_clients(evidence,transport=None):
    sync=httpx.Client(transport=NoSyncRequests(),timeout=httpx.Timeout(30,connect=5))
    try:
        asynchronous=httpx.AsyncClient(transport=transport,timeout=httpx.Timeout(30,connect=5),follow_redirects=False,
            event_hooks={'request':[evidence.request],'response':[evidence.response]})
    except BaseException:
        sync.close();raise
    return sync,asynchronous


def create_llm(model,key,base_url,sync,asynchronous,callback_manager):
    # The supported dictionary path retains injected clients. Converting an
    # HttpOptions model to JSON would exclude these runtime-only fields.
    return GoogleGenAI(model=model,api_key=key,max_tokens=4096,context_window=32768,max_retries=0,
        file_mode='inline',is_function_calling_model=False,callback_manager=callback_manager,
        generation_config=types.GenerateContentConfig(max_output_tokens=4096,candidate_count=1),
        http_options={'base_url':base_url,'api_version':'v1beta','timeout':30000,
            'retry_options':types.HttpRetryOptions(attempts=1),'httpx_client':sync,'httpx_async_client':asynchronous})
