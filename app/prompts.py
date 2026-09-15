"""
Organisation-specific prompt grounding (MRPL).

This is the cheapest, highest-leverage way to make the workbench feel
built FOR Mangalore Refinery and Petrochemicals Limited rather than a
generic assistant. Every prompt sent to the reasoning model carries
this domain context.

Owner: Track A (model layer). Edit freely — no other module needs to
change when you tune these strings.
"""

ORG_NAME = "Mangalore Refinery and Petrochemicals Limited (MRPL)"

# --------------------------------------------------------------------
# Domain context injected into every reasoning call
# --------------------------------------------------------------------
ORG_CONTEXT = f"""You are the on-premise engineering assistant for {ORG_NAME},
a petroleum refining and petrochemical facility. You operate entirely inside
the plant's air-gapped network. No data you see may ever leave the facility.

Domain conventions you must follow:
- Pipeline segments are tagged like PL-204B, PL-118A.
- Pressure gauges are tagged like PG-11, PG-07. Pumps like P-7, P-12.
- Heat exchangers like E-301. Columns like C-102.
- Inspection findings fall into these categories: corrosion, gasket/seal wear,
  pressure deviation, temperature excursion, vibration anomaly, leak detection,
  insulation damage, structural/support defect.
- Severity is expressed as: Observation, Minor, Major, or Critical.
- Always preserve exact equipment tags and numeric readings from the source.
- Never invent readings, tags or dates that are not present in the source text.
"""

# --------------------------------------------------------------------
# Task-specific prompts
# --------------------------------------------------------------------
FINDINGS_SYSTEM_PROMPT = """You are an intelligent document analysis and extraction assistant.
Your task: read the provided text (which may be a scanned document, technical report, code file, academic syllabus, letter, or general note) and extract the distinct key points, observations, or takeaways.

Rules:
- If the document is an industrial/equipment report: extract equipment tags, specific readings, anomalies, and recommendations.
- If the document is general text (e.g. code, notes, syllabus, letter, article): extract the core highlights, main topics, key requests, or important points.
- Output ONE concise point per line.
- No numbering, no bullet characters (do NOT output '-', '*', '1.'), no preamble, no closing remarks.
- Each line must be a single complete, informative point directly from the text.
- Never output "no engineering findings" or refuse the text. Always extract the actual highlights of the content.
- Maximum 8 lines.
"""

CODE_SYSTEM_PROMPT = """You are a code generation assistant running on-premise
inside an industrial facility's air-gapped network.

Rules:
- Output ONLY executable Python 3 code. No markdown fences, no explanation.
- The code must be fully self-contained and runnable with no arguments,
  no input() calls, and no third-party imports.
- Include a small inline demo dataset and print the result, so running the
  script proves it works.
- Keep it under 30 lines.
"""


