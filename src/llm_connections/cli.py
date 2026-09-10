import argparse
from datetime import date, timedelta

from llm_connections.backfill import (
    DEFAULT_END,
    DEFAULT_START,
    MODELS,
    run_backfill,
)
from llm_connections.engine import run_game
from llm_connections.game import download_connections, most_recent_date
from llm_connections.log import GameAlreadyCompletedError, list_results
from llm_connections.nightly import run_nightly
from llm_connections.telemetry import init_sentry, nightly_checkin


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _require_date_range(args: argparse.Namespace) -> None:
    if args.end < args.start:
        raise SystemExit("end date must be on or after start date")


def cmd_update(_args: argparse.Namespace) -> None:
    download_connections()
    latest_date = most_recent_date()
    if latest_date is not None:
        print(f"Latest Game: {latest_date}")


def cmd_run(args: argparse.Namespace) -> None:
    _require_date_range(args)

    day = args.start
    while day <= args.end:
        try:
            run_game(day, model=args.model, force=args.force)
        except GameAlreadyCompletedError as exc:
            print(exc)
        day += timedelta(days=1)


def cmd_list(args: argparse.Namespace) -> None:
    _require_date_range(args)

    results = list_results(args.start, args.end, args.model)
    if not results:
        print(f"No results for {args.model} between {args.start} and {args.end}")
        return

    solved = lost = in_progress = 0
    for result in results:
        status = result.get("status", "?")
        if status == "completed":
            outcome = result.get("outcome", "?")
            mistakes = result.get("mistakes", "?")
            invalid = result.get("invalid_guesses")
            line = f"{result['date']}  {outcome:<7}  mistakes={mistakes}"
            if invalid is not None:
                line += f"  invalid={invalid}"
            print(line)
            if outcome == "solved":
                solved += 1
            elif outcome == "lost":
                lost += 1
        else:
            print(f"{result['date']}  {status}")
            in_progress += 1

    print(
        f"\n{len(results)} games — "
        f"{solved} solved, {lost} lost, {in_progress} in progress"
    )


def cmd_backfill(args: argparse.Namespace) -> None:
    _require_date_range(args)
    models = args.model or None
    run_backfill(start=args.start, end=args.end, models=models)


def cmd_nightly(args: argparse.Namespace) -> None:
    models = args.model or None
    # Wrap nightly run in a checkin to report start/end times, and capture runtime exceptions.
    with nightly_checkin() as finish:
        failed = run_nightly(models=models)
        finish(failed == 0)
    if failed:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Connections tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    update_parser = subparsers.add_parser(
        "update",
        help="Download/update the local connections puzzle data",
    )
    update_parser.set_defaults(func=cmd_update)

    run_parser = subparsers.add_parser(
        "run",
        help="Run Connections games for a date range",
    )
    run_parser.add_argument("start", type=_parse_date, help="Start date (YYYY-MM-DD)")
    run_parser.add_argument("end", type=_parse_date, help="End date (YYYY-MM-DD)")
    run_parser.add_argument("model", help="LLM model id (e.g. openai/gpt-4.1)")
    run_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite completed runs",
    )
    run_parser.set_defaults(func=cmd_run)

    list_parser = subparsers.add_parser(
        "list",
        help="List logged results for a model and date range",
    )
    list_parser.add_argument("start", type=_parse_date, help="Start date (YYYY-MM-DD)")
    list_parser.add_argument("end", type=_parse_date, help="End date (YYYY-MM-DD)")
    list_parser.add_argument("model", help="LLM model id (e.g. openai/gpt-4.1)")
    list_parser.set_defaults(func=cmd_list)

    backfill_parser = subparsers.add_parser(
        "backfill",
        help=(
            "Run the benchmark model suite over a date range "
            "(skips dates that already have an entry)"
        ),
    )
    backfill_parser.add_argument(
        "start",
        type=_parse_date,
        nargs="?",
        default=DEFAULT_START,
        help=f"Start date (YYYY-MM-DD), default {DEFAULT_START}",
    )
    backfill_parser.add_argument(
        "end",
        type=_parse_date,
        nargs="?",
        default=DEFAULT_END,
        help=f"End date (YYYY-MM-DD), default {DEFAULT_END}",
    )
    backfill_parser.add_argument(
        "--model",
        action="append",
        metavar="MODEL",
        help=(
            "Limit to one or more models (repeatable). "
            f"Default suite has {len(MODELS)} models — edit "
            "llm_connections.backfill.MODELS to change it."
        ),
    )
    backfill_parser.set_defaults(func=cmd_backfill)

    nightly_parser = subparsers.add_parser(
        "nightly",
        help=(
            "Refresh connections data and run the model suite for the last week of data"
        ),
    )
    nightly_parser.add_argument(
        "--model",
        action="append",
        metavar="MODEL",
        help=(
            "Limit to one or more models (repeatable). "
            f"Default suite has {len(MODELS)} models."
        ),
    )
    nightly_parser.set_defaults(func=cmd_nightly)

    args = parser.parse_args()
    init_sentry(command=args.command)
    args.func(args)


if __name__ == "__main__":
    main()
