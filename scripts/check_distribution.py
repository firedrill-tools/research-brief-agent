"""Install both distributions with fresh locked dependencies outside checkout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import tomllib
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
UV=os.environ.get('UV') or shutil.which('uv')
if not UV:raise RuntimeError('uv is required for distribution verification')
VERSION=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
wheel=ROOT/'dist'/f'research_brief_agent-{VERSION}-py3-none-any.whl'
sdist=ROOT/'dist'/f'research_brief_agent-{VERSION}.tar.gz'
env={**os.environ}
for key in ('GOOGLE_API_KEY','GEMINI_API_KEY','GEMINI_MODEL','GOOGLE_GENAI_USE_VERTEXAI','GOOGLE_GENAI_USE_ENTERPRISE','VIRTUAL_ENV','PYTHONPATH','PYTHONHOME'):env.pop(key,None)


def run(command,cwd,check=True):
    return subprocess.run(command,cwd=cwd,env=env,check=check,text=True,capture_output=True,timeout=180)


def exercise(python,base):
    cli=[str(python),'-I','-m','research_brief.cli']
    run([str(python.parent/'research-brief'),'--help'],base)
    manifest=json.loads(run([*cli,'--list-cases'],base).stdout)
    assert len(manifest['cases'])==10 and manifest['version']==1
    for case in manifest['cases']:
        file=base/f'{case["id"]}.json';selected=json.loads(run([*cli,'--init-case',case['id'],'--sources',str(file)],base).stdout)
        assert selected['sha256']==case['sha256'] and file.stat().st_mode&0o777==0o600
    result=json.loads(run([*cli,'--case','no-match'],base).stdout)
    assert result['execution_kind']=='model_free_no_match' and result['reported_usage']['prepared_attempts']==0
    failed=run([*cli,'--case','starter'],base,False);assert failed.returncode==1
    receipt=json.loads(Path(json.loads(failed.stderr)['receipt_path']).read_text())
    assert receipt['status']=='failed' and receipt['provider_observations']==[] and receipt['result'] is None
    program='''
from pathlib import Path
import sys
import research_brief
from llama_index.core.base.response.schema import Response
from research_brief.research import assess,conflicts
from research_brief.retrieval import LexicalSourceRetriever
from research_brief.sources import SourceCorpus
assert Path(research_brief.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
base=Path(sys.argv[1]);corpus=SourceCorpus(base/'busy.json');before=corpus.path.read_bytes()
assert len(corpus.records)==24 and len({r['topic'] for r in corpus.records})==8
nodes=LexicalSourceRetriever(corpus.records).retrieve('Summarize Helio support findings in Q3 and their limitations.')
assert {n.node.metadata['source_id'] for n in nodes}=={'SUPPORT-001','SUPPORT-002','SUPPORT-003'}
result=assess(Response(response='A synthetic boundary assertion [1].',source_nodes=nodes),corpus,{n.node.metadata['source_id'] for n in nodes})
assert result['status']=='draft' and len(result['cited_source_ids'])==1
assert conflicts(SourceCorpus(base/'different-periods.json').records)=={}
assert corpus.path.read_bytes()==before
'''
    run([str(python),'-I','-c',program,str(base)],base)


with TemporaryDirectory(prefix='research-distribution-') as directory:
    temp=Path(directory)
    with ZipFile(wheel) as archive:
        assert 'research_brief/sample_data/manifest.json' in archive.namelist()
        assert len([n for n in archive.namelist() if n.startswith('research_brief/sample_data/') and n.endswith('.json')])==11
    requirements=temp/'requirements.txt'
    requirements.write_text(run([UV,'export','--locked','--no-dev','--no-emit-project','--format','requirements-txt'],ROOT).stdout)
    wheel_env=temp/'wheel-env';run([UV,'venv','--python',sys.executable,str(wheel_env)],temp)
    wheel_python=wheel_env/'bin/python'
    run([UV,'pip','sync','--python',str(wheel_python),str(requirements)],temp)
    run([UV,'pip','install','--python',str(wheel_python),'--no-deps',str(wheel)],temp)
    wheel_case=temp/'wheel-case';wheel_case.mkdir();exercise(wheel_python,wheel_case)
    source_root=temp/'source';source_root.mkdir()
    with tarfile.open(sdist) as archive:archive.extractall(source_root,filter='data')
    source,=source_root.iterdir();assert (source/'uv.lock').exists()
    run([UV,'sync','--locked','--no-dev','--no-editable','--project',str(source)],temp)
    source_case=temp/'source-case';source_case.mkdir();exercise(source/'.venv/bin/python',source_case)
print('Wheel and sdist passed fresh locked installs, console/module CLI, ten private cases, model-free no-match, failed-key receipts and actual source/chunk assessment outside checkout. No provider or semantic quality claim.')
