import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from llm_connections.game import (
    FileNotFoundError,
    Game,
    Group,
    InvalidGuessError,
    _file_exists,
    _file_is_up_to_date,
    download_connections,
    most_recent_date,
)

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


@pytest.fixture
def connections_path(tmp_path, monkeypatch):
    path = tmp_path / "connections.json"
    monkeypatch.setattr("llm_connections.game.CONNECTIONS_FILE", str(path))
    return path


class TestGroup:
    def test_parses_level_group_and_members(self):
        group = Group(SAMPLE_ANSWERS[0])

        assert group.level == 0
        assert group.name == "WET WEATHER"
        assert group.members == ["HAIL", "RAIN", "SLEET", "SNOW"]
        assert group.solved is False
        assert group.data is SAMPLE_ANSWERS[0]

    @pytest.mark.parametrize(
        ("level", "color"),
        [
            (0, "Yellow"),
            (1, "Green"),
            (2, "Blue"),
            (3, "Purple"),
        ],
    )
    def test_color_matches_difficulty_level(self, level, color):
        group = Group({"level": level, "group": "GROUP", "members": []})

        assert group.color() == color

    def test_color_returns_none_for_unknown_level(self):
        group = Group({"level": 4, "group": "GROUP", "members": []})

        assert group.color() is None


class TestGame:
    def test_parses_id_date_and_answers(self):
        game = Game(SAMPLE_GAME)

        assert game.id == 42
        assert game.date == datetime(2026, 9, 15)
        assert len(game.groups) == 4
        assert all(isinstance(group, Group) for group in game.groups)
        assert game.groups[2].name == "KEYBOARD KEYS"

    def test_all_entries_returns_every_member(self):
        game = Game(SAMPLE_GAME)

        assert game.all_entries() == [
            "HAIL",
            "RAIN",
            "SLEET",
            "SNOW",
            "BUCKS",
            "HEAT",
            "JAZZ",
            "NETS",
            "OPTION",
            "RETURN",
            "SHIFT",
            "TAB",
            "KAYAK",
            "LEVEL",
            "MOM",
            "RACECAR",
        ]

    def test_unsolved_entries_includes_every_member_when_nothing_is_solved(self):
        game = Game(SAMPLE_GAME)

        assert game.unsolved_entries() == [
            "HAIL",
            "RAIN",
            "SLEET",
            "SNOW",
            "BUCKS",
            "HEAT",
            "JAZZ",
            "NETS",
            "OPTION",
            "RETURN",
            "SHIFT",
            "TAB",
            "KAYAK",
            "LEVEL",
            "MOM",
            "RACECAR",
        ]

    def test_unsolved_entries_omits_members_from_solved_answers(self):
        game = Game(SAMPLE_GAME)
        game.groups[0].solved = True

        assert game.unsolved_entries() == [
            "BUCKS",
            "HEAT",
            "JAZZ",
            "NETS",
            "OPTION",
            "RETURN",
            "SHIFT",
            "TAB",
            "KAYAK",
            "LEVEL",
            "MOM",
            "RACECAR",
        ]

    def test_load_all_raises_when_file_is_missing(self, connections_path):
        with pytest.raises(FileNotFoundError, match="Connections file not found"):
            Game.load_all()

    def test_load_all_skips_games_before_august_2026(self, connections_path):
        connections_path.write_text(
            json.dumps(
                [
                    {"id": 1, "date": "2026-07-31", "answers": SAMPLE_ANSWERS},
                    {"id": 2, "date": "2026-08-01", "answers": SAMPLE_ANSWERS},
                    {"id": 3, "date": "2026-09-02", "answers": SAMPLE_ANSWERS},
                ]
            )
        )

        games = Game.load_all()

        assert [game.id for game in games] == [2, 3]
        assert games[0].date == datetime(2026, 8, 1)

    def test_load_loads_game_for_date(self, connections_path):
        connections_path.write_text(
            json.dumps(
                [
                    {"id": 1, "date": "2026-09-01", "answers": SAMPLE_ANSWERS},
                    {"id": 2, "date": "2026-09-02", "answers": SAMPLE_ANSWERS},
                ]
            )
        )
        game = Game.load(datetime(2026, 9, 1))
        assert game.id == 1
        assert game.date == datetime(2026, 9, 1)

    def test_load_raises_when_game_not_found(self, connections_path):
        connections_path.write_text(
            json.dumps(
                [
                    {"id": 1, "date": "2026-09-01", "answers": SAMPLE_ANSWERS},
                    {"id": 2, "date": "2026-09-02", "answers": SAMPLE_ANSWERS},
                ]
            )
        )
        with pytest.raises(ValueError, match="Game not found for date: 2026-09-03"):
            Game.load(datetime(2026, 9, 3))


