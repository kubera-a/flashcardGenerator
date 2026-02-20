"""
LLM Interface Module
-------------------
Provides a unified interface for communicating with different LLM providers.
"""

import base64
import json
import logging
import time
from pathlib import Path

import httpx
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

    def _retry_on_rate_limit(self, fn, *args, **kwargs):
        """Retry a function with exponential backoff on rate limit errors (max 60s, 5 attempts)."""
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                if "rate limit" not in str(e).lower() or attempt == max_attempts - 1:
                    raise
                delay = min(60, 10 * (2 ** attempt))  # 10, 20, 40, 60, 60
                logger.info(f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_attempts})")
                time.sleep(delay)

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
        params = {**self.config, **kwargs}

        def _do_call():
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

        return self._retry_on_rate_limit(_do_call)

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
        params = {**self.config, **kwargs}

        def _do_call():
            response = self.client.messages.create(
                model=params.get("model", "claude-3-opus-20240229"),
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.3),
                max_tokens=params.get("max_tokens", 1000),
                timeout=httpx.Timeout(600.0, connect=5.0),
            )
            return response.content[0].text

        return self._retry_on_rate_limit(_do_call)

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

    def supports_native_pdf(self) -> bool:
        """
        Check if the current provider supports native PDF processing.

        Returns:
            True if the provider can process PDFs natively, False otherwise
        """
        return self.provider == "anthropic"

    def _encode_pdf_to_base64(self, pdf_path: str | Path) -> str:
        """
        Encode a PDF file to base64.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Base64-encoded string of the PDF content
        """
        pdf_path = Path(pdf_path)
        with open(pdf_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    def _encode_pdf_pages_to_base64(self, pdf_path: str | Path, page_indices: list[int]) -> str:
        """
        Extract specific pages from a PDF and encode to base64.

        Args:
            pdf_path: Path to the PDF file
            page_indices: 0-based page indices to include

        Returns:
            Base64-encoded string of the subset PDF
        """
        import fitz

        src = fitz.open(str(pdf_path))
        dst = fitz.open()
        try:
            for page_num in page_indices:
                if page_num < len(src):
                    dst.insert_pdf(src, from_page=page_num, to_page=page_num)
            pdf_bytes = dst.tobytes()
        finally:
            dst.close()
            src.close()

        return base64.standard_b64encode(pdf_bytes).decode("utf-8")

    def _call_anthropic_with_pdf(
        self,
        pdf_data: str,
        prompt: str,
        system_prompt: str,
        images: list[tuple[str, str]] | None = None,
        **kwargs,
    ) -> str:
        """
        Call the Anthropic API with a PDF document and optional images.

        Args:
            pdf_data: Base64-encoded PDF data
            prompt: The text prompt
            system_prompt: The system prompt
            images: Optional list of (base64_data, media_type) tuples for
                    extracted images to send alongside the PDF
            **kwargs: Additional parameters
        """
        params = {**self.config, **kwargs}

        # Build content: PDF first, then individual images, then text prompt
        content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_data,
                },
            },
        ]

        if images:
            for img_data, media_type in images:
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": img_data,
                        },
                    }
                )

        content.append(
            {
                "type": "text",
                "text": prompt,
            }
        )

        def _do_call():
            response = self.client.messages.create(
                model=params.get("model", "claude-sonnet-4-5-20250514"),
                system=system_prompt,
                messages=[{"role": "user", "content": content}],
                temperature=params.get("temperature", 0.3),
                max_tokens=params.get("max_tokens", 4096),
                timeout=httpx.Timeout(600.0, connect=5.0),
            )
            return response.content[0].text

        return self._retry_on_rate_limit(_do_call)

    def generate_from_pdf(
        self,
        pdf_path: str | Path,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        page_indices: list[int] | None = None,
        images: list[tuple[str, str]] | None = None,
        **kwargs,
    ) -> str:
        """
        Generate a completion from a PDF document.

        For providers that support native PDF processing (Anthropic), the PDF
        is sent directly to the API. For other providers, text is extracted
        and sent as a regular prompt.

        Args:
            pdf_path: Path to the PDF file
            prompt: The prompt to send with the PDF
            system_prompt: The system prompt for context
            page_indices: Optional list of 0-based page indices to process.
                         If None, all pages are processed.
            images: Optional list of (base64_data, media_type) tuples for
                    extracted images to send alongside the PDF
            **kwargs: Additional parameters to pass to the provider

        Returns:
            The LLM response as a string
        """
        logger.debug(f"Generating from PDF with provider: {self.provider}")

        if self.supports_native_pdf():
            if page_indices is not None:
                pdf_data = self._encode_pdf_pages_to_base64(pdf_path, page_indices)
            else:
                pdf_data = self._encode_pdf_to_base64(pdf_path)
            return self._call_anthropic_with_pdf(
                pdf_data, prompt, system_prompt, images=images, **kwargs
            )
        else:
            # Fall back to text extraction for other providers
            from modules.pdf_processor import PDFProcessor

            processor = PDFProcessor()
            chunks, metadata = processor.process_pdf(str(pdf_path))

            # If page_indices specified, filter chunks (approximate by chunk index)
            if page_indices is not None:
                # This is approximate since chunks don't map 1:1 to pages
                # For better control, the PDF processor would need enhancement
                pass

            # Combine chunks into a single text
            combined_text = "\n\n".join(chunks)

            # Create an enhanced prompt with the extracted text
            enhanced_prompt = f"{prompt}\n\nDocument content:\n{combined_text}"

            return self.generate_completion(enhanced_prompt, system_prompt, **kwargs)

    def generate_structured_from_pdf(
        self,
        pdf_path: str | Path,
        prompt: str,
        output_format: dict,
        system_prompt: str = "You are a helpful assistant that outputs structured JSON.",
        page_indices: list[int] | None = None,
        images: list[tuple[str, str]] | None = None,
        **kwargs,
    ) -> dict:
        """
        Generate structured output (JSON) from a PDF document.

        Args:
            pdf_path: Path to the PDF file
            prompt: The prompt to send with the PDF
            output_format: Dictionary specifying the expected output format
            system_prompt: The system prompt for context
            page_indices: Optional list of 0-based page indices to process
            images: Optional list of (base64_data, media_type) tuples for
                    extracted images to send alongside the PDF
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
                response = self.generate_from_pdf(
                    pdf_path=pdf_path,
                    prompt=enhanced_prompt,
                    system_prompt=enhanced_system_prompt,
                    page_indices=page_indices,
                    images=images,
                    **kwargs,
                )

                # Extract JSON from response
                response = response.strip()
                if response.startswith("```json"):
                    response = response.split("```json")[1]
                if response.endswith("```"):
                    response = response.rsplit("```", 1)[0]

                return json.loads(response)

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON from PDF response (attempt {attempt+1}/{max_retries}): {e}"
                )

                if attempt == max_retries - 1:
                    logger.error(
                        f"JSON parsing failed after {max_retries} attempts. Last response: {response}"
                    )
                    raise

                enhanced_system_prompt += "\nYOUR PREVIOUS RESPONSE WAS NOT VALID JSON. ENSURE YOU RETURN ONLY VALID JSON WITH NO MARKDOWN OR OTHER TEXT."

    def _encode_image_to_base64(self, image_path: Path) -> tuple[str, str]:
        """
        Encode an image file to base64 and determine its media type.

        Args:
            image_path: Path to the image file

        Returns:
            Tuple of (base64_data, media_type)
        """
        suffix = image_path.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(suffix, "image/png")

        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")

        return data, media_type

    def _call_anthropic_with_images(
        self,
        text_content: str,
        images: list[tuple[str, str]],  # List of (base64_data, media_type)
        system_prompt: str,
        **kwargs,
    ) -> str:
        """
        Call Anthropic API with text and multiple images.

        Args:
            text_content: The text prompt
            images: List of (base64_data, media_type) tuples
            system_prompt: The system prompt
            **kwargs: Additional parameters

        Returns:
            The LLM response as a string
        """
        params = {**self.config, **kwargs}

        # Build content array with images first, then text
        content = []
        for img_data, media_type in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": img_data,
                    },
                }
            )
        content.append(
            {
                "type": "text",
                "text": text_content,
            }
        )

        def _do_call():
            response = self.client.messages.create(
                model=params.get("model", "claude-sonnet-4-5-20250514"),
                system=system_prompt,
                messages=[{"role": "user", "content": content}],
                temperature=params.get("temperature", 0.3),
                max_tokens=params.get("max_tokens", 4096),
                timeout=httpx.Timeout(600.0, connect=5.0),
            )
            return response.content[0].text

        return self._retry_on_rate_limit(_do_call)

    def generate_structured_from_markdown(
        self,
        markdown_content: str,
        images: list[Path],
        prompt: str,
        output_format: dict,
        system_prompt: str = "You are a helpful assistant that outputs structured JSON.",
        **kwargs,
    ) -> dict:
        """
        Generate structured output from markdown content with images.

        This method sends markdown text along with associated images to Claude
        for multimodal understanding and card generation.

        Args:
            markdown_content: The markdown text content
            images: List of image paths to include
            prompt: The user prompt
            output_format: Dictionary specifying expected output format
            system_prompt: The system prompt
            **kwargs: Additional parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            ValueError: If not using Anthropic provider
        """
        if not self.supports_native_pdf():
            raise ValueError("Image support requires Anthropic provider")

        # Encode all images
        encoded_images = []
        for img_path in images:
            if img_path.exists():
                data, media_type = self._encode_image_to_base64(img_path)
                encoded_images.append((data, media_type))
                logger.debug(f"Encoded image: {img_path.name} ({media_type})")

        logger.info(f"Sending {len(encoded_images)} images with markdown to Claude")

        # Combine markdown and prompt
        full_prompt = f"{prompt}\n\n## Document Content:\n{markdown_content}"

        # Add output format instructions
        format_desc = json.dumps(output_format, indent=2)
        enhanced_system = (
            f"{system_prompt}\n\n"
            f"You must respond with a valid JSON object using the following format:\n"
            f"{format_desc}\n\n"
            f"Do not include any text outside of the JSON object."
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self._call_anthropic_with_images(
                    full_prompt, encoded_images, enhanced_system, **kwargs
                )

                # Parse JSON response
                response = response.strip()
                if response.startswith("```json"):
                    response = response.split("```json")[1]
                if response.endswith("```"):
                    response = response.rsplit("```", 1)[0]

                return json.loads(response)

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON from markdown response "
                    f"(attempt {attempt + 1}/{max_retries}): {e}"
                )

                if attempt == max_retries - 1:
                    logger.error(
                        f"JSON parsing failed after {max_retries} attempts. "
                        f"Last response: {response}"
                    )
                    raise

                enhanced_system += (
                    "\nYOUR PREVIOUS RESPONSE WAS NOT VALID JSON. "
                    "ENSURE YOU RETURN ONLY VALID JSON WITH NO MARKDOWN OR OTHER TEXT."
                )
