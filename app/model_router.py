"""
Model Router — picks the right model for each subtask and calls it.

This is the module that makes the "Model Router" box in the architecture
diagram real: reasoning subtasks go to one model, code subtasks go to a
different one, each served by its own local llama.cpp server.

    reasoning  ->  localhost:8080  (Llama-3.2-3B-Instruct)
    code       ->  localhost:8081  (Qwen2.5-Coder-1.5B-Instruct)
    ocr/vision ->  Tesseract (a local tool, not an LLM)

Two execution modes, switched by USE_REAL_MODEL in .env:

    USE_REAL_MODEL=true   real llama.cpp inference
    USE_REAL_MODEL=false  deterministic stub (no model needed)

The stub is not a placeholder to be deleted — it is the demo safety net.
If a model is slow, unavailable, or produces garbage minutes before you
record, flip the flag and every flow still works. Real calls also fall
back to the stub automatically if the server is unreachable, so a
teammate who has not started llama-server can still run the whole app.

Owner: Track A.
"""
import re
import json

from . import config
from . import prompts

# --------------------------------------------------------------------
# Routing table — task type -> which model serves it
# --------------------------------------------------------------------
MODEL_REGISTRY = {
    "reasoning": {
        "name": config.REASONING_MODEL_NAME,
        "url": config.REASONING_MODEL_URL,
    },
    "code": {
        "name": config.CODE_MODEL_NAME,
        "url": config.CODE_MODEL_URL,
    },
    "ocr": {
        "name": "Tesseract OCR (local tool)",
        "url": None,
    },
}


def route_task(task_type: str) -> dict:
    """Pick the model config for a subtask type."""
    if task_type in ("ocr", "vision", "document_understanding"):
        return MODEL_REGISTRY["ocr"]
    if task_type == "code":
        return MODEL_REGISTRY["code"]
    return MODEL_REGISTRY["reasoning"]


def model_name_for(task_type: str) -> str:
    """Human-readable model name, used in the activity log so the demo
    visibly shows two different models handling two different tasks."""
    if not config.USE_REAL_MODEL and task_type != "ocr":
        return f"{route_task(task_type)['name']} (stub mode)"
    return route_task(task_type)["name"]