class TestValidateGuess:
    def test_accepts_four_unique_unsolved_entries(self):
        game = Game(SAMPLE_GAME)

        assert game._validate_guess(["HAIL", "RAIN", "SLEET", "SNOW"]) is True

    def test_accepts_entries_in_any_order(self):
        game = Game(SAMPLE_GAME)

        assert game._validate_guess(["SNOW", "SLEET", "RAIN", "HAIL"]) is True

    @pytest.mark.parametrize(
        "guess",
        [
            [],
            ["HAIL"],
            ["HAIL", "RAIN", "SLEET"],
            ["HAIL", "RAIN", "SLEET", "SNOW", "BUCKS"],
        ],
    )
    def test_rejects_wrong_number_of_entries(self, guess):
        game = Game(SAMPLE_GAME)

        with pytest.raises(InvalidGuessError, match="Guess must be 4 unique entries"):
            game._validate_guess(guess)

    def test_rejects_duplicate_entries(self):
        game = Game(SAMPLE_GAME)

        with pytest.raises(InvalidGuessError, match="Guess must be 4 unique entries"):
            game._validate_guess(["HAIL", "RAIN", "SLEET", "HAIL"])

    def test_rejects_entries_not_in_the_game(self):
        game = Game(SAMPLE_GAME)

        with pytest.raises(InvalidGuessError, match="Invalid entries: \\['NOTAWORD'\\]"):
            game._validate_guess(["HAIL", "RAIN", "SLEET", "NOTAWORD"])

    def test_rejects_multiple_invalid_entries(self):
        game = Game(SAMPLE_GAME)

        with pytest.raises(InvalidGuessError, match="Invalid entries:"):
            game._validate_guess(["FOO", "BAR", "SLEET", "SNOW"])

    def test_rejects_entries_from_already_solved_groups(self):
        game = Game(SAMPLE_GAME)
        game.groups[0].solved = True

        with pytest.raises(
            InvalidGuessError,
            match="Entry already used in a solved group:",
        ):
            game._validate_guess(["HAIL", "RAIN", "SLEET", "SNOW"])

    def test_rejects_guess_that_mixes_solved_and_unsolved_entries(self):
        game = Game(SAMPLE_GAME)
        game.groups[0].solved = True

        with pytest.raises(
            InvalidGuessError,
            match="Entry already used in a solved group:",
        ):
            game._validate_guess(["HAIL", "BUCKS", "HEAT", "JAZZ"])

    def test_rejects_duplicate_guess(self):
        game = Game(SAMPLE_GAME)
        guess = [group["members"][0] for group in SAMPLE_ANSWERS]
        game._validate_guess(guess)
        with pytest.raises(InvalidGuessError, match="Duplicate guess:"):
            game._validate_guess(guess)


class TestCheckGuess:
    def test_returns_none_for_incorrect_guess(self):
        game = Game(SAMPLE_GAME)

        result = game.check_guess(["HAIL", "BUCKS", "OPTION", "KAYAK"])

        assert result is None
        assert all(not group.solved for group in game.groups)

    def test_marks_matching_group_solved_on_correct_guess(self):
        game = Game(SAMPLE_GAME)

        result = game.check_guess(["HAIL", "RAIN", "SLEET", "SNOW"])
        assert result is game.groups[0]
        assert result.solved is True
        assert game.groups[0].solved is True
        assert result.name == "WET WEATHER"

    def test_correct_guess_is_order_independent(self):
        game = Game(SAMPLE_GAME)

        guess = ["SNOW", "HAIL", "SLEET", "RAIN"]
        result = game.check_guess(guess)
        assert result is game.groups[0]
        assert result.solved is True
        assert game.groups[0].solved is True
        assert result.name == "WET WEATHER"

    def test_does_not_rematch_already_solved_group(self):
        game = Game(SAMPLE_GAME)
        game.groups[0].solved = True

        with pytest.raises(InvalidGuessError, match="Entry already used in a solved group"):
            game.check_guess(["HAIL", "RAIN", "SLEET", "SNOW"])

    def test_raises_for_invalid_guess_before_checking_answers(self):
        game = Game(SAMPLE_GAME)

        with pytest.raises(InvalidGuessError, match="Guess must be 4 unique entries"):
            game.check_guess(["HAIL", "RAIN"])

        assert all(not group.solved for group in game.groups)

    def test_can_solve_a_later_group_after_an_earlier_one(self):
        game = Game(SAMPLE_GAME)
        game.groups[0].solved = True

        result = game.check_guess(["BUCKS", "HEAT", "JAZZ", "NETS"])
        assert result is game.groups[1]
        assert result.solved is True
        assert game.groups[1].solved is True
        assert game.groups[1].name == "NBA TEAMS"

    def test_increments_mistakes_on_incorrect_guess(self):
        game = Game(SAMPLE_GAME)

        game.check_guess(["HAIL", "BUCKS", "OPTION", "KAYAK"])

        assert game.mistakes == 1
        assert game.is_lost() is False

    def test_is_lost_after_four_mistakes(self):
        game = Game(SAMPLE_GAME)
        wrong_guesses = [
            ["HAIL", "BUCKS", "OPTION", "KAYAK"],
            ["HAIL", "BUCKS", "OPTION", "LEVEL"],
            ["HAIL", "BUCKS", "OPTION", "MOM"],
            ["HAIL", "BUCKS", "OPTION", "RACECAR"],
        ]

        for guess in wrong_guesses:
            assert game.check_guess(guess) is None

        assert game.mistakes == 4
        assert game.is_lost() is True

    def test_raises_when_guessing_after_loss(self):
        game = Game(SAMPLE_GAME)
        game.mistakes = 4

        with pytest.raises(InvalidGuessError, match="too many mistakes"):
            game.check_guess(["HAIL", "RAIN", "SLEET", "SNOW"])

    def test_is_solved_when_all_groups_are_solved(self):
        game = Game(SAMPLE_GAME)
        assert game.is_solved() is False

        for group in game.groups:
            group.solved = True

        assert game.is_solved() is True
        assert game.solved_groups() == game.groups
        assert game.solved_entries() == game.all_entries()
        assert game.unsolved_entries() == []

    def test_day_returns_date(self):
        game = Game(SAMPLE_GAME)
        assert game.day() == datetime(2026, 9, 15).date()


