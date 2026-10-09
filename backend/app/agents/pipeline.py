from datetime import datetime, timezone
import re

from app.services.gemini import generate_text
from app.rag.retriever import vector_store
from app.rag.reranker import rerank
from app.services.web_research import search_web


AGENTS = [
    "Planner",
    "Researcher",
    "Analyst",
    "Verifier",
    "Writer",
    "Reviewer",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def run_stage(name, function, args, on_stage=None):

    if on_stage:
        on_stage(name, "running")

    try:
        result = function(*args)

        if on_stage:
            on_stage(name, "completed")

        return result

    except Exception:

        if on_stage:
            on_stage(name, "failed")

        raise


# ---------------------------------------------------------
# PLANNER
# ---------------------------------------------------------

def planner_agent(topic, report_type):

    prompt = f"""
You are the Planner Agent.

Topic: {topic}
Report Type: {report_type}

Create a concise research plan.

Return:
1. Objective
2. Research questions
3. Important subtopics
4. Evidence requirements
5. Report structure

Do not write the report.
Do not invent sources.
Keep the response concise.
"""

    return generate_text(prompt)


# ---------------------------------------------------------
# RESEARCHER
# ---------------------------------------------------------

def researcher_agent(topic, plan, evidence):

    # Limit evidence size
    evidence = evidence[:12000]

    prompt = f"""
You are the Researcher Agent.

Topic:
{topic}

Research Plan:
{plan[:5000]}

Evidence:
{evidence}

Extract the most important findings.

Rules:
- Use only supplied evidence.
- Reference source IDs.
- Identify conflicting information.
- Identify missing information.
- Do not invent facts.
- Do not invent sources.

Return concise structured findings.
"""

    return generate_text(prompt)


# ---------------------------------------------------------
# ANALYST
# ---------------------------------------------------------

def analyst_agent(topic, research):

    prompt = f"""
You are the Analyst Agent.

Topic:
{topic}

Research Findings:
{research[:10000]}

Analyze the findings.

Return:
1. Major findings
2. Patterns
3. Comparisons
4. Contradictions
5. Limitations
6. Research gaps
7. Key insights

Do not introduce unsupported facts.
Keep the analysis concise.
"""

    return generate_text(prompt)


# ---------------------------------------------------------
# VERIFIER
# ---------------------------------------------------------

def verifier_agent(topic, research, analysis, evidence):

    evidence = evidence[:9000]

    prompt = f"""
You are the Verification Agent.

Topic:
{topic}

Research:
{research[:7000]}

Analysis:
{analysis[:7000]}

Evidence:
{evidence}

Verify the important claims.

For each major claim provide:

Claim:
Status:
Source:
Confidence:

Allowed statuses:
SUPPORTED
PARTIALLY_SUPPORTED
UNSUPPORTED
CONTRADICTED

Do not invent evidence.
Only use supplied source IDs.

Finish with an overall assessment.
"""

    return generate_text(prompt)


# ---------------------------------------------------------
# WRITER
# ---------------------------------------------------------

def writer_agent(
    topic,
    report_type,
    plan,
    research,
    analysis,
    verification,
    evidence,
    reviewer_feedback=""
):

    prompt = f"""
You are the Writer Agent in an advanced autonomous research system.

Your job is to create a HIGH-QUALITY, PUBLICATION-READY {report_type}.

==================================================
TOPIC
==================================================

{topic}

==================================================
RESEARCH PLAN
==================================================

{plan[:4000]}

==================================================
RESEARCH FINDINGS
==================================================

{research[:7000]}

==================================================
ANALYSIS
==================================================

{analysis[:7000]}

==================================================
VERIFICATION
==================================================

{verification[:7000]}

==================================================
AVAILABLE SOURCES
==================================================

{evidence[:8000]}

==================================================
PREVIOUS REVIEWER FEEDBACK
==================================================

{reviewer_feedback[:3000]}

==================================================
WRITING REQUIREMENTS
==================================================

Create the ACTUAL FINAL REPORT.

Do NOT explain how the report was created.

Do NOT mention that you are an AI.

Do NOT mention the agent pipeline.

Do NOT use placeholder text.

Do NOT write statements such as:
"This section introduces..."
"This topic can be understood..."
"The research identifies several..."
unless they contain meaningful topic-specific information.

==================================================
DOCUMENT STRUCTURE
==================================================

Use a professional structure appropriate for the report type.

For an academic/research report, prefer:

# Title

## Executive Summary

## 1. Introduction

### 1.1 Background

### 1.2 Research Objectives

### 1.3 Research Questions

## 2. Methodology

### 2.1 Research Approach

### 2.2 Evidence Selection

## 3. Findings

### 3.1 [Relevant Subtopic]

### 3.2 [Relevant Subtopic]

### 3.3 [Relevant Subtopic]

## 4. Analysis and Discussion

### 4.1 Key Insights

### 4.2 Comparisons

### 4.3 Challenges and Limitations

## 5. Recommendations

## 6. Future Scope

## 7. Conclusion

## References

Adapt the structure when another report type requires a different
organization.

==================================================
MARKDOWN FORMATTING
==================================================

You MUST use Markdown formatting correctly.

Use:

# for the document title

## for major sections

### for subsections

**bold text** for:
- Important concepts
- Key findings
- Important terminology
- Major conclusions
- Important recommendations

*italic text* only when genuinely useful.

Use numbered lists for sequential recommendations or procedures.

Use bullet lists for grouped findings.

Use Markdown tables when comparing multiple items.

Use blockquotes only when directly quoting supplied evidence.

Separate paragraphs with blank lines.

Do NOT create extremely long paragraphs.

==================================================
ACADEMIC QUALITY
==================================================

Write in a professional academic style.

Every important factual claim must be supported by available evidence.

Do not invent:
- statistics
- studies
- researchers
- dates
- organizations
- citations
- URLs
- findings

If evidence is insufficient, explicitly say:

**Evidence limitation:** The available sources do not provide
sufficient evidence to establish this claim.

Do not pretend that missing evidence exists.

Clearly distinguish:
- Evidence
- Analysis
- Interpretation
- Recommendations

==================================================
CITATIONS
==================================================

Use ONLY source IDs that appear in the supplied evidence.

Valid examples:

[WEB-1]

[PDF-1]

Never create:

[WEB-99]

[PDF-99]

Never use:

WEB?1
WEB?2
PDF?1

Never invent citations.

==================================================
REFERENCES
==================================================

At the end create:

## References

Then list every source actually cited in the report.

Example:

1. **[WEB-1]** Source Title — URL
2. **[WEB-2]** Source Title — URL

Do not list sources that were not used.

==================================================
IMPORTANT
==================================================

The final output must look like a professional research document
that can be converted directly into PDF or DOCX.

Prioritize:

**clarity + structure + evidence + readability + professional formatting**

Return ONLY the final report.
"""

    return generate_text(prompt)


# ---------------------------------------------------------
# REVIEWER
# ---------------------------------------------------------

def reviewer_agent(topic, report, verification):

    prompt = f"""
You are the Reviewer Agent.

Topic:
{topic}

Report:
{report[:11000]}

Verification:
{verification[:5000]}

Review the report for:

1. Accuracy
2. Evidence support
3. Citation integrity
4. Completeness
5. Relevance
6. Organization
7. Readability
8. Unsupported claims

Return EXACTLY:

SCORE: <0-100>

STATUS: READY

or

STATUS: REVISE

ISSUES:
- issue

RECOMMENDATIONS:
- recommendation

Do not rewrite the report.
"""

    return generate_text(prompt)


# ---------------------------------------------------------
# EVIDENCE COLLECTION
# ---------------------------------------------------------

def collect_evidence(topic):

    unified = []

    # -----------------------------
    # RAG
    # -----------------------------

    try:

        candidates = vector_store.hybrid_search(
            topic,
            top_k=10
        )

        if candidates:

            ranked = rerank(
                topic,
                candidates,
                top_k=3
            )

            for i, item in enumerate(ranked, start=1):

                unified.append({
                    "id": f"PDF-{i}",
                    "source_type": "user_document",
                    "title": item.get(
                        "filename",
                        "Uploaded document"
                    ),
                    "url": "",
                    "document_id": item.get(
                        "document_id"
                    ),
                    "page": item.get(
                        "page"
                    ),
                    "chunk_id": item.get(
                        "chunk_id"
                    ),
                    "content": item.get(
                        "text",
                        ""
                    )[:3500],
                    "score": item.get(
                        "score"
                    ),
                })

    except Exception as error:

        print(
            "RAG evidence collection failed:",
            repr(error)
        )

    # -----------------------------
    # WEB
    # -----------------------------

    try:

        web_results = search_web(
            topic,
            max_results=3
        )

    except Exception as error:

        print(
            "Web research failed:",
            repr(error)
        )

        web_results = []

    seen_urls = set()

    for item in web_results:

        url = item.get("url", "")

        if not url:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        unified.append({
            "id": f"WEB-{len(seen_urls)}",
            "source_type": "web",
            "title": item.get(
                "title",
                ""
            ),
            "url": url,
            "document_id": None,
            "page": None,
            "chunk_id": None,
            "content": item.get(
                "content",
                ""
            )[:3000],
            "score": item.get(
                "score"
            ),
        })

    return unified


# ---------------------------------------------------------
# FORMAT EVIDENCE
# ---------------------------------------------------------

def format_evidence(evidence_results):

    if not evidence_results:
        return """
NO VERIFIED EXTERNAL EVIDENCE IS AVAILABLE.

The writer must not invent factual claims.
"""

    formatted = []

    for item in evidence_results:

        source_id = item["id"]

        title = item.get(
            "title",
            "Unknown source"
        )

        url = item.get(
            "url",
            ""
        )

        page = item.get(
            "page"
        )

        content = item.get(
            "content",
            ""
        )

        if url:
            location = url

        elif page:
            location = (
                f"User document, page {page}"
            )

        else:
            location = "User document"

        formatted.append(
            f"""
==================================================
SOURCE ID: {source_id}
==================================================

Title:
{title}

Location:
{location}

Evidence:
{content}
"""
        )

    return "\n".join(formatted)


# ---------------------------------------------------------
# PIPELINE
# ---------------------------------------------------------

def run_pipeline(
    topic,
    report_type,
    on_stage=None
):

    started = now()

    # Evidence
    evidence_results = collect_evidence(topic)

    evidence = format_evidence(
        evidence_results
    )

    # Planner
    plan = run_stage(
        "Planner",
        planner_agent,
        (
            topic,
            report_type
        ),
        on_stage
    )

    # Researcher
    research = run_stage(
        "Researcher",
        researcher_agent,
        (
            topic,
            plan,
            evidence
        ),
        on_stage
    )

    # Analyst
    analysis = run_stage(
        "Analyst",
        analyst_agent,
        (
            topic,
            research
        ),
        on_stage
    )

    # Verifier
    verification = run_stage(
        "Verifier",
        verifier_agent,
        (
            topic,
            research,
            analysis,
            evidence
        ),
        on_stage
    )

    # Writer
    report = run_stage(
        "Writer",
        writer_agent,
        (
            topic,
            report_type,
            plan,
            research,
            analysis,
            verification,
            evidence,
            ""
        ),
        on_stage
    )

    # Reviewer
    review = run_stage(
        "Reviewer",
        reviewer_agent,
        (
            topic,
            report,
            verification
        ),
        on_stage
    )

    # ---------------------------------
    # REVISION LOOP
    # ---------------------------------

    revision_count = 0

    for _ in range(2):

        if "STATUS: REVISE" not in review.upper():
            break

        revision_count += 1

        print(
            f"Revision {revision_count} requested."
        )

        report = run_stage(
            "Writer",
            writer_agent,
            (
                topic,
                report_type,
                plan,
                research,
                analysis,
                verification,
                evidence,
                review
            ),
            on_stage
        )

        review = run_stage(
            "Reviewer",
            reviewer_agent,
            (
                topic,
                report,
                verification
            ),
            on_stage
        )

    finished = now()

    # ---------------------------------
    # REVIEW SCORE
    # ---------------------------------

    score_match = re.search(
        r"SCORE\s*:\s*(\d{1,3})",
        review,
        re.IGNORECASE
    )

    reviewer_score = (
        min(
            100,
            int(score_match.group(1))
        )
        if score_match
        else None
    )

    # ---------------------------------
    # CITATIONS
    # ---------------------------------

    reported_citations = sorted(
        set(
            re.findall(
                r"\b(?:WEB|PDF)-\d+\b",
                report
            )
        )
    )

    valid_source_ids = {
        item["id"]
        for item in evidence_results
    }

    cited_ids = sorted(
        set(reported_citations)
        & valid_source_ids
    )

    unknown_citations = sorted(
        set(reported_citations)
        - valid_source_ids
    )

    # ---------------------------------
    # AGENT RUNS
    # ---------------------------------

    outputs = [
        plan,
        research,
        analysis,
        verification,
        report,
        review
    ]

    agent_runs = []

    for name, output in zip(
        AGENTS,
        outputs
    ):

        agent_runs.append({
            "agent_name": name,
            "status": "completed",
            "started_at": started,
            "completed_at": finished,
            "output_summary": output[:500]
        })

    # ---------------------------------
    # FINAL RESULT
    # ---------------------------------

    return {

        "topic": topic,

        "report_type": report_type,

        "sources": evidence_results,

        "plan": plan,

        "research": research,

        "analysis": analysis,

        "verification": verification,

        "report": report,

        "review": review,

        "agent_runs": agent_runs,

        "verification_status": "reviewed",

        "reviewer_score": reviewer_score,

        "quality": {

            "evidence_count":
                len(evidence_results),

            "cited_source_ids":
                cited_ids,

            "evidence_coverage":
                round(
                    len(cited_ids)
                    / len(evidence_results),
                    2
                )
                if evidence_results
                else 0.0,

            "unknown_citations":
                unknown_citations,

            "citation_integrity":
                not unknown_citations,
        },

        "revision_count":
            revision_count,

        "generated_at":
            finished,
    }