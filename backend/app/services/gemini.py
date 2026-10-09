import os
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
USE_MOCK_AI = os.getenv("USE_MOCK_AI", "true").lower() == "true"

if not USE_MOCK_AI and not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing from .env")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Smaller model = lower token usage
MODEL = "openai/gpt-oss-20b"


def generate_text(prompt: str) -> str:

    if USE_MOCK_AI:
        return mock_response(prompt)

    # Keep prompts from becoming excessively large.
    # Groq's current free/on-demand limit is token based.
    MAX_PROMPT_CHARS = 18000

    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS] + (
            "\n\n[Context truncated to control token usage.]"
        )

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_completion_tokens=1400,
            )

            return response.choices[0].message.content or ""

        except Exception as error:

            error_text = str(error).lower()

            # Groq 429 can happen because of TPM.
            # Wait before retrying instead of immediately failing.
            if "rate_limit_exceeded" in error_text or "429" in error_text:
                if attempt < 2:
                    wait_time = 2 + (attempt * 2)
                    print(
                        f"Groq rate limit reached. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    continue

            transient = (
                "timeout" in error_text
                or "connection" in error_text
                or "503" in error_text
                or "502" in error_text
                or "500" in error_text
            )

            if attempt < 2 and transient:
                time.sleep(1)
                continue

            raise


def mock_response(prompt: str) -> str:

    prompt_lower = prompt.lower()

    if "planner agent" in prompt_lower:
        return """Research Plan

1. Research Objective
Analyze the selected topic and identify its major concepts,
applications, benefits, challenges and future implications.

2. Research Questions
- What are the major concepts?
- What are the applications?
- What are the benefits?
- What are the challenges?
- What is the future scope?

3. Important Subtopics
- Background
- Applications
- Benefits
- Challenges
- Future developments

4. Evidence Requirements
Important factual claims should be supported by reliable sources.

5. Report Structure
Introduction
Background
Main Analysis
Key Findings
Challenges
Future Scope
Conclusion
References
"""

    if "researcher agent" in prompt_lower:
        return """Research Findings

The available evidence was reviewed and organized according
to the research questions.

Key findings:
- The topic has significant practical applications.
- Multiple benefits have been identified.
- Several limitations and challenges remain.
- Further research is required where evidence is limited.
"""

    if "analyst agent" in prompt_lower:
        return """Analysis

Major Findings:
- The topic is developing rapidly.
- Applications are expanding across multiple domains.
- Benefits must be considered alongside limitations.

Research Gaps:
- Additional high-quality evidence is required.
- Long-term effects require further investigation.
"""

    if "verification agent" in prompt_lower:
        return """Verification Results

Claim 1:
Status: SUPPORTED
Confidence: Medium

Claim 2:
Status: PARTIALLY_SUPPORTED
Confidence: Medium

Claim 3:
Status: UNSUPPORTED
Confidence: Low

Overall verification assessment:
Some claims require stronger source-backed evidence.
"""

    if "reviewer agent" in prompt_lower:
        return """SCORE: 85
STATUS: READY

ISSUES:
- Some claims require stronger source support.

RECOMMENDATIONS:
- Add additional reliable sources.
- Improve citation coverage.
"""

    if "writer agent" in prompt_lower:
        return """# Generated Research Report

## Introduction

This section introduces the selected research topic and explains
its importance and context.

## Background

The topic can be understood through its major concepts,
developments and applications.

## Main Analysis

The available findings reveal several important aspects of the topic.

## Key Findings

The research identifies several significant observations.

## Conclusion

The topic has significant relevance and requires continued
research and evaluation.

## References

Sources will be added by the RAG and research pipeline.
"""

    return "Mock AI Response"


def get_ai_mode():
    return "MOCK" if USE_MOCK_AI else "GROQ"