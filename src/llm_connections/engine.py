import datetime
import json
from llm_connections.llm import AIChat
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

# TODO: Some models, like claude-sonnet-5, blow up with thinking tokens. We may need to default to low effort or something.
# Defaulting to low effort or turning off thinking tokens may save money and help with latency.
def run_game(date: datetime.date, model='openai/gpt-4.1', force: bool = False):
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

    llm_wait_s = 0.0
    input_tokens = 0
    output_tokens = 0
    total_cost = 0.0
    invalid_guesses = 0
    guess_error = None
    while not game.is_solved() and not game.is_lost():
        body = f"{_serialize_game(game)}"
        if guess_error is not None:
            body = f"Invalid guess - Please try again. {guess_error}\n\n{body}"

        content, usage = chat.send(body)
        llm_wait_s += usage.latency
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens
        total_cost += usage.total_cost

        guess = json.loads(content)
        guess = guess | usage.to_dict()
        try:
            result = game.check_guess(guess['guess'])
            guess_error = None
            guess['success'] = result is not None
            guess['invalid'] = False
        except InvalidGuessError as err:
            guess_error = err
            invalid_guesses += 1
            guess['success'] = False
            guess['invalid'] = True
            guess['invalid_reason'] = str(err)
        log_guess(date, model, guess)

    outcome = "solved" if game.is_solved() else "lost"
    solved_groups = len(game.solved_groups())
    complete_run(
        date,
        model,
        outcome=outcome,
        mistakes=game.mistakes,
        invalid_guesses=invalid_guesses,
        solved_groups=solved_groups,
        llm_wait_s=llm_wait_s,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_cost=total_cost,
    )
    print(f"[{date}] Game {outcome}! ({game.mistakes} mistakes)")
