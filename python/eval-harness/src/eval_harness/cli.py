import asyncio
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

from .cache import create_file_cache, null_cache, verdict_cache_key
from .config import load_config
from .datasets import Scenario, load_scenarios
from .judge import Verdict, judge_scenario
from .judge_client import create_judge_client
from .log import log
from .report import format_report, summarize
from .runner import RunnerDeps, run_evaluation

USAGE = """eval-harness run <dataset.jsonl> [options]

Options:
  --no-cache        ignore cached verdicts and re-judge every scenario
  -h, --help        show this message
"""


@dataclass(frozen=True)
class Args:
    dataset_path: str
    use_cache: bool


def parse_args(argv: list[str]) -> Args | None:
    if len(argv) == 0 or argv[0] != "run":
        return None

    dataset_path: str | None = None
    use_cache = True

    for arg in argv[1:]:
        if arg == "--no-cache":
            use_cache = False
        elif arg in ("-h", "--help"):
            return None
        elif arg.startswith("-"):
            raise ValueError(f'unknown option "{arg}"')
        elif dataset_path is None:
            dataset_path = arg
        else:
            raise ValueError(f'unexpected argument "{arg}"')

    return None if dataset_path is None else Args(dataset_path=dataset_path, use_cache=use_cache)


async def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args is None:
        sys.stdout.write(USAGE)
        return 2

    config = load_config()
    scenarios = await load_scenarios(args.dataset_path)
    client = create_judge_client(config.judge)
    cache = create_file_cache(config.cache_dir) if args.use_cache and config.cache_enabled else null_cache

    log.info("starting run", scenarios=len(scenarios), model=config.judge.model)

    async def judge(scenario: Scenario) -> Verdict:
        return await judge_scenario(client, scenario, config.judge)

    def cache_key(scenario: Scenario) -> str:
        return verdict_cache_key(
            scenario=scenario,
            model=config.judge.model,
            prompt_version=config.judge.prompt_version,
        )

    run = await run_evaluation(
        scenarios,
        RunnerDeps(
            judge=judge, cache=cache, cache_key=cache_key, concurrency=config.concurrency
        ),
    )

    summary = summarize(run)
    log.info("run finished", scored=summary.scored, errored=summary.errored)

    sys.stdout.write(f"{format_report(run)}\n")
    return 1 if summary.errored > 0 else 0


def run() -> None:
    load_dotenv()
    try:
        code = asyncio.run(main(sys.argv[1:]))
    except Exception as error:
        sys.stderr.write(f"{error}\n")
        code = 1
    sys.exit(code)
