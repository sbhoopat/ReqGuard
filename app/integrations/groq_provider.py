"""Groq LLM provider implementation with strict JSON schema validation and retry safety."""

import abc
import json
import logging
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, ValidationError

try:
    from groq import Groq, APIError, APITimeoutError, RateLimitError
except ImportError:
    Groq = None
    APIError = Exception
    APITimeoutError = Exception
    RateLimitError = Exception

from app.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(abc.ABC):
    """Abstract interface for LLM providers allowing drop-in replacement."""

    @abc.abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[BaseModel],
        max_retries: int = 2
    ) -> BaseModel:
        """Generate structured data conforming to the response_model."""
        pass


class GroqProvider(LLMProvider):
    """Groq implementation using the official Groq SDK with json_object response format."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None
    ):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self.temperature = temperature if temperature is not None else settings.GROQ_TEMPERATURE
        self.timeout = timeout if timeout is not None else settings.GROQ_TIMEOUT_SECONDS
        
        self.client = None
        if Groq and self.api_key:
            self.client = Groq(api_key=self.api_key, timeout=self.timeout)

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[BaseModel],
        max_retries: int = 2
    ) -> BaseModel:
        if not self.client:
            raise ValueError("Groq API client is not initialized. Please configure GROQ_API_KEY.")

        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        system_instructions = (
            f"{system_prompt}\n\n"
            f"IMPORTANT: You MUST respond ONLY with valid JSON conforming to this JSON Schema:\n"
            f"{schema_json}\n"
            f"Do not include markdown triple backticks around the JSON unless inside standard json. "
            f"Return only the raw JSON object."
        )

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Invoking Groq model {self.model} (attempt {attempt + 1}/{max_retries + 1})")
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_instructions},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=self.model,
                    temperature=self.temperature,
                    response_format={"type": "json_object"}
                )

                response_text = chat_completion.choices[0].message.content
                if not response_text:
                    raise ValueError("Groq returned empty response content.")

                # Parse JSON and validate against Pydantic schema
                data = json.loads(response_text)
                validated_model = response_model.model_validate(data)
                return validated_model

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"Groq output validation failed on attempt {attempt + 1}: {e}")
                last_error = e
            except (APITimeoutError, RateLimitError) as e:
                logger.error(f"Groq API error on attempt {attempt + 1}: {e}")
                last_error = e
            except APIError as e:
                logger.error(f"Groq API fatal error on attempt {attempt + 1}: {e}")
                raise e
            except Exception as e:
                logger.exception(f"Unexpected error calling Groq on attempt {attempt + 1}: {e}")
                last_error = e

        raise ValueError(f"Failed to generate valid structured output after {max_retries + 1} attempts. Last error: {last_error}")
