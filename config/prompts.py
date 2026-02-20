"""
Prompt Templates Module
-----------------------
Centralized prompt definitions for flashcard generation.

Design Principles:
1. Single source of truth for all prompts
2. One unified generation prompt for all document types (PDF, text, markdown)
3. Image handling is an optional add-on, not a separate prompt
4. All 20 of SuperMemo's Rules of Formulating Knowledge are included

References:
- SuperMemo 20 Rules: https://www.supermemo.com/en/blog/twenty-rules-of-formulating-knowledge
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptTemplate:
    """A prompt template with system and user components."""
    name: str
    description: str
    system_prompt: str
    user_prompt_template: str
    output_format: dict = field(default_factory=dict)


# =============================================================================
# Unified Card Generation Prompts
# =============================================================================

CARD_GENERATION_SYSTEM = """
You are an expert educational content designer specializing in spaced repetition and memory optimization.
Your task is to create high-quality Anki flashcards following SuperMemo's 20 Rules of Formulating Knowledge.

Key principles:
- ATOMIC: One fact per card (minimum information principle)
- CLEAR: Concise, unambiguous wording

Always return valid JSON format with no additional text.
"""

CARD_GENERATION_USER = """
Analyze this document and create Anki flashcards for concepts worth retaining long-term.

## WHAT TO LOOK FOR:
- Definitions, terms, and concepts
- Formulas, equations, and relationships
- Cause-effect relationships
- Comparisons and contrasts between concepts
- Process steps and procedures
- Principles, rules, and laws
- Examples and their applications

## CARD CREATION RULES - SuperMemo's 20 Rules of Formulating Knowledge:

1. **Do not learn if you do not understand**: Only create cards for concepts the document explains clearly. Do not create cards about vague or unexplained references.

2. **Learn before you memorize**: Structure cards so foundational concepts come before details. Define terms before testing their applications.

3. **Build upon the basics**: Start with simple, fundamental cards. Create more specific cards that build on those basics.

4. **Minimum information principle**: Each card tests ONE atomic piece of knowledge.
   - BAD: "What are the three types of X?"
   - GOOD: Three separate cards, one for each type

5. **Cloze deletion is easy and effective**: Use fill-in-the-blank style questions.
   - "The process of X is called ___" -> Answer: "Y"
   - "X is defined as ___" -> Answer: "definition"

6. **Use imagery**: When images are available, reference them with [IMAGE: filename.png]. Place diagrams in the QUESTION to test visual recognition.

7. **Use mnemonic techniques**: When content lends itself to it, frame cards to leverage memorable associations.

8. **Graphic deletion is as good as cloze deletion**: For diagrams, ask the learner to identify missing parts or labels.

9. **Avoid sets**: Never ask "List all..." or "What are the types of..."
   - Instead: Create individual cards for each item
   - Use "What is ONE example of..." or test each item separately

10. **Avoid enumerations**: Do not ask for ordered lists. Break sequences into individual cards testing each step.

11. **Combat interference**: Make similar concepts distinguishable. Add context to prevent confusion between similar terms.

12. **Optimize wording**: Keep questions and answers concise and clear.
    - Front: Short, specific question
    - Back: Brief, direct answer (1-2 sentences max)

13. **Refer to other memories**: Connect new knowledge to familiar concepts when possible.

14. **Personalize and provide examples**: Include concrete examples in answers when helpful.

15. **Rely on emotional states**: Frame questions around interesting, surprising, or counterintuitive aspects of the material when possible.

16. **Context cues simplify wording**: Add brief context in brackets when needed.
    - "[In genetics] What does DNA stand for?"

17. **Redundancy does not contradict minimum information principle**: It's OK to create multiple cards testing the same concept from different angles (e.g., forward and reverse cards).

18. **Provide sources**: When the document cites specific sources or page numbers, include them in the answer for reference.

19. **Provide date stamping**: When content is time-sensitive or historical, include dates in the card.

20. **Prioritize**: Focus more cards on core concepts and less on trivial details.

