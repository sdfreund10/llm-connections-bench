from llm_connections.llm import OpenAIChat
from llm_connections.game import Game
import datetime
import json

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

# LOG_FILE = 'data/games.json'
# def log_guess(date: datetime.date, llm_model: str, guess: dict):
#     with open(LOG_FILE, 'w') as f:
#         data = json.load(LOG_FILE)
#         data[date][llm_model].append(guess)
#         f.write(json.dumps(data), indent=4)


def run_game(date: datetime.date, model='openai/gpt-4.1'):
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
    while not game.is_solved() and not game.is_lost():
        guess = chat.send(f"{_serialize_game(game)}")
        guess = json.loads(guess)
        result = game.check_guess(guess['guess'])
        guess['success'] = result is not None
        # log_guess(date, model, guess)
        print(guess)
    if game.is_solved():
        print("Game solved!")
    else:
        print("Game lost!")

    # while not game.is_solved() and not game.is_lost():

    # Feed instructions on how to play to LLM
    # Feed initial game state to LLM
    # On each turn, feed result of guess and new game state
    # Log guess each & reasoning, and the result
    # At the end, log the final game state - solved & mistakes #