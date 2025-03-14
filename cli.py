"""
Command Line Interface
--------------------
Provides a command-line interface for the flashcard generator.
"""

import logging
import logging.config
import sys
import time

import click

from config.settings import LOGGING_CONFIG
from utils.pipeline import Pipeline

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """
    Anki Flashcard Generator - Create flashcards from PDF documents using LLMs.
    """
    pass


@cli.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option(
    "--output", "-o", type=click.Path(), help="Output file path for Anki cards"
)
@click.option(
    "--llm",
    type=click.Choice(["openai", "anthropic"]),
    default="openai",
    help="LLM provider to use",
)
@click.option(
    "--max-cards", type=int, default=50, help="Maximum number of cards to generate"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def generate(pdf_path, output, llm, max_cards, verbose):
    """
    Generate Anki flashcards from a PDF document.

    PDF_PATH: Path to the PDF file to process
    """
    # Set the log level based on verbose flag
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    start_time = time.time()
    click.echo(f"Processing PDF: {pdf_path}")

    try:
        # Initialize the pipeline
        pipeline = Pipeline(llm_provider=llm, max_cards=max_cards)

        # Process the PDF and generate cards
        result = pipeline.run(pdf_path, output)

        if result.get("success", False):
            elapsed_time = time.time() - start_time
            click.echo(
                click.style(
                    f"✅ Successfully generated {result['card_count']} cards in {elapsed_time:.2f} seconds",
                    fg="green",
                )
            )
            click.echo(f"Output saved to: {result['output_path']}")
            click.echo(f"Import instructions saved to: {result['instructions_path']}")
        else:
            click.echo(
                click.style(
                    f"❌ Failed to generate cards: {result.get('message', 'Unknown error')}",
                    fg="red",
                )
            )
            return 1

    except Exception as e:
        logger.exception("Error running pipeline")
        click.echo(click.style(f"❌ Error: {str(e)}", fg="red"))
        return 1

    return 0


@cli.command()
@click.option(
    "--llm",
    type=click.Choice(["openai", "anthropic"]),
    default="openai",
    help="LLM provider to check",
)
def check_api(llm):
    """
    Check if the API keys are configured correctly.
    """
    from modules.llm_interface import LLMInterface

    try:
        llm_interface = LLMInterface(provider=llm)

        # Simple test prompt
        response = llm_interface.generate_completion(
            prompt="Respond with the text 'API is working correctly' if you can read this.",
            system_prompt="You are a test assistant.",
        )

        if "API is working correctly" in response:
            click.echo(
                click.style(f"✅ {llm.upper()} API is configured correctly", fg="green")
            )
            return 0
        else:
            click.echo(
                click.style(
                    f"❌ {llm.upper()} API test failed: Unexpected response", fg="red"
                )
            )
            return 1

    except Exception as e:
        click.echo(click.style(f"❌ {llm.upper()} API test failed: {str(e)}", fg="red"))
        return 1


if __name__ == "__main__":
    sys.exit(cli())
