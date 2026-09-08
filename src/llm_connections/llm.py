from dataclasses import dataclass
from openrouter import OpenRouter
from dotenv import load_dotenv
import os
import time
from openrouter.errors import TooManyRequestsResponseError

load_dotenv()


@dataclass(frozen=True)
class ChatUsage:
    latency: float
    input_tokens: int
    output_tokens: int
    total_cost: float

    def to_dict(self):
        return {
            "latency": self.latency,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_cost": self.total_cost,
        }


def chat(messages, model="~openai/gpt-latest"):
    with OpenRouter(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    ) as open_router:

        response = open_router.chat.send(
            model=model,
            messages=messages,
            stream=False
        )
        print(response)
        return response


class AIChat:
    def __init__(self, model="~openai/gpt-latest", system_prompt=None, response_schema=None):
        self.model = model
        self.messages = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

        self.response_schema = None
        if response_schema:
            self.response_schema = {
                "type": "json_schema",
                "json_schema": {
                    "name": "guess",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "guess": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "4 words or phrases that make up a group"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Reasoning for the guess"
                            }
                        },
                        "required": ["guess", "reasoning"],
                        "additionalProperties": False
                    }
                }
            }

    def send(self, message) -> tuple[str, ChatUsage]:
        self.messages.append({"role": "user", "content": message})
        try:
            return self._send_messages()
        except TooManyRequestsResponseError as e:
            print("Rate limit exceeded, resting for 30 seconds...")
            time.sleep(30)
            return self._send_messages()

    def _send_messages(self) -> tuple[str, ChatUsage]:
        with OpenRouter(
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
        ) as open_router:
            t0 = time.perf_counter()
            response = open_router.chat.send(
                model=self.model,
                messages=self.messages,
                response_format=self.response_schema,
                stream=False
            )
            latency = time.perf_counter() - t0
            message = response.choices[0].message
            usage = response.usage
            chat_usage = ChatUsage(
                latency=latency,
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                total_cost=float(getattr(usage, "cost", 0) or 0),
            )
            self.messages.append(
                {
                    "role": message.role,
                    "content": message.content,
                    "latency": chat_usage.latency,
                    "input_tokens": chat_usage.input_tokens,
                    "output_tokens": chat_usage.output_tokens,
                    "total_cost": chat_usage.total_cost,
                }
            )
        return message.content, chat_usage


# Pure rename - identical functionality
class OpenAIChat(AIChat):
    pass


class AnthropicChat(AIChat):
    pass