## CARD TYPES TO CREATE:
- Definition cards: "What is [term]?" -> "Definition"
- Concept cards: "What does [concept] do/mean?" -> "Explanation"
- Relationship cards: "How does X relate to Y?" -> "Relationship"
- Application cards: "When would you use X?" -> "Use case"
- Comparison cards: "What is the difference between X and Y?" -> "Key difference"
- Process cards: "What is the first/next step in X?" -> "Step"
- Example cards: "What is an example of X?" -> "Specific example"
- Reverse cards: If useful, create both "What is X?" and "What is the term for [definition]?"

Do NOT generate tags - tags are managed automatically.

Return ONLY valid JSON with no additional text.
"""

CARD_OUTPUT_FORMAT = {
    "cards": [
        {
            "front": "Question text goes here",
            "back": "Answer text goes here",
        }
    ]
}

# =============================================================================
# Image Handling Add-on (prepended to user prompt for markdown with images)
# =============================================================================

IMAGE_HANDLING_SECTION = """
## IMAGE HANDLING:
The document contains the following images that you can see:
{image_list}

Images can go in EITHER the front (question) OR back (answer) depending on what makes pedagogical sense:

**Image in QUESTION (front)** - Use when testing recognition/interpretation:
- "What concept does this diagram illustrate? [IMAGE: diagram.png]"
- "What type of network topology is shown? [IMAGE: topology.png]"
- "Identify the components in this architecture: [IMAGE: arch.png]"

**Image in ANSWER (back)** - Use when the image supports/explains the answer:
- Front: "What is the hierarchical structure of ISPs?"
- Back: "Tier-1 (global), Tier-2 (regional), Tier-3 (access/local). [IMAGE: isp_hierarchy.png]"

Choose the placement that best tests understanding. Visual recognition cards (image in front) are excellent for diagrams.

For the output format, include an "images" array listing ALL image filenames used in each card (empty array if none).
"""

MARKDOWN_OUTPUT_FORMAT = {
    "cards": [
        {
            "front": "Question text (may include [IMAGE: filename.png])",
            "back": "Answer text (may include [IMAGE: filename.png])",
            "images": ["filename.png"],
        }
    ]
}

# =============================================================================
# PDF Image Handling Add-on (prepended to user prompt for PDFs with images)
# =============================================================================

PDF_IMAGE_HANDLING_SECTION = """
## IMAGE HANDLING:
Images have been extracted from this PDF and are provided above as individual images, in the following order:
{image_list}

The images above appear in the same order as listed. Use the filenames exactly as shown when referencing them.

Images can go in EITHER the front (question) OR back (answer) depending on what makes pedagogical sense:

**Image in QUESTION (front)** - Use when testing recognition/interpretation:
- "What concept does this diagram illustrate? [IMAGE: page3_img0.png]"
- "Identify the components shown: [IMAGE: page5_img1.png]"

**Image in ANSWER (back)** - Use when the image supports/explains the answer:
- Front: "What is the structure of X?"
- Back: "Description here. [IMAGE: page7_img0.png]"

Reference images using [IMAGE: filename] format. Only reference images from the list above.
For the output format, include an "images" array listing ALL image filenames used in each card (empty array if none).
"""


# =============================================================================
# Continue Generation Prompts (for generating additional cards)
# =============================================================================

CONTINUE_GENERATION_SYSTEM = """
You are an expert educational content designer. Your task is to find GAPS in existing flashcard coverage
and create cards for missing concepts. Be thorough but avoid duplicating existing content.

Always return valid JSON format with no additional text.
"""

CONTINUE_GENERATION_USER = """
Analyze this document and create ADDITIONAL Anki flashcards for concepts that are MISSING.

## EXISTING CARDS (DO NOT DUPLICATE THESE):
The following cards have already been created. Do NOT create cards that test the same concepts:

{existing_cards}

## YOUR TASK:
1. Review the document carefully
2. Identify concepts, definitions, relationships, and facts NOT covered by existing cards
3. Create NEW cards for the missing content

{focus_areas}

## IMPORTANT:
- Only create cards for concepts NOT in the existing cards list
- If you find no new concepts, return an empty cards array
- Focus on depth - find subtle details, examples, and edge cases
- Look for relationships between concepts that weren't captured
- Follow SuperMemo's 20 Rules (minimum information, no sets/enumerations, etc.)

Return ONLY valid JSON with no additional text.
"""


# =============================================================================
# Card Validation Prompts
# =============================================================================

CARD_VALIDATION_SYSTEM = """
You are an expert in educational psychology and spaced repetition learning.
Your task is to review and improve flashcards for effectiveness.