# --------------------------------------------------------------------
# Real inference — OpenAI-compatible llama.cpp server call
# --------------------------------------------------------------------
def _call_model(task_type: str, messages: list[dict]) -> str:
    """POST to the llama.cpp server for this task type. Raises on any
    failure so the caller can fall back to the stub."""
    import requests

    target = route_task(task_type)
    payload = {
        "messages": messages,
        "temperature": config.MODEL_TEMPERATURE,
        "max_tokens": config.MODEL_MAX_TOKENS,
        "stream": False,
    }

    resp = requests.post(
        target["url"],
        json=payload,
        timeout=config.MODEL_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def model_health() -> dict:
    """Check whether each model server is actually reachable. Used by
    /api/health so teammates can see setup problems immediately."""
    if not config.USE_REAL_MODEL:
        return {"mode": "stub", "reasoning": "n/a", "code": "n/a"}

    import requests

    status = {"mode": "real"}
    for key in ("reasoning", "code"):
        url = MODEL_REGISTRY[key]["url"]
        try:
            base = url.split("/v1/")[0]
            r = requests.get(f"{base}/health", timeout=3)
            status[key] = "up" if r.status_code == 200 else f"http {r.status_code}"
        except Exception as e:  # noqa: BLE001
            status[key] = f"unreachable ({type(e).__name__})"
    return status


# --------------------------------------------------------------------
# Public task functions — real call with automatic stub fallback
# --------------------------------------------------------------------
def summarize_findings(raw_text: str, kb_context: str = "") -> tuple[list[str], str]:
    """Extract engineering findings from OCR'd report text.

    Returns (findings, source) where source is "model" or "stub" so the
    orchestrator can log honestly which path actually ran."""
    if config.USE_REAL_MODEL:
        try:
            messages = prompts.build_findings_prompt(raw_text, kb_context)
            raw = _call_model("reasoning", messages)
            findings = _parse_findings(raw)
            if findings:
                return findings, "model"
        except Exception:  # noqa: BLE001 - any failure -> stub, never a crash
            pass

    return _stub_summarize_findings(raw_text), "stub"


def generate_code(prompt: str) -> tuple[str, str]:
    """Generate self-contained Python for a plain-English request.

    Returns (code, source) where source is "model" or "stub"."""
    if config.USE_REAL_MODEL:
        try:
            messages = prompts.build_code_prompt(prompt)
            raw = _call_model("code", messages)
            code = _strip_code_fences(raw)
            if code.strip():
                return code, "model"
        except Exception:  # noqa: BLE001
            pass

    return _stub_generate_code(prompt), "stub"

def chat(
    history: list[dict],
    kb_context: str = "",
    attached_text: str = "",
    doc_context: dict | None = None,
    documents: list[dict] | None = None,
) -> tuple[str, str]:
    """General-purpose chat reply, grounded on kb_context/attached_text/doc_context
    or multiple session documents. Returns (reply, source)."""
    if config.USE_REAL_MODEL:
        try:
            messages = prompts.build_chat_prompt(
                history,
                kb_context=kb_context,
                attached_text=attached_text,
                doc_context=doc_context,
                documents=documents,
            )
            reply = _call_model("reasoning", messages)
            if reply.strip():
                return reply, "model"
        except Exception:  # noqa: BLE001
            pass

    return _stub_chat_reply(
        history,
        attached_text=attached_text,
        doc_context=doc_context,
        documents=documents,
    ), "stub"


def _extract_json_dict(raw: str) -> dict:
    """Extract first valid JSON object from model output."""
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if match:
        raw = match.group(1).strip()
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        raw = raw[first_brace : last_brace + 1]
    return json.loads(raw)


def generate_presentation_content(
    topic: str,
    context: str = "",
    findings: list[str] | None = None,
) -> tuple[dict, str]:
    """Generate real slide-deck presentation content (title, subtitle, slides with points)."""
    if config.USE_REAL_MODEL:
        try:
            msgs = prompts.build_presentation_prompt(topic, context=context, findings=findings)
            raw = _call_model("reasoning", msgs)
            parsed = _extract_json_dict(raw)
            if isinstance(parsed, dict) and "slides" in parsed and len(parsed["slides"]) >= 2:
                slides = []
                for s in parsed["slides"]:
                    if isinstance(s, dict) and "header" in s:
                        pts = [str(p).strip() for p in s.get("points", []) if str(p).strip()]
                        if pts:
                            slides.append({"header": str(s["header"]), "points": pts})
                if len(slides) >= 2:
                    return {
                        "title": str(parsed.get("title") or topic[:60]),
                        "subtitle": str(parsed.get("subtitle") or "UrjaKavach Sovereign Analysis"),
                        "slides": slides,
                    }, "model"
        except Exception:
            pass

    return _dynamic_presentation_fallback(topic, context=context, findings=findings), "stub"


def generate_table_content(
    topic: str,
    context: str = "",
    findings: list[str] | None = None,
) -> tuple[dict, str]:
    """Generate real tabular dataset content (title, headers, rows)."""
    if config.USE_REAL_MODEL:
        try:
            msgs = prompts.build_table_prompt(topic, context=context, findings=findings)
            raw = _call_model("reasoning", msgs)
            parsed = _extract_json_dict(raw)
            if isinstance(parsed, dict) and "headers" in parsed and "rows" in parsed:
                headers = [str(h) for h in parsed["headers"]]
                rows = [list(r) for r in parsed["rows"] if isinstance(r, (list, tuple))]
                if headers and rows:
                    return {
                        "title": str(parsed.get("title") or topic[:60]),
                        "headers": headers,
                        "rows": rows,
                    }, "model"
        except Exception:
            pass

    return _dynamic_table_fallback(topic, context=context, findings=findings), "stub"


def _dynamic_presentation_fallback(topic: str, context: str = "", findings: list[str] | None = None) -> dict:
    """Generate dynamic, topic-grounded presentation content without hardcoded refinery boilerplate."""
    clean_topic = re.sub(r"(?i)\b(generate|create|make|powerpoint|presentation|ppt|pptx|slide deck|slides|about|on)\b", "", topic).strip()
    title = clean_topic.title() if len(clean_topic) > 3 else "Technical Briefing & Analysis"
    
    # Gather actual points from findings and context
    all_pts = []
    if findings:
        all_pts.extend(findings)
    if context:
        lines = [l.strip() for l in context.splitlines() if len(l.strip()) > 10 and not l.strip().startswith(("#", "//", "/*"))]
        all_pts.extend(lines[:8])

    slide1_pts = all_pts[:3] if len(all_pts) >= 3 else [
        f"Core objective: {title}",
        "Comprehensive on-premise technical review",
        "Key requirements and architectural parameters established",
    ]

    slide2_pts = all_pts[3:6] if len(all_pts) >= 6 else (all_pts[:3] if all_pts else [
        "Primary telemetry and operational characteristics reviewed",
        "Verified against sovereign engineering standards",
        "Deterministic parameter validation completed",
    ])

    slide3_pts = all_pts[6:9] if len(all_pts) >= 9 else [
        "Multi-component synchronization and data integrity verified",
        "Cross-document context preserved in session memory",
        "System operating within verified design specifications",
    ]

    slide4_pts = [
        f"Execute verified actions for {title}",
        "Continuous on-premise monitoring and verification",
        "Maintain sovereign audit logging for regulatory compliance",
    ]

    return {
        "title": title,
        "subtitle": "UrjaKavach Sovereign On-Premise Analysis",
        "slides": [
            {"header": "1. Executive Summary & Scope", "points": slide1_pts},
            {"header": "2. Technical Observations & Findings", "points": slide2_pts},
            {"header": "3. Detailed Architectural Breakdown", "points": slide3_pts},
            {"header": "4. Action Plan & Roadmap", "points": slide4_pts},
        ],
    }


def _dynamic_table_fallback(topic: str, context: str = "", findings: list[str] | None = None) -> dict:
    from .tools.deliverable_builder import parse_tabular_data
    title, headers, rows = parse_tabular_data(context, findings=findings)
    return {
        "title": title,
        "headers": headers,
        "rows": rows,
    }



# --------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------
def _parse_findings(raw: str) -> list[str]:
    """Turn the model's line-per-finding output into a clean list."""
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # strip leading bullets / numbering the model may add anyway
        line = re.sub(r"^[-*•]\s*", "", line)
        line = re.sub(r"^\d+[.)]\s*", "", line)
        if len(line) > 3:
            lines.append(line)
    return lines[:8]


def _strip_code_fences(raw: str) -> str:
    """Models often wrap code in ```python fences despite instructions."""
    fence = re.search(r"```(?:python)?\s*\n(.*?)```", raw, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return raw.strip()


# --------------------------------------------------------------------
# Deterministic stubs — the safety net, and the default for teammates
# who have not set up a local model yet.
# --------------------------------------------------------------------
_FINDING_KEYWORDS = [
    "leak", "corrosion", "pressure", "vibration", "temperature",
    "crack", "wear", "fault", "recommend", "replace", "abnormal",
    "deviation", "exceed", "overdue",
]


def _stub_summarize_findings(raw_text: str) -> list[str]:
    # Split text into non-empty lines and sentences
    raw_lines = [line.strip() for line in raw_text.splitlines() if line.strip() and len(line.strip()) > 6]
    sentences = [s.strip() for s in raw_text.replace("\n", " ").split(".") if len(s.strip()) > 8]

    # 1. Industrial/equipment keywords
    findings = [s for s in sentences if any(k in s.lower() for k in _FINDING_KEYWORDS)]
    if findings:
        return findings[:6]

    # 2. General document / code / note extraction: take top informative lines or sentences
    candidates = []
    for item in raw_lines:
        clean = re.sub(r"^[-*•\d.)]\s*", "", item)
        if len(clean) > 8 and not clean.startswith(("//", "/*")):
            candidates.append(clean)
            if len(candidates) >= 6:
                break
    if candidates:
        return candidates

    return sentences[:5] if sentences else ["Document analyzed successfully."]


_CODE_TEMPLATES = {
    "average": (
        "def average(nums):\n"
        "    return sum(nums) / len(nums)\n\n"
        "data = [12, 45, 7, 89, 23, 56]\n"
        "print('Input:', data)\n"
        "print('Average:', average(data))\n"
    ),
    "prime": (
        "def is_prime(n):\n"
        "    if n < 2:\n"
        "        return False\n"
        "    for i in range(2, int(n ** 0.5) + 1):\n"
        "        if n % i == 0:\n"
        "            return False\n"
        "    return True\n\n"
        "primes = [n for n in range(2, 50) if is_prime(n)]\n"
        "print('Primes under 50:', primes)\n"
    ),
    "sort": (
        "data = [38, 27, 43, 3, 9, 82, 10]\n"
        "print('Before:', data)\n"
        "data.sort()\n"
        "print('After:', data)\n"
    ),
}

_DEFAULT_CODE = (
    "# Generated for prompt: {prompt!r}\n"
    "print('Task received:', {prompt!r})\n"
    "print('UrjaKavach code-sandbox check: OK')\n"
)


def _stub_generate_code(prompt: str) -> str:
    p = prompt.lower()
    for key, code in _CODE_TEMPLATES.items():
        if key in p:
            return code
    return _DEFAULT_CODE.format(prompt=prompt)


def _stub_chat_reply(
    history: list[dict],
    attached_text: str = "",
    doc_context: dict | None = None,
    documents: list[dict] | None = None,
) -> str:
    last_user = next(
        (m.get("prompt") or m.get("content", "") for m in reversed(history) if m["role"] == "user"),
        "",
    )

    all_docs = []
    if documents:
        all_docs = list(documents)
    elif doc_context:
        all_docs = [doc_context]

    note = "\n\n*(Running in deterministic stub mode — connect local llama-server on port 8080 for generative inference.)*"

    if all_docs:
        doc_blocks = []
        for idx, d in enumerate(all_docs, start=1):
            s_name = d.get("source_name", f"Document {idx}")
            f_list = d.get("findings", [])
            bullets = "\n".join(f"  • {f}" for f in f_list[:4]) if f_list else "  • Content loaded and active in memory."
            doc_blocks.append(f"**Document {idx} ({s_name}):**\n{bullets}")

        docs_header = "\n\n".join(doc_blocks) + "\n\n"

        q_lower = last_user.lower()
        if any(k in q_lower for k in ["summary", "summarize", "analyze", "what", "tell", "overview", "findings"]):
            return (
                f"{docs_header}"
                f"**Summary:** The {len(all_docs)} document(s) uploaded in this session are listed above with their respective highlights. "
                f"All documents co-exist in this session's memory and can be referenced at any time."
                f"{note}"
            )
        return (
            f"{docs_header}"
            f"**Regarding your query:** *\"{last_user}\"*\n"
            f"Context from all {len(all_docs)} document(s) is active in this session. You can ask specific questions about any of them."
            f"{note}"
        )

    if attached_text:
        return (
            f"Analyzed attached text ({len(attached_text)} characters).\n"
            f"Query: \"{last_user}\""
            f"{note}"
        )

    return f"You said: \"{last_user}\".{note}"


def draft_skill_content(
    role_name: str,
    description: str,
    use_cases: list[str] | None = None,
    guidelines: str = "",
) -> str:
    """Invokes the Meta-Agent (reasoning model) to draft a structured SKILL.md file."""
    if config.USE_REAL_MODEL:
        msgs = prompts.build_skill_draft_prompt(role_name, description, use_cases, guidelines)
        try:
            raw = _call_model("reasoning", msgs)
            if raw and len(raw.strip()) > 100:
                return raw.strip()
        except Exception:
            pass

    # High-quality fallback template
    uc_str = ", ".join(use_cases) if use_cases else "Industrial Domain Engineering"
    return f"""# {role_name} Skill Specification

## 1. Domain Scope & Objectives
The {role_name} is an autonomous agent specialized in {description}.
It is designed to automate analysis, perform verification, and generate authoritative industrial deliverables for the following use cases:
- {uc_str}

## 2. Applicable Standards & Codes
- Relevant Industrial & Engineering Standards (e.g. ASME, API, TEMA, ISO, OISD).
- Facility Standard Operating Procedures (SOPs) and safety guidelines.

## 3. Core Calculations & Technical Rules
- Maintain strict dimensional units across all calculations (e.g. SI / Imperial).
- Calculate key technical indicators, efficiencies, and variances deterministically.
- When calculations involve complex mathematical equations, execute Python code via the sandbox.

## 4. Operational Guardrails & Safety Thresholds
- Always highlight any critical anomaly, over-pressure, or over-temperature condition.
- Maintain zero tolerance for invented/hallucinated equipment tags or telemetry values.
- Verify remaining operational limits against standard design baselines.

## 5. Expected Deliverable Formats
- **Technical Slides (.pptx)**: High-level overview, engineering methodology, findings, and recommendations.
- **Data Spreadsheets (.xlsx)**: Tabular telemetry, parameters, and status indicators with auto-fitted widths.
- **Formal Memos (.docx)**: Comprehensive engineering memos with standard PSU headers.
"""

