"""Immutable, bounded, byte-identified fictional source collection."""
from datetime import date
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from pydantic import BaseModel,ConfigDict,Field,field_validator

MAX_BYTES=4_194_304


def sha(data):return hashlib.sha256(data).hexdigest()


def read_source(path):
    with Path(path).open('rb') as file:raw=file.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('source collection exceeds 4 MiB')
    return raw


class Source(BaseModel):
    model_config=ConfigDict(frozen=True,extra='forbid')
    source_id:str=Field(min_length=1,max_length=100)
    title:str=Field(min_length=1,max_length=240)
    published:date
    topic:str=Field(min_length=1,max_length=100)
    claim_key:str|None=Field(default=None,max_length=160)
    claim_value:str|None=Field(default=None,max_length=240)
    tags:tuple[str,...]=Field(min_length=1,max_length=24)
    text:str=Field(min_length=1,max_length=16000)
    method:str|None=Field(default=None,max_length=500)
    sample_size:int|None=Field(default=None,ge=1,le=10000000,strict=True)

    @field_validator('source_id','title','topic','text','claim_key','claim_value','method')
    @classmethod
    def nonblank(cls,value):
        if value is not None and not value.strip():raise ValueError('source fields cannot be blank')
        return value

    @field_validator('tags')
    @classmethod
    def meaningful_tags(cls,value):
        if any(not tag.strip() or len(tag)>100 for tag in value) or len({tag.casefold() for tag in value})!=len(value):raise ValueError('invalid/duplicate tag')
        return value


def record_hash(record):
    return sha(json.dumps(dict(record),sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode())


def render(record):
    details=[f'Title: {record["title"]}',f'Published: {record["published"]}']
    if record.get('method'):details.append(f'Method: {record["method"]}')
    if record.get('sample_size') is not None:details.append(f'Sample size: {record["sample_size"]}')
    return '\n'.join(details)+'\n\n'+record['text']


class SourceCorpus:
    def __init__(self,path):
        self.path=Path(path).resolve(strict=True);raw=read_source(self.path);self.sha256=sha(raw)
        data=json.loads(raw);self.dataset=None
        if isinstance(data,dict):
            identity=data.get('dataset')
            if data.get('synthetic') is not True or not isinstance(identity,dict) or not all(isinstance(identity.get(key),str) and identity[key].strip() for key in ('id','profile','case_id')) or type(identity.get('version')) is not int or identity['version']<1:raise ValueError('invalid synthetic dataset identity')
            self.dataset=json.loads(json.dumps(identity));rows=data.get('sources')
        else:rows=data
        if not isinstance(rows,list) or not rows or len(rows)>1000:raise ValueError('collection requires 1–1000 sources')
        records=[]
        for item in rows:
            value=Source.model_validate(item).model_dump(mode='json');value['tags']=tuple(value['tags']);records.append(MappingProxyType(value))
        self.records=tuple(records);self.by_id=MappingProxyType({r['source_id']:r for r in records})
        if len(self.by_id)!=len(records):raise ValueError('duplicate source ID')

    def assert_current(self):
        if sha(read_source(self.path))!=self.sha256:raise ValueError('source collection changed; reload before drafting again')
