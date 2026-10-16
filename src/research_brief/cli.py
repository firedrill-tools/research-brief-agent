"""Noninteractive async research briefs and model-free data selection."""
import argparse
import asyncio
import json
from pathlib import Path
import signal
import sys

from .datasets import initialize,list_cases,select
from .research import ResearchBriefService

DEFAULT_ENDPOINT='https://generativelanguage.googleapis.com'


async def run(service,question,top_k,args):
    loop=asyncio.get_running_loop();task=asyncio.current_task();previous=signal.getsignal(signal.SIGTERM)
    loop.add_signal_handler(signal.SIGTERM,task.cancel)
    try:return await service.brief_async(question,args.model,top_k=top_k,output_root=args.output_root,base_url=args.base_url,timeout_seconds=args.timeout)
    finally:loop.remove_signal_handler(signal.SIGTERM);signal.signal(signal.SIGTERM,previous)


def main(argv=None):
    parser=argparse.ArgumentParser(description='LlamaIndex/Gemini sourced research brief',allow_abbrev=False)
    parser.add_argument('question',nargs='?')
    group=parser.add_mutually_exclusive_group();group.add_argument('--case');group.add_argument('--list-cases',action='store_true');group.add_argument('--init-case')
    parser.add_argument('--sources',type=Path,help='custom collection, or new destination for --init-case')
    parser.add_argument('--model',help='enabled Gemini Developer API model name; or GEMINI_MODEL')
    parser.add_argument('--top-k',type=int)
    parser.add_argument('--output-root',type=Path)
    parser.add_argument('--timeout',type=float,default=120)
    parser.add_argument('--base-url',default=DEFAULT_ENDPOINT,help='explicit Developer API endpoint; HTTPS or loopback HTTP')
    args=parser.parse_args(argv)
    if (args.case or args.list_cases or args.init_case) and args.question:parser.error('a selected case already supplies its question')
    if args.case and args.sources:parser.error('--case and custom --sources are separate input selections')
    if args.list_cases and args.sources:parser.error('--list-cases uses the bundled manifest')
    if (args.list_cases or args.init_case) and (args.model or args.top_k is not None or args.output_root or args.timeout!=120 or args.base_url!=DEFAULT_ENDPOINT):parser.error('list/init does not execute a model')
    try:
        if args.list_cases:output=list_cases()
        elif args.init_case:
            if args.sources is None:parser.error('--init-case requires a new --sources destination')
            output=initialize(args.init_case,args.sources)
        else:
            if args.case:case,corpus,_=select(args.case);question=case['question']
            else:
                if not args.question:parser.error('supply a question or --case')
                case,corpus,_=select('starter');question=args.question
                if args.sources is not None:
                    from .sources import SourceCorpus
                    corpus=SourceCorpus(args.sources)
            top_k=args.top_k if args.top_k is not None else case['top_k']
            output=asyncio.run(run(ResearchBriefService(corpus.path),question,top_k,args))
        print(json.dumps(output,indent=2));return 0
    except (Exception,asyncio.CancelledError,KeyboardInterrupt) as error:
        source=error if getattr(error,'evidence',None) is not None else error.__context__
        print(json.dumps({'error':str(error) or type(error).__name__,'type':type(error).__name__,'receipt_path':getattr(source,'receipt_path',None),
            'evidence_error':getattr(source,'evidence',{}).get('evidence_error') if getattr(source,'evidence',None) else None}),file=sys.stderr)
        return 130 if isinstance(error,(asyncio.CancelledError,KeyboardInterrupt)) else 1


if __name__=='__main__':raise SystemExit(main())
