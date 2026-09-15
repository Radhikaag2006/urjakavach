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

