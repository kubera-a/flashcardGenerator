"""
Prompt Templates Module
-----------------------
Centralized prompt definitions for flashcard generation.

Design Principles:
1. Single source of truth for all prompts
2. Structured using dataclasses for type safety
3. Clear separation between system prompts and user templates
4. Based on SuperMemo's 20 Rules of Formulating Knowledge

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
# SuperMemo's 20 Rules Summary (for reference)
# =============================================================================
SUPERMEMO_RULES = """
1. Do not learn if you do not understand
2. Learn before you memorize
3. Build upon the basics
4. Stick to the minimum information principle
5. Cloze deletion is easy and effective
6. Use imagery
7. Use mnemonic techniques
8. Graphic deletion is as good as cloze deletion
9. Avoid sets
10. Avoid enumerations
11. Combat interference
12. Optimize wording
13. Refer to other memories
14. Personalize and provide examples
15. Rely on emotional states
16. Context cues simplify wording
17. Redundancy does not contradict minimum information principle
18. Provide sources
19. Provide date stamping
20. Prioritize
"""


# =============================================================================
# Card Generation Prompts
# =============================================================================

CARD_GENERATION_SYSTEM = """
You are an expert educational content designer specializing in spaced repetition and memory optimization.
Your task is to create COMPREHENSIVE, high-quality Anki flashcards following SuperMemo's 20 Rules of Formulating Knowledge.

Key principles:
- EXHAUSTIVE: Extract ALL learnable content, not just highlights
- ATOMIC: One fact per card (minimum information principle)
- CLEAR: Concise, unambiguous wording
- COMPLETE: Cover definitions, relationships, examples, applications

Generate as many cards as needed to fully cover the material. Do not artificially limit the number of cards.

Always return valid JSON format with no additional text.
"""

CARD_GENERATION_USER = """
Analyze this PDF document THOROUGHLY and create comprehensive Anki flashcards for ALL important concepts.

## EXTRACTION GOALS - Be Exhaustive:
- Extract EVERY definition, term, and concept
- Create cards for ALL formulas, equations, and relationships
- Cover ALL examples and their applications
- Include ALL key facts, dates, names, and figures
- Create cards for cause-effect relationships
- Cover comparisons and contrasts between concepts
- Include process steps and procedures
- Extract principles, rules, and laws

## CARD CREATION RULES (Based on SuperMemo's 20 Rules):

1. **Minimum Information Principle**: Each card tests ONE atomic piece of knowledge
   - BAD: "What are the three types of X?"
   - GOOD: Three separate cards, one for each type

2. **Optimize Wording**: Keep questions and answers concise and clear
   - Front: Short, specific question
   - Back: Brief, direct answer (1-2 sentences max)

3. **No Sets or Enumerations**: Never ask "List all..." or "What are the types of..."
   - Instead: Create individual cards for each item
   - Use "What is ONE example of..." or test each item separately

4. **Use Cloze-Style Questions**: Frame questions to fill in the blank
   - "The process of X is called ___" -> Answer: "Y"
   - "X is defined as ___" -> Answer: "definition"

5. **Context Cues**: Add brief context in brackets when needed
   - "[In genetics] What does DNA stand for?"

6. **Build on Basics**: Create foundational cards before advanced ones
   - Define terms before asking about their applications

7. **Combat Interference**: Make similar concepts distinguishable
   - Add context to prevent confusion between similar terms

8. **Provide Examples**: Include concrete examples in answers when helpful

## QUANTITY GUIDELINES:
- Generate AT LEAST 5-10 cards per page of content
- For dense technical content, generate 10-15 cards per page
- Don't skip any important concept - when in doubt, create a card
- It's better to have more atomic cards than fewer complex ones

## CARD TYPES TO CREATE:
- Definition cards: "What is [term]?" -> "Definition"
- Concept cards: "What does [concept] do/mean?" -> "Explanation"
- Relationship cards: "How does X relate to Y?" -> "Relationship"
- Application cards: "When would you use X?" -> "Use case"
- Comparison cards: "What is the difference between X and Y?" -> "Key difference"
- Process cards: "What is the first/next step in X?" -> "Step"
- Example cards: "What is an example of X?" -> "Specific example"
- Reverse cards: If useful, create both "What is X?" and "What is the term for [definition]?"

Return ONLY valid JSON with no additional text.
"""

CARD_OUTPUT_FORMAT = {
    "cards": [
        {
            "front": "Question text goes here",
            "back": "Answer text goes here",
            "tags": ["tag1", "tag2"],
        }
    ]
}


# =============================================================================
# Continue Generation Prompts (for generating additional cards)
# =============================================================================

CONTINUE_GENERATION_SYSTEM = """
You are an expert educational content designer. Your task is to find GAPS in existing flashcard coverage
and create cards for missing concepts. Be thorough but avoid duplicating existing content.

Always return valid JSON format with no additional text.
"""

CONTINUE_GENERATION_USER = """
Analyze this PDF document and create ADDITIONAL Anki flashcards for concepts that are MISSING.

## EXISTING CARDS (DO NOT DUPLICATE THESE):
The following cards have already been created. Do NOT create cards that test the same concepts:

{existing_cards}

## YOUR TASK:
1. Review the document carefully
2. Identify concepts, definitions, relationships, and facts NOT covered by existing cards
3. Create NEW cards for the missing content

{focus_areas}

## CARD CREATION RULES (Based on SuperMemo's 20 Rules):

1. **Minimum Information Principle**: Each card tests ONE atomic piece of knowledge
2. **Optimize Wording**: Keep questions and answers concise and clear
3. **No Sets or Enumerations**: Create individual cards for each item
4. **Context Cues**: Add brief context in brackets when needed

## IMPORTANT:
- Only create cards for concepts NOT in the existing cards list
- If you find no new concepts, return an empty cards array
- Focus on depth - find subtle details, examples, and edge cases
- Look for relationships between concepts that weren't captured

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

For each card, evaluate:
1. Is the question clear and specific?
2. Is the answer concise but complete?
3. Does the card focus on an important concept?
4. Is the card formatted properly?
5. Does it follow the minimum information principle (one fact per card)?

Improve any cards that don't meet these criteria.
Return only the improved cards in JSON format.
"""

VALIDATION_OUTPUT_FORMAT = {
    "improved_cards": [
        {
            "front": "Improved question text",
            "back": "Improved answer text",
            "tags": ["tag1", "tag2"],
        }
    ]
}


# =============================================================================
# Prompt Templates (Structured)
# =============================================================================

GENERATION_PROMPT = PromptTemplate(
    name="card_generation",
    description="Primary prompt for generating flashcards from PDF documents using SuperMemo's 20 Rules",
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
# All prompts registry (for easy access)
# =============================================================================

PROMPTS = {
    "generation": GENERATION_PROMPT,
    "continue_generation": CONTINUE_GENERATION_PROMPT,
    "validation": VALIDATION_PROMPT,
}


def get_prompt(name: str) -> PromptTemplate:
    """Get a prompt template by name."""
    if name not in PROMPTS:
        raise ValueError(f"Unknown prompt: {name}. Available: {list(PROMPTS.keys())}")
    return PROMPTS[name]
