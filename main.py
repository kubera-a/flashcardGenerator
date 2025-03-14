"""
Anki Flashcard Generator
------------------------
An automated system for generating Anki flashcards from PDF documents
using Large Language Models.
"""


import click

from utils.pipeline import Pipeline


@click.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file path for Anki package')
@click.option('--llm', type=click.Choice(['openai', 'anthropic']), help='LLM provider to use')
@click.option('--max-cards', type=int, default=50, help='Maximum number of cards to generate')
def main(pdf_path, output, llm, max_cards):
    """Generate Anki flashcards from a PDF document using LLMs."""
    click.echo(f"Processing PDF: {pdf_path}")

    # Initialize the pipeline
    pipeline = Pipeline(llm_provider=llm, max_cards=max_cards)

    # Process the PDF and generate cards
    result = pipeline.run(pdf_path, output)

    click.echo(f"Generated {result['card_count']} cards")
    click.echo(f"Output saved to: {result['output_path']}")

if __name__ == '__main__':
    main()