Return only valid JSON with the improved cards. Do not include any explanations or additional text.
"""

CARD_VALIDATION_USER = """
Review the following flashcards for quality and effectiveness:

{cards_json}

For each card, evaluate against SuperMemo's 20 Rules:
1. Is the question clear and specific? (Rule 12: Optimize wording)
2. Is the answer concise but complete? (Rule 4: Minimum information)
3. Does the card focus on an important concept? (Rule 20: Prioritize)
4. Does it test ONE atomic fact? (Rule 4: Minimum information)
5. Does it avoid sets/enumerations? (Rules 9 & 10)
6. Are similar concepts distinguished? (Rule 11: Combat interference)

Improve any cards that don't meet these criteria.
Return only the improved cards in JSON format.
"""

VALIDATION_OUTPUT_FORMAT = {
    "improved_cards": [
        {
            "front": "Improved question text",
            "back": "Improved answer text",
        }
    ]
}


# =============================================================================
# Batch Context Template (for multi-batch processing)
# =============================================================================

BATCH_CONTEXT_TEMPLATE = """

## BATCH CONTEXT:
- This is batch {batch_num} of {total_batches}
- Pages {context_pages} are included for context continuity (already processed)
- Focus on generating cards for pages {new_pages} (new content)
- Do NOT create cards for concepts already covered in context pages
"""


# =============================================================================
# Prompt Templates (Structured)
# =============================================================================

GENERATION_PROMPT = PromptTemplate(
    name="card_generation",
    description="Unified prompt for generating flashcards from any document type using SuperMemo's 20 Rules",
    system_prompt=CARD_GENERATION_SYSTEM.strip(),
    user_prompt_template=CARD_GENERATION_USER.strip(),
    output_format=CARD_OUTPUT_FORMAT,
)

CONTINUE_GENERATION_PROMPT = PromptTemplate(
    name="continue_generation",
    description="Prompt for generating additional cards while avoiding duplicates",
    system_prompt=CONTINUE_GENERATION_SYSTEM.strip(),
    user_prompt_template=CONTINUE_GENERATION_USER.strip(),
    output_format=CARD_OUTPUT_FORMAT,
)

VALIDATION_PROMPT = PromptTemplate(
    name="card_validation",
    description="Prompt for reviewing and improving generated flashcards",
    system_prompt=CARD_VALIDATION_SYSTEM.strip(),
    user_prompt_template=CARD_VALIDATION_USER.strip(),
    output_format=VALIDATION_OUTPUT_FORMAT,
)

# PDF image prompt = same system + base user prompt with PDF image section prepended
PDF_GENERATION_PROMPT = PromptTemplate(
    name="pdf_generation",
    description="Same generation prompt with PDF image handling section for PDFs with extracted images",
    system_prompt=CARD_GENERATION_SYSTEM.strip(),
    user_prompt_template=(PDF_IMAGE_HANDLING_SECTION + "\n" + CARD_GENERATION_USER).strip(),
    output_format=MARKDOWN_OUTPUT_FORMAT,
)

# Markdown prompt = same system + base user prompt with image section prepended
MARKDOWN_GENERATION_PROMPT = PromptTemplate(
    name="markdown_generation",
    description="Same generation prompt with image handling section for markdown documents",
    system_prompt=CARD_GENERATION_SYSTEM.strip(),
    user_prompt_template=(IMAGE_HANDLING_SECTION + "\n" + CARD_GENERATION_USER).strip(),
    output_format=MARKDOWN_OUTPUT_FORMAT,
)


# =============================================================================
# All prompts registry (for easy access)
# =============================================================================

PROMPTS = {
    "generation": GENERATION_PROMPT,
    "continue_generation": CONTINUE_GENERATION_PROMPT,
    "validation": VALIDATION_PROMPT,
    "pdf_generation": PDF_GENERATION_PROMPT,
    "markdown_generation": MARKDOWN_GENERATION_PROMPT,
}


def get_prompt(name: str) -> PromptTemplate:
    """Get a prompt template by name."""
    if name not in PROMPTS:
        raise ValueError(f"Unknown prompt: {name}. Available: {list(PROMPTS.keys())}")
    return PROMPTS[name]
