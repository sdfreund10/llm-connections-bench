import datetime
import json
from llm_connections.llm import OpenAIChat
from llm_connections.game import Game, InvalidGuessError
from llm_connections.log import start_run, log_guess, complete_run

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


def run_game(date: datetime.date, model='openai/gpt-4.1', force: bool = False):
    start_run(date, model, force=force)
    game = Game.load(date)
    chat = OpenAIChat(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        response_schema={
            "type": "object",
            "properties": {
                "guess": {"type": "array", "items": {"type": "string"}},
                "reasoning": {"type": "string"},
            },
            "required": ["guess", "reasoning"],
        }
    )
    # TODO: Maybe log latency?
    invalid_guesses = 0
    while not game.is_solved() and not game.is_lost():
        guess = chat.send(f"{_serialize_game(game)}")
        guess = json.loads(guess)
        try:
            result = game.check_guess(guess['guess'])
        except InvalidGuessError as e:
            chat.send(f"Invalid guess: {e}")
            invalid_guesses += 1
            continue
        guess['success'] = result is not None
        log_guess(date, model, guess)

    outcome = "solved" if game.is_solved() else "lost"
    complete_run(date, model, outcome=outcome, mistakes=game.mistakes, invalid_guesses=invalid_guesses)
    print(f"[{date}] Game {outcome}! ({game.mistakes} mistakes)")
