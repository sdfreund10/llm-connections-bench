import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from llm_connections.engine import _serialize_game, run_game
from llm_connections.game import Game
from llm_connections.llm import ChatUsage


SAMPLE_ANSWERS = [
    {
        "level": 0,
        "group": "WET WEATHER",
        "members": ["HAIL", "RAIN", "SLEET", "SNOW"],
    },
    {
        "level": 1,
        "group": "NBA TEAMS",
        "members": ["BUCKS", "HEAT", "JAZZ", "NETS"],
    },
    {
        "level": 2,
        "group": "KEYBOARD KEYS",
        "members": ["OPTION", "RETURN", "SHIFT", "TAB"],
    },
    {
        "level": 3,
        "group": "PALINDROMES",
        "members": ["KAYAK", "LEVEL", "MOM", "RACECAR"],
    },
]

SAMPLE_GAME = {
    "id": 42,
    "date": "2026-09-15",
    "answers": SAMPLE_ANSWERS,
}

DAY = date(2026, 9, 15)
MODEL = "openai/gpt-4.1"


def _usage(latency=0.1, input_tokens=10, output_tokens=5, total_cost=0.001):
    return ChatUsage(
        latency=latency,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_cost=total_cost,
    )


def _reply(guess, reasoning="because"):
    return json.dumps({"guess": guess, "reasoning": reasoning}), _usage()


class TestSerializeGame:
    def test_uncategorized_when_nothing_solved(self):
        game = Game(SAMPLE_GAME)
        text = _serialize_game(game)

        assert text.startswith("Uncategorized:")
        assert "HAIL" in text
        assert "WET WEATHER" not in text

    def test_includes_solved_groups_before_uncategorized(self):
        game = Game(SAMPLE_GAME)
        game.groups[0].solved = True
        text = _serialize_game(game)

        assert text.startswith("WET WEATHER: ['HAIL', 'RAIN', 'SLEET', 'SNOW']\n")
        assert "Uncategorized:" in text
        assert "HAIL" not in text.split("Uncategorized:")[1]
        assert "BUCKS" in text.split("Uncategorized:")[1]


class TestRunGame:
    @pytest.fixture
    def log_path(self, tmp_path, monkeypatch):
        path = tmp_path / "games.json"
        monkeypatch.setattr("llm_connections.log.LOG_FILE", str(path))
        return path

    def test_solves_and_completes_run(self, log_path):
        game = Game(SAMPLE_GAME)
        replies = [
            _reply(["HAIL", "RAIN", "SLEET", "SNOW"]),
            _reply(["BUCKS", "HEAT", "JAZZ", "NETS"]),
            _reply(["OPTION", "RETURN", "SHIFT", "TAB"]),
            _reply(["KAYAK", "LEVEL", "MOM", "RACECAR"]),
        ]
        chat = MagicMock()
        chat.send.side_effect = replies

        with (
            patch("llm_connections.engine.start_run") as start_run,
            patch("llm_connections.engine.Game.load", return_value=game),
            patch("llm_connections.engine.AIChat", return_value=chat),
            patch("llm_connections.engine.log_guess") as log_guess,
            patch("llm_connections.engine.complete_run") as complete_run,
        ):
            run_game(DAY, model=MODEL)

        start_run.assert_called_once_with(DAY, MODEL, force=False)
        assert log_guess.call_count == 4
        complete_run.assert_called_once()
        kwargs = complete_run.call_args.kwargs
        assert kwargs["outcome"] == "solved"
        assert kwargs["mistakes"] == 0
        assert kwargs["invalid_guesses"] == 0
        assert kwargs["solved_groups"] == 4
        assert kwargs["input_tokens"] == 40
        assert kwargs["output_tokens"] == 20
        assert kwargs["total_cost"] == pytest.approx(0.004)

    def test_counts_invalid_guess_and_retries(self, log_path):
        game = Game(SAMPLE_GAME)
        replies = [
            _reply(["HAIL", "RAIN"]),  # invalid — too few
            _reply(["HAIL", "RAIN", "SLEET", "SNOW"]),
            _reply(["BUCKS", "HEAT", "JAZZ", "NETS"]),
            _reply(["OPTION", "RETURN", "SHIFT", "TAB"]),
            _reply(["KAYAK", "LEVEL", "MOM", "RACECAR"]),
        ]
        chat = MagicMock()
        chat.send.side_effect = replies

        with (
            patch("llm_connections.engine.start_run"),
            patch("llm_connections.engine.Game.load", return_value=game),
            patch("llm_connections.engine.AIChat", return_value=chat),
            patch("llm_connections.engine.log_guess") as log_guess,
            patch("llm_connections.engine.complete_run") as complete_run,
        ):
            run_game(DAY, model=MODEL)

        assert log_guess.call_count == 5
        first_guess = log_guess.call_args_list[0].args[2]
        assert first_guess["invalid"] is True
        assert first_guess["success"] is False
        assert "invalid_reason" in first_guess

        second_body = chat.send.call_args_list[1].args[0]
        assert second_body.startswith("Invalid guess - Please try again.")

        kwargs = complete_run.call_args.kwargs
        assert kwargs["outcome"] == "solved"
        assert kwargs["invalid_guesses"] == 1
        assert kwargs["mistakes"] == 0

    def test_records_loss_after_four_mistakes(self, log_path):
        game = Game(SAMPLE_GAME)
        wrong = [
            ["HAIL", "BUCKS", "OPTION", "KAYAK"],
            ["HAIL", "BUCKS", "OPTION", "LEVEL"],
            ["HAIL", "BUCKS", "OPTION", "MOM"],
            ["HAIL", "BUCKS", "OPTION", "RACECAR"],
        ]
        chat = MagicMock()
        chat.send.side_effect = [_reply(g) for g in wrong]

        with (
            patch("llm_connections.engine.start_run"),
            patch("llm_connections.engine.Game.load", return_value=game),
            patch("llm_connections.engine.AIChat", return_value=chat),
            patch("llm_connections.engine.log_guess"),
            patch("llm_connections.engine.complete_run") as complete_run,
        ):
            run_game(DAY, model=MODEL)

        kwargs = complete_run.call_args.kwargs
        assert kwargs["outcome"] == "lost"
        assert kwargs["mistakes"] == 4
        assert kwargs["solved_groups"] == 0
        assert game.is_lost()
