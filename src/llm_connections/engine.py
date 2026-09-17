import datetime
import json
from llm_connections.llm import AIChat, ChatUsage
from llm_connections.game import Game, InvalidGuessError
from llm_connections.log import start_run, log_guess, complete_run
from llm_connections.telemetry import record_game
from llm_connections.applog import event

SYSTEM_PROMPT = '''
You are trying to solve a game of Connections.
You will be given 16 words or phrases.
Each word or phrase belongs to one of four groups with a common theme.
You solve the game by identifying the secret groups.

EXAMPLES:
"Wet Weather" -> "HAIL", "RAIN", "SLEET", "SNOW"
"Letter Homophones" -> "ARE", "QUEUE", "SEA", "WHY"
"Slang For Toilet" -> "CAN", "HEAD", "JOHN", "THRONE"
"THINGS WITH WINGS" -> "AIRPLANE", "ANGEL", "BIRD", "PEGASUS"
"___ TRIANGLE" -> "ACUTE", "BERMUDA", "LOVE", "RIGHT"

At the start of the game, you will be given all 16 words or phrases.
On each turn, you will guess a group of 4 words or phrases you think make up a group.
You will then be told whether they form a correct group or not.
The game ends when you have solved all for 4 groups, or when you have made 4 mistakes.
'''

def _serialize_game(game: Game) -> str:
    serialized = ''
    for group in game.solved_groups():
        serialized += f'{group.name}: {group.members}\n'

    serialized += f"Uncategorized: {game.unsolved_entries()}\n"
    return serialized

# Models confirmed to work. More may worl, but are untested.
SUPPORTED_MODELS = [
    "openai/gpt-4.1",
    "anthropic/claude-haiku-4.5",
    "openai/gpt-4.1-mini",
    "google/gemini-3.7-flash",
]

# Maybe this should all be stored on the actual Game class? Whatever its fine for now.
class GameMetadata:
    def __init__(self):
        self.llm_wait_s = 0.0
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0
        self.invalid_guesses = 0
        self.guess_error = None
        self.solved_groups = 0
        self.outcome = None
        self.mistakes = 0

    def add_usage(self, usage: ChatUsage):
        self.llm_wait_s += usage.latency
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.total_cost += usage.total_cost

    def add_invalid_guess(self, err: Exception):
        self.guess_error = err
        self.invalid_guesses += 1

    def reset_guess_error(self):
        self.guess_error = None


class LLMResponseError(Exception):
    def __init__(self, err: Exception):
        self.err = err
        super().__init__(f"Unable to parse LLM response: {err}")

@record_game
def run_game(date: datetime.date, model='openai/gpt-4.1', force: bool = False) -> GameMetadata:
    start_run(date, model, force=force)
    game = Game.load(date)
    # Override with custom chat class if needed
    chat = AIChat(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        response_schema={
            "type": "object",
            "properties": {
                "guess": {"type": "array", "items": {"type": "string"}, "description": "The four words or phrases you think make up a group."},
                "reasoning": {"type": "string", "decsription": "Why the four words or phrases form a group."},
            },
            "required": ["guess", "reasoning"],
        }
    )

    metadata = GameMetadata()
    error_count = 0
    while not game.is_solved() and not game.is_lost():
        body = f"{_serialize_game(game)}"
        if metadata.guess_error is not None:
            body = f"Invalid guess - Please try again. {metadata.guess_error}\n\n{body}"

        content, usage = chat.send(body)
        metadata.add_usage(usage)

        guess = None
        try:
            guess = json.loads(content)
            guess = guess | usage.to_dict()

            result = game.check_guess(guess['guess'])
            metadata.reset_guess_error()
            guess['success'] = result is not None
            guess['invalid'] = False
        except InvalidGuessError as err:
            metadata.add_invalid_guess(err)
            guess['success'] = False
            guess['invalid'] = True
            guess['invalid_reason'] = str(err)
        except (json.JSONDecodeError, TypeError) as err:
            error_count += 1
            if error_count > 3:
                raise LLMResponseError(err)
            guess = usage.to_dict()
            guess['success'] = False
            guess['invalid'] = True
            guess['invalid_reason'] = str(err)
            metadata.add_invalid_guess(err)
            event(
                "Unable to parse LLM response",
                model=model,
                stage="guess",
                game_date=date,
                status="error",
                error=type(err).__name__,
                error_message=str(err),
            )

        log_guess(date, model, guess)

    metadata.outcome = "solved" if game.is_solved() else "lost"
    metadata.solved_groups = len(game.solved_groups())
    metadata.mistakes = game.mistakes
    complete_run(
        date,
        model,
        outcome=metadata.outcome,
        mistakes=game.mistakes,
        invalid_guesses=metadata.invalid_guesses,
        solved_groups=metadata.solved_groups,
        llm_wait_s=metadata.llm_wait_s,
        input_tokens=metadata.input_tokens,
        output_tokens=metadata.output_tokens,
        total_cost=metadata.total_cost,
    )
    event(
        f"Game {metadata.outcome}",
        stage="game",
        model=model,
        game_date=date,
        status="done",
        outcome=metadata.outcome,
        mistakes=metadata.mistakes,
    )
    return metadata