class TestFileHelpers:
    def test_file_exists_when_present(self, connections_path):
        connections_path.write_text("[]")

        assert _file_exists() is True

    def test_file_does_not_exist_when_missing(self, connections_path):
        assert _file_exists() is False

    def test_file_is_not_up_to_date_when_missing(self, connections_path):
        assert _file_is_up_to_date() is False

    def test_file_is_not_up_to_date_when_empty(self, connections_path):
        connections_path.write_text("[]")

        assert _file_is_up_to_date() is False

    def test_file_is_up_to_date_when_latest_puzzle_is_today(self, connections_path):
        today = datetime.now().date().isoformat()
        connections_path.write_text(
            json.dumps([{"id": 1, "date": today, "answers": SAMPLE_ANSWERS}])
        )

        assert _file_is_up_to_date() is True

    def test_file_is_up_to_date_when_latest_puzzle_is_yesterday(self, connections_path):
        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
        connections_path.write_text(
            json.dumps([{"id": 1, "date": yesterday, "answers": SAMPLE_ANSWERS}])
        )

        assert _file_is_up_to_date() is True

    def test_file_is_stale_when_latest_puzzle_is_older_than_one_day(
        self, connections_path
    ):
        old = (datetime.now().date() - timedelta(days=2)).isoformat()
        connections_path.write_text(
            json.dumps([{"id": 1, "date": old, "answers": SAMPLE_ANSWERS}])
        )

        assert _file_is_up_to_date() is False


class TestMostRecentDate:
    def test_returns_none_when_missing(self, connections_path):
        assert most_recent_date() is None

    def test_returns_none_when_empty(self, connections_path):
        connections_path.write_text("[]")
        assert most_recent_date() is None

    def test_returns_latest_puzzle_date(self, connections_path):
        connections_path.write_text(
            json.dumps(
                [
                    {"id": 1, "date": "2026-09-01", "answers": SAMPLE_ANSWERS},
                    {"id": 2, "date": "2026-09-10", "answers": SAMPLE_ANSWERS},
                    {"id": 3, "date": "2026-09-05", "answers": SAMPLE_ANSWERS},
                ]
            )
        )

        assert most_recent_date() == datetime(2026, 9, 10).date()


class TestDownloadConnections:
    def test_skips_download_when_file_is_fresh(self, connections_path):
        today = datetime.now().date().isoformat()
        connections_path.write_text(
            json.dumps([{"id": 1, "date": today, "answers": SAMPLE_ANSWERS}])
        )

        with patch("llm_connections.game.requests.get") as get:
            download_connections()

        get.assert_not_called()

    def test_downloads_and_writes_file_when_missing(self, connections_path):
        payload = [{"id": 1, "date": "2026-09-01", "answers": []}]
        response = Mock()
        response.json.return_value = payload

        with patch("llm_connections.game.requests.get", return_value=response) as get:
            download_connections()

        get.assert_called_once_with(
            "https://github.com/Eyefyre/NYT-Connections-Answers/raw/main/connections.json"
        )
        response.raise_for_status.assert_called_once()
        assert json.loads(connections_path.read_text()) == payload

    def test_downloads_when_latest_puzzle_is_stale(self, connections_path):
        old = (datetime.now().date() - timedelta(days=2)).isoformat()
        connections_path.write_text(
            json.dumps([{"id": 1, "date": old, "answers": SAMPLE_ANSWERS}])
        )
        payload = [{"id": 2, "date": datetime.now().date().isoformat(), "answers": []}]
        response = Mock()
        response.json.return_value = payload

        with patch("llm_connections.game.requests.get", return_value=response) as get:
            download_connections()

        get.assert_called_once()
        assert json.loads(connections_path.read_text()) == payload

    def test_raises_when_request_fails(self, connections_path):
        response = Mock()
        response.raise_for_status.side_effect = Exception("boom")

        with patch("llm_connections.game.requests.get", return_value=response):
            with pytest.raises(Exception, match="boom"):
                download_connections()

        assert not connections_path.exists()
