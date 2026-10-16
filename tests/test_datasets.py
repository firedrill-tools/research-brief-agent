from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from research_brief.datasets import data_root,initialize,list_cases,load_manifest,select
from research_brief.retrieval import LexicalSourceRetriever
from research_brief.research import conflicts
from research_brief.sources import SourceCorpus,sha


def test_all_ten_hash_bound_cases_are_coherent_and_assessment_stays_outside_context(tmp_path):
    manifest=list_cases();assert len(manifest['cases'])==10 and {c['profile'] for c in manifest['cases']}=={'starter','busy','ambiguous','boundary'}
    for case in manifest['cases']:
        selected,corpus,digest=select(case['id']);before=corpus.path.read_bytes()
        destination=tmp_path/case['file'];receipt=initialize(case['id'],destination)
        assert receipt['sha256']==sha(before)==case['sha256'] and receipt['manifest_sha256']==digest
        assert destination.read_bytes()==before and destination.stat().st_mode&0o777==0o600
        copied=SourceCorpus(destination);nodes=LexicalSourceRetriever(copied.records,case['top_k']).retrieve(case['question'])
        assert all(case['focus'] not in node.node.text for node in nodes)
        assert corpus.path.read_bytes()==before and copied.dataset==corpus.dataset
        with pytest.raises(FileExistsError):initialize(case['id'],destination)
        assert destination.read_bytes()==before


def test_busy_population_and_scope_and_period_denominators_are_preserved():
    case,corpus,_=select('busy');assert len(corpus.records)==24 and len({r['topic'] for r in corpus.records})==8
    nodes=LexicalSourceRetriever(corpus.records).retrieve(case['question'])
    assert {n.node.metadata['source_id'] for n in nodes}=={'SUPPORT-001','SUPPORT-002','SUPPORT-003'}
    assert {r['sample_size'] for r in corpus.records if r['topic']=='helio-support'}=={120}
    for name in ('different-periods','different-populations'):assert conflicts(select(name)[1].records)=={}
    assert conflicts(select('contradictory-surveys')[1].records)['q3-2026-paid-user-adoption']=={'42 percent':['SURVEY-301'],'58 percent':['SURVEY-077']}
    no_match,corpus,_=select('no-match');assert LexicalSourceRetriever(corpus.records).retrieve(no_match['question'])==[]
    assert max(len(r['text']) for r in select('long-context')[1].records)>12000


@pytest.mark.parametrize('fault',['content','identity','path','symlink','population'])
def test_changed_hash_identity_or_escaping_manifest_fails(fault,tmp_path):
    root=tmp_path/'data';shutil.copytree(data_root(),root);file=root/'manifest.json';manifest=json.loads(file.read_text());case=manifest['cases'][0]
    target=root/case['file'];data=json.loads(target.read_text())
    if fault=='content':data['sources'][0]['text']+=' Changed.';target.write_text(json.dumps(data))
    elif fault=='identity':
        data['dataset']['case_id']='different';target.write_text(json.dumps(data));case['sha256']=sha(target.read_bytes())
    elif fault=='path':case['file']='../outside.json'
    elif fault=='symlink':
        external=tmp_path/'external.json';external.write_bytes(target.read_bytes());target.unlink();target.symlink_to(external)
    else:case['source_count']+=1
    file.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):load_manifest(root)
