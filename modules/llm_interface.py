"""
LLM Interface Module
-------------------
Provides a unified interface for communicating with different LLM providers.
"""

import json
import logging
import time

import openai
from anthropic import Anthropic

from config.settings import (
    ANTHROPIC_API_KEY,
    DEFAULT_LLM_PROVIDER,
    LLM_CONFIG,
    OPENAI_API_KEY,
)

logger = logging.getLogger(__name__)


class LLMInterface:
    """Interface for communicating with Large Language Models."""

    def __init__(self, provider: str = DEFAULT_LLM_PROVIDER):
        """
        Initialize the LLM interface.

        Args:
            provider: The LLM provider to use ('openai' or 'anthropic')
        """
        self.provider = provider.lower()
        self.config = LLM_CONFIG.get(self.provider, {})

        # Initialize the appropriate client
        if self.provider == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("OpenAI API key is required but not provided")
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        elif self.provider == "anthropic":
            if not ANTHROPIC_API_KEY:
                raise ValueError("Anthropic API key is required but not provided")
            self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        logger.info(f"Initialized LLM interface with provider: {self.provider}")

    def _call_openai(self, prompt: str, system_prompt: str, **kwargs) -> str:
        """
        Call the OpenAI API with the given prompts.

        Args:
            prompt: The user prompt
            system_prompt: The system prompt
            **kwargs: Additional parameters to pass to the API

        Returns:
            The LLM response as a string
        """
        # Merge default config with provided kwargs
        params = {**self.config, **kwargs}

        try:
            response = self.client.chat.completions.create(
                model=params.get("model", "gpt-4"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=params.get("temperature", 0.3),
                max_tokens=params.get("max_tokens", 1000),
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            # Implement exponential backoff for rate limits
            if "rate limit" in str(e).lower():
                logger.info("Rate limit hit, backing off and retrying...")
                time.sleep(5)
                return self._call_openai(prompt, system_prompt, **kwargs)
            raise

    def _call_anthropic(self, prompt: str, system_prompt: str, **kwargs) -> str:
        """
        Call the Anthropic API with the given prompts.

        Args:
            prompt: The user prompt
            system_prompt: The system prompt
            **kwargs: Additional parameters to pass to the API

        Returns:
            The LLM response as a string
        """
        # Merge default config with provided kwargs
        params = {**self.config, **kwargs}

        try:
            response = self.client.messages.create(
                model=params.get("model", "claude-3-opus-20240229"),
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.3),
                max_tokens=params.get("max_tokens", 1000),
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            # Implement exponential backoff for rate limits
            if "rate limit" in str(e).lower():
                logger.info("Rate limit hit, backing off and retrying...")
                time.sleep(5)
                return self._call_anthropic(prompt, system_prompt, **kwargs)
            raise

    def generate_completion(
        self, prompt: str, system_prompt: str = "You are a helpful assistant.", **kwargs
    ) -> str:
        """
        Generate a completion using the configured LLM provider.

        Args:
            prompt: The prompt to send to the LLM
            system_prompt: The system prompt for context
            **kwargs: Additional parameters to pass to the provider

        Returns:
            The LLM response as a string
        """
        logger.debug(f"Generating completion with provider: {self.provider}")

        if self.provider == "openai":
            return self._call_openai(prompt, system_prompt, **kwargs)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt, system_prompt, **kwargs)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def generate_structured_output(
        self,
        prompt: str,
        output_format: dict,
        system_prompt: str = "You are a helpful assistant that outputs structured JSON.",
        **kwargs,
    ) -> dict:
        """
        Generate structured output (JSON) using the LLM.

        Args:
            prompt: The prompt to send to the LLM
            output_format: Dictionary specifying the expected output format
            system_prompt: The system prompt for context
            **kwargs: Additional parameters to pass to the provider

        Returns:
            The parsed structured response as a dictionary
        """
        # Enhance the system prompt with formatting instructions
        format_description = json.dumps(output_format, indent=2)
        enhanced_system_prompt = (
            f"{system_prompt}\n\n"
            f"You must respond with a valid JSON object using the following format:\n"
            f"{format_description}\n\n"
            f"Do not include any text outside of the JSON object."
        )

        # Enhance the user prompt to emphasize JSON output
        enhanced_prompt = (
            f"{prompt}\n\n"
            f"Remember to respond with only a valid JSON object according to the specified format."
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.generate_completion(
                    enhanced_prompt, enhanced_system_prompt, **kwargs
                )

                # Extract JSON from response (in case there's surrounding text)
                response = response.strip()
                if response.startswith("```json"):
                    response = response.split("```json")[1]
                if response.endswith("```"):
                    response = response.rsplit("```", 1)[0]

                # Parse the JSON response
                return json.loads(response)

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON response (attempt {attempt+1}/{max_retries}): {e}"
                )

                if attempt == max_retries - 1:
                    logger.error(
                        f"JSON parsing failed after {max_retries} attempts. Last response: {response}"
                    )
                    raise

                # Add more explicit instructions for retry
                enhanced_system_prompt += "\nYOUR PREVIOUS RESPONSE WAS NOT VALID JSON. ENSURE YOU RETURN ONLY VALID JSON WITH NO MARKDOWN OR OTHER TEXT."
