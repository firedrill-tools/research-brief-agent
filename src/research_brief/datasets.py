"""Hash-bound read-only research cases and exclusive private input copies."""
import json
import os
from pathlib import Path

from .sources import SourceCorpus,read_source,sha


def data_root():
    bundled=Path(__file__).parent/'sample_data'
    return bundled if bundled.exists() else Path(__file__).parents[2]/'data'


def load_manifest(root=None):
    root=Path(root) if root is not None else data_root();raw=read_source(root/'manifest.json');manifest=json.loads(raw)
    if (manifest.get('id'),manifest.get('version'),manifest.get('synthetic'))!=('synthetic-research-cases',1,True):raise ValueError('unsupported manifest identity')
    cases=manifest.get('cases')
    if not isinstance(cases,list) or not cases:raise ValueError('manifest has no cases')
    ids=set();files=set()
    for case in cases:
        if not isinstance(case,dict) or not isinstance(case.get('id'),str) or not case['id'] or case['id'] in ids:raise ValueError('duplicate/invalid case identity')
        ids.add(case['id']);file=case.get('file')
        if not isinstance(file,str) or not file or Path(file).is_absolute() or '..' in Path(file).parts or file in files:raise ValueError('invalid case path')
        files.add(file)
        if case.get('profile') not in {'starter','busy','ambiguous','boundary'}:raise ValueError('invalid profile')
        if not isinstance(case.get('question'),str) or not case['question'].strip() or len(case['question'])>8000:raise ValueError('invalid question')
        if type(case.get('top_k')) is not int or not 1<=case['top_k']<=20:raise ValueError('invalid top_k')
        target=(root/file).resolve(strict=True)
        if not target.is_relative_to(root.resolve(strict=True)):raise ValueError('case path escapes dataset')
        corpus=SourceCorpus(target)
        if corpus.sha256!=case.get('sha256'):raise ValueError('case hash differs')
        if corpus.dataset!={'id':manifest['id'],'version':1,'profile':case['profile'],'case_id':case['id']}:raise ValueError('case identity differs')
        if len(corpus.records)!=case.get('source_count') or len({r['topic'] for r in corpus.records})!=case.get('topic_count'):raise ValueError('case population differs')
    return manifest,sha(raw),root


def list_cases(root=None):
    manifest,digest,_=load_manifest(root);return {**manifest,'manifest_sha256':digest}


def select(case_id,root=None):
    manifest,digest,root=load_manifest(root);case=next((c for c in manifest['cases'] if c['id']==case_id),None)
    if case is None:raise ValueError('unknown case')
    corpus=SourceCorpus(root/case['file'])
    if corpus.sha256!=case['sha256']:raise ValueError('case changed before selection')
    return case,corpus,digest


def initialize(case_id,path,root=None):
    case,corpus,digest=select(case_id,root);raw=read_source(corpus.path)
    if sha(raw)!=case['sha256']:raise ValueError('case changed before copying')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(descriptor,'wb') as file:file.write(raw);file.flush();os.fsync(file.fileno())
    except BaseException:path.unlink(missing_ok=True);raise
    return {'sources':str(path.resolve()),'dataset':corpus.dataset,'sha256':case['sha256'],'manifest_sha256':digest,'question':case['question'],'top_k':case['top_k']}