def build_findings_prompt(raw_text: str, kb_context: str = "") -> list[dict]:
    """Assemble the chat messages for the findings-extraction call."""
    user_content = ""
    if kb_context:
        user_content += (
            "Reference material from the plant's own document library:\n"
            f"{kb_context}\n\n"
        )
    user_content += f"Document text:\n{raw_text}"

    return [
        {"role": "system", "content": FINDINGS_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_code_prompt(prompt: str) -> list[dict]:
    """Assemble the chat messages for the code-generation call."""
    return [
        {"role": "system", "content": CODE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]


def build_chat_prompt(
    history: list[dict],
    kb_context: str = "",
    attached_text: str = "",
    doc_context: dict | None = None,
    documents: list[dict] | None = None,
) -> list[dict]:
    """General-purpose chat prompt, grounded on plant docs and/or
    attached documents/images across turns.
    """
    system = (
        "You are UrjaKavach, a sovereign on-premise AI workbench assistant. "
        "You assist with document understanding, code analysis, technical workflows, and general queries. "
        "When attached documents, images, or code are provided in the context below, examine them carefully "
        "and answer the user's questions directly based on their content.\n\n"
        "Important rules regarding documents:\n"
        "- A session may contain multiple attached documents uploaded across different conversation turns.\n"
        "- Different documents may cover completely different topics (for example, a course syllabus, C++ code, a report, or a general note).\n"
        "- All attached documents are valid and co-exist in this session. Never claim a previous document was an error or mistaken.\n"
        "- When answering, distinguish between documents clearly and refer to them by their document titles when appropriate."
    )

    context_parts = []
    if kb_context:
        context_parts.append(
            "Relevant reference material:\n" + kb_context
        )

    # Collect all available documents
    docs_to_include = []
    if documents:
        docs_to_include = list(documents)
    elif doc_context:
        docs_to_include = [doc_context]

    if docs_to_include:
        for idx, doc in enumerate(docs_to_include, start=1):
            source = doc.get("source_name", f"document_{idx}")
            findings = doc.get("findings", [])
            raw = doc.get("raw_text", "")
            
            valid_findings = [
                f for f in findings
                if "no engineering findings" not in f.lower() and "no significant findings" not in f.lower()
            ]
            
            doc_label = f"Document {idx}: {source}" if len(docs_to_include) > 1 else f"Document: {source}"
            doc_section = [f"### [ATTACHED {doc_label.upper()}]"]
            if valid_findings:
                findings_block = "\n".join(f"- {f}" for f in valid_findings[:6])
                doc_section.append(f"Key Points / Highlights:\n{findings_block}")
            if raw.strip():
                doc_section.append(f"Extracted Content:\n\"\"\"\n{raw[:5000]}\n\"\"\"")
            context_parts.append("\n\n".join(doc_section))
    elif attached_text:
        context_parts.append(
            "Attached document content:\n\"\"\"\n" + attached_text[:5000] + "\n\"\"\""
        )

    messages = [{"role": "system", "content": system}]
    if context_parts:
        messages.append({
            "role": "system",
            "content": "\n\n---\n\n".join(context_parts),
        })
    messages.extend(history)
    return messages


PRESENTATION_SYSTEM_PROMPT = """You are an expert executive and technical presentation designer.
Your task is to generate a comprehensive, highly specific 4-to-6 slide presentation based on the user's prompt and provided context.

You must respond ONLY with a valid JSON object matching this schema:
{
  "title": "Clear, compelling main presentation title",
  "subtitle": "Informative subtitle or scope",
  "slides": [
    {
      "header": "Slide 1 Header",
      "points": [
        "Concrete, technical, informative bullet point 1",
        "Concrete, technical, informative bullet point 2",
        "Concrete, technical, informative bullet point 3"
      ]
    }
  ]
}

Rules:
- NEVER use generic placeholders (e.g. do NOT write "Review findings with team", "Implement adjustments", "Ensure compliance").
- Ground EVERY point in the specific facts, terminology, code, metrics, or concepts provided in the prompt/context.
- Each slide must have 3 to 5 detailed, informative bullet points.
- Create 4 to 5 distinct slides (e.g. Overview & Scope, Core Architecture/Findings, Detailed Analysis/Mechanisms, Implementation Roadmap/Actions).
- Output ONLY the raw JSON object. No preamble, no postscript, no markdown code fences.
"""

TABLE_SYSTEM_PROMPT = """You are an expert data analyst and tabular structuring assistant.
Your task is to generate or extract a clean, structured tabular dataset based on the user's prompt and provided context.

You must respond ONLY with a valid JSON object matching this schema:
{
  "title": "Clear descriptive table title",
  "headers": ["Column 1", "Column 2", "Column 3"],
  "rows": [
    ["row1_val1", "row1_val2", "row1_val3"],
    ["row2_val1", "row2_val2", "row2_val3"]
  ]
}

Rules:
- Generate meaningful, specific columns and rows directly relevant to the topic and context.
- Never use generic placeholder rows. Fill the table with real, useful data (at least 4 to 8 rows).
- Output ONLY the raw JSON object. No preamble, no markdown code fences.
"""


def build_presentation_prompt(topic: str, context: str = "", findings: list[str] | None = None) -> list[dict]:
    """Assemble messages for real slide-deck generation."""
    user_content = f"Presentation Request / Topic:\n{topic}"
    if findings:
        user_content += "\n\nExtracted Key Findings:\n" + "\n".join(f"- {f}" for f in findings)
    if context:
        user_content += f"\n\nReference Material / Context:\n{context[:4000]}"

    return [
        {"role": "system", "content": PRESENTATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_table_prompt(topic: str, context: str = "", findings: list[str] | None = None) -> list[dict]:
    """Assemble messages for real tabular dataset generation."""
    user_content = f"Data / Table Request:\n{topic}"
    if findings:
        user_content += "\n\nExtracted Key Findings:\n" + "\n".join(f"- {f}" for f in findings)
    if context:
        user_content += f"\n\nReference Material / Context:\n{context[:4000]}"

    return [
        {"role": "system", "content": TABLE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


SKILL_ARCHITECT_SYSTEM_PROMPT = """You are UrjaKavach's AI Skill Architect and Meta-Agent.
Your job is to draft a rigorous, industrial-grade SKILL.md file for a newly onboarded engineering agent in an air-gapped refinery/PSU environment.

Format your output in clean, structured Markdown containing:
# [Agent Role Name] Skill Specification

## 1. Domain Scope & Objectives
Brief explanation of what this agent is responsible for, its primary deliverables, and operational boundaries.

## 2. Applicable Standards & Codes
List relevant industry codes (e.g. ASME, API 510/570/653, TEMA, OISD, IEEE, ISO) or standard engineering practices.

## 3. Core Equations & Technical Calculations
List the mathematical formulas, thermodynamic/fluid equations, or algorithmic rules this agent must apply.

## 4. Operational Guardrails & Safety Thresholds
Explicit warning conditions, critical tolerances, and anomaly thresholds that require escalation.

## 5. Expected Deliverable Formats
Define how the agent must structure its outputs (e.g. .pptx presentation decks, .xlsx inspection sheets, .docx approval memos, or verified python code).

Rules:
- Output ONLY the markdown document. Do not wrap in conversational preamble.
- Make the rules concrete and engineering-focused with specific numbers, units, and formulas.
"""


def build_skill_draft_prompt(
    role_name: str,
    description: str,
    use_cases: list[str] | None = None,
    guidelines: str = "",
) -> list[dict]:
    """Assemble messages for the Meta-Agent to draft a new SKILL.md."""
    user_content = f"Agent Role Name: {role_name}\nAgent Description: {description}"
    if use_cases:
        user_content += f"\nUse Cases / Scenarios: {', '.join(use_cases)}"
    if guidelines:
        user_content += f"\nSpecial User Domain Guidelines / SOPs:\n{guidelines}"

    return [
        {"role": "system", "content": SKILL_ARCHITECT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]



