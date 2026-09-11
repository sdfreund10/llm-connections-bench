# Pull connections history from https://github.com/Eyefyre/NYT-Connections-Answers and save it locally
import os
import json
import requests
from datetime import date, datetime, timedelta
from pathlib import Path

from llm_connections.applog import event

CONNECTIONS_URL = "https://github.com/Eyefyre/NYT-Connections-Answers/raw/main/connections.json"
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data"))
CONNECTIONS_FILE = os.path.join(DATA_DIR, "connections.json")

class FileNotFoundError(Exception):
    """Raised when the connections file is not found."""
    pass

def _file_exists():
    file_path = Path(CONNECTIONS_FILE)
    return file_path.exists()

def _file_is_up_to_date():
    if not _file_exists():
        return False
    latest_puzzle_date = most_recent_date()
    if latest_puzzle_date is None:
        return False

    return latest_puzzle_date >= datetime.now().date() - timedelta(days=1)


def download_connections():
    event("Updating connections file", stage="update", status="running")
    if _file_is_up_to_date():
        event("Connections file is up to date", stage="update", status="skipped")
        return

    response = requests.get(CONNECTIONS_URL)
    response.raise_for_status()
    with open(CONNECTIONS_FILE, "w") as f:
        json.dump(response.json(), f, indent=2)
    event("Connections file updated", stage="update", status="done")

def most_recent_date():
    if not _file_exists():
        return None
    with open(CONNECTIONS_FILE, "r") as f:
        entries = json.load(f)
        if len(entries) == 0:
            return None
        return max(datetime.strptime(entry["date"], "%Y-%m-%d") for entry in entries).date()

class Group:
    def __init__(self, data: dict):
        self.data = data
        self.level: int = data["level"]
        self.name: str = data["group"]
        self.members: list[str] = data["members"]
        self.solved = False

    def color(self):
        match self.level:
            case 0:
                return "Yellow"
            case 1:
                return "Green"
            case 2:
                return "Blue"
            case 3:
                return "Purple"


class InvalidGuessError(Exception):
    """Raised when the guess is invalid."""
    pass

class Game:
    def __init__(self, data: dict):
        self.data = data
        self.id: int = data["id"]
        self.date: datetime = datetime.strptime(data["date"], "%Y-%m-%d")
        self.groups: list[Group] = [Group(answer) for answer in data["answers"]]
        self.mistakes: int = 0
        self.guesses: list[set[str]] = []

    def is_solved(self):
        return all(group.solved for group in self.groups)

    def is_lost(self):
        return self.mistakes > 3

    def day(self):
        return self.date.date()

    def all_entries(self):
        return [member for group in self.groups for member in group.members]

    def unsolved_entries(self):
        entries = []
        for group in self.groups:
            if not group.solved:
                entries.extend(group.members)
        return entries

    def solved_entries(self):
        entries = []
        for group in self.groups:
            if group.solved:
                entries.extend(group.members)
        return entries
    def solved_groups(self):
        return [group for group in self.groups if group.solved]

    # Raises on invalid guess
    # Returns solved Group if the guess is correct
    # Otherwise returns None
    # TODO: Handle 1-away guesses
    def check_guess(self, guess: list[str]):
        if self.mistakes > 3:
            raise InvalidGuessError("You have made too many mistakes. You lose.")

        self._validate_guess(guess)
        for group in self.groups:
            if group.solved:
                continue

            if set(group.members) == set(guess):
                group.solved = True
                return group
        self.mistakes += 1
        return None

    def _validate_guess(self, guess: list[str]):
        if len(guess) != 4 or len(guess) != len(set(guess)):
            raise InvalidGuessError("Guess must be 4 unique entries")

        # validate each guess is a valid entry
        invalid_entries = []
        for entry in guess:
            if entry not in self.all_entries():
                invalid_entries.append(entry)

        if len(invalid_entries) > 0:
            raise InvalidGuessError(f"Invalid entries: {invalid_entries}")

        # validate none of the guessed entries are already solved
        solved_entries = []
        for entry in guess:
            if entry in self.solved_entries():
                solved_entries.append(entry)


        if len(solved_entries) > 0:
            raise InvalidGuessError(f"Entry already used in a solved group: {solved_entries}")

        # Validate the guess is not a duplicate of a previous guess
        if set(guess) in self.guesses:
            raise InvalidGuessError(f"Duplicate guess: {guess}")

        self.guesses.append(set(guess))
        return True

    @classmethod
    def load_all(clas):
        if not _file_exists():
            raise FileNotFoundError(f"Connections file not found at {CONNECTIONS_FILE}")

        with open(CONNECTIONS_FILE, "r") as f:
            entries = json.load(f)
            games = []
            for entry in entries:
                game_date = datetime.strptime(entry["date"], "%Y-%m-%d")
                if game_date < datetime(2026, 8, 1):
                    continue
                games.append(Game(entry))
            return games

    @classmethod
    def load(cls, date: date | datetime):
        all_games = cls.load_all()
        day = date.date() if isinstance(date, datetime) else date
        game = next((g for g in all_games if g.day() == day), None)
        if not game:
            raise ValueError(f"Game not found for date: {day}")
        return game