"""Private per-run corpus, retrieval, chunk and original provider evidence."""
from copy import deepcopy
from importlib.metadata import version
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from llama_index.core.schema import MetadataMode
from .runtime import aggregate_usage,now
from .sources import read_source,sha


def source_state(corpus):
    try:
        raw=read_source(corpus.path);digest=sha(raw)
        return {'path':str(corpus.path),'sha256':digest,'matches_loaded_snapshot':digest==corpus.sha256,'error':None}
    except Exception as error:return {'path':str(corpus.path),'sha256':None,'matches_loaded_snapshot':False,'error':str(error)}


def publish(path,data):
    staged=None
    try:
        with NamedTemporaryFile(mode='w',encoding='utf8',dir=path.parent,prefix='.receipt-',suffix='.tmp',delete=False) as file:
            staged=Path(file.name);json.dump(data,file,indent=2,allow_nan=False);file.write('\n');file.flush();os.fsync(file.fileno())
        os.replace(staged,path)
    finally:
        if staged is not None:staged.unlink(missing_ok=True)


class Receipt:
    def __init__(self,corpus,question,model,top_k,output_root=None):
        root=(Path(output_root) if output_root is not None else Path.cwd()/'.runs').resolve();root.mkdir(parents=True,exist_ok=True,mode=0o700)
        run_id=str(uuid4());directory=root/run_id;directory.mkdir(mode=0o700)
        self.path=directory/'receipt.json';self.corpus=corpus;self.native=None;self.recording_error=None
        self.data={'schema_version':1,'run_id':run_id,'receipt_path':str(self.path),'status':'running','execution_kind':'not_started',
            'started_at':now(),'finished_at':None,'question':question,'question_sha256':sha(question.encode()),'requested_model':model,
            'versions':{name:version(name) for name in ('llama-index-core','llama-index-llms-google-genai','google-genai','httpx')},
            'corpus_sha256':corpus.sha256,'dataset':corpus.dataset,'top_k':top_k,'initial_source':source_state(corpus),'final_source':None,
            'retrievals':[],'source_nodes':[],'raw_brief':None,'provider_observations':[],'sdk_events':[],'reported_usage':aggregate_usage([]),'result':None,'error':None}

    def guard(self):
        if self.recording_error is not None:raise self.recording_error

    def save(self):
        if self.native:
            self.data['provider_observations']=deepcopy(self.native.observations)
            self.data['sdk_events']=deepcopy(self.native.sdk_events)
        self.data['reported_usage']=aggregate_usage(self.data['provider_observations'])
        try:publish(self.path,self.data)
        except BaseException as error:self.recording_error=error;raise

    def retrieval(self,value,phase):
        self.guard();self.data['retrievals'].append({'number':len(self.data['retrievals'])+1,'at':now(),'phase':phase,**deepcopy(value)});self.save()

    def response(self,value):
        self.guard();self.data['raw_brief']=str(value)
        self.data['source_nodes']=[{'position':i,'node_id':node.node.node_id,'source_id':node.node.metadata.get('source_id'),
            'record_sha256':node.node.metadata.get('record_sha256'),'text':node.node.get_content(metadata_mode=MetadataMode.NONE),
            'context_sha256':sha(node.node.get_content(metadata_mode=MetadataMode.NONE).encode()),'score':node.score} for i,node in enumerate(value.source_nodes,1)]
        self.save()

    def finish(self,result,error):
        self.data.update(status='failed' if error is not None else 'completed',finished_at=now(),final_source=source_state(self.corpus),result=result if error is None else None)
        if error is not None:
            causes=[];current=error
            while current is not None and len(causes)<5:
                causes.append({'name':type(current).__name__,'message':str(current),'http_status':getattr(current,'code',None) or getattr(current,'status_code',None)})
                current=current.__cause__
            self.data['error']={'name':type(error).__name__,'message':str(error),'causes':causes}
        self.save()
