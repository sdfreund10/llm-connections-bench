from openrouter import OpenRouter
from openrouter.components import ResponseFormat, ChatFormatJSONSchemaConfig
from dotenv import load_dotenv
import os

load_dotenv()


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

class OpenAIChat:
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

            #             "type": "object",
            # "properties": {
            #     "guess": {"type": "array", "items": {"type": "string"}},
            #     "reasoning": {"type": "string"},
            # },
            # "required": ["guess", "guess"],

# "response_format": {
#     "type": "json_schema",
#     "json_schema": {
#       "name": "weather",
#       "strict": true,
#       "schema": {
#         "type": "object",
#         "properties": {
#           "location": {
#             "type": "string",
#             "description": "City or location name"
#           },
#           "temperature": {
#             "type": "number",
#             "description": "Temperature in Celsius"
#           },
#           "conditions": {
#             "type": "string",
#             "description": "Weather conditions description"
#           }
#         },
#         "required": ["location", "temperature", "conditions"],
#         "additionalProperties": false
#       }
#     }
    def send(self, message):
        self.messages.append({"role": "user", "content": message})
        return self._send_messages()

    def _send_messages(self):
        with OpenRouter(
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
        ) as open_router:
            response = open_router.chat.send(
                model=self.model,
                messages=self.messages,
                response_format=self.response_schema,
                stream=False
            )
            message = response.choices[0].message
            self.messages.append(
                {"role": message.role, "content": message.content}
            )
        return message.content
