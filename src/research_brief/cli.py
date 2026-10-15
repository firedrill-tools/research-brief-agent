import argparse
import json
from pathlib import Path

from .research import ResearchBriefService


def main() -> None:
    parser = argparse.ArgumentParser(description="LlamaIndex/Gemini sourced research brief")
    parser.add_argument("question")
    parser.add_argument("--sources", type=Path, default=Path("fixtures/sources.json"))
    parser.add_argument("--model", help="enabled Gemini model name")
    args = parser.parse_args()
    result = ResearchBriefService(args.sources).brief(args.question, args.model)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
