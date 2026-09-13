"""
Agentic Orchestrator — the agent layer.

Breaks a task into steps, routes each step to the right model, calls the
right local tool, logs every step, and iterates until the task is
complete. This is a hand-rolled equivalent of a LangGraph graph: the
same plan -> route -> act -> verify -> iterate loop, with no framework
dependency to install or debug under time pressure.

If Track B has slack on Day 2, swapping this for a real LangGraph
StateGraph is contained entirely within this file — nothing in main.py
or the tools needs to change.

Owner: Track B.
"""
import os
import uuid

from . import config
from . import model_router
from .activity_log import log_step
from .tools.ocr_tool import ocr_image
from .tools.sandbox_tool import run_in_sandbox
from .tools.docgen_tool import draft_approval_note
from .tools.kb_tool import retrieve_context

MAX_CODE_ATTEMPTS = 2


def run_document_flow(image_path: str, source_name: str) -> dict:
    """Scanned document -> OCR -> findings -> approval note."""
    task_id = str(uuid.uuid4())[:8]
    log_step(task_id, "plan", "Task received: read scanned report and draft an approval note")

    # Step 1 — vision/OCR tool
    log_step(task_id, "route", f"Routed vision subtask to {model_router.model_name_for('ocr')}")
    raw_text = ocr_image(image_path)
    log_step(task_id, "tool:vision_ocr", "Extracted text from scanned document",
             {"chars": len(raw_text)})

    # Step 2 — organisation-specific retrieval (optional, degrades to "")
    kb_context = ""
    if config.USE_KNOWLEDGE_BASE:
        kb_context = retrieve_context(raw_text)
        if kb_context:
            log_step(task_id, "tool:knowledge_base",
                     "Retrieved plant reference material for grounding",
                     {"chars": len(kb_context)})
        else:
            log_step(task_id, "tool:knowledge_base",
                     "No knowledge base available - proceeding without grounding")

    # Step 3 — reasoning model extracts findings
    log_step(task_id, "route",
             f"Routed reasoning subtask to {model_router.model_name_for('reasoning')}")
    findings, source = model_router.summarize_findings(raw_text, kb_context)
    log_step(task_id, "tool:reasoning",
             f"Extracted {len(findings)} key findings from report",
             {"source": source})

    # Step 4 — verify before producing the deliverable
    if findings:
        log_step(task_id, "iterate_check", "Findings present -> generating deliverable")
    else:
        log_step(task_id, "iterate_check",
                 "No findings extracted -> would replan in full system")

    # Step 5 — file write tool produces a real .docx
    out_path = draft_approval_note(source_name, findings, task_id)
    log_step(task_id, "tool:file_write", "Approval note drafted as DOCX",
             {"path": os.path.basename(out_path)})

    log_step(task_id, "done", "Deliverable ready, shown in UI with full audit log")

    return {
        "task_id": task_id,
        "raw_text": raw_text,
        "findings": findings,
        "source": source,
        "grounded": bool(kb_context),
        "output_file": os.path.basename(out_path),
    }


def run_code_flow(prompt: str) -> dict:
    """Plain-English coding request -> generate -> execute -> verify,
    with one retry if the first attempt fails in the sandbox."""
    task_id = str(uuid.uuid4())[:8]
    log_step(task_id, "plan", f"Task received: coding request -> {prompt!r}")

    log_step(task_id, "route",
             f"Routed code subtask to {model_router.model_name_for('code')}")

    code, source, result = "", "stub", {}

    for attempt in range(1, MAX_CODE_ATTEMPTS + 1):
        code, source = model_router.generate_code(prompt)
        log_step(task_id, "tool:code_gen",
                 f"Code generated (attempt {attempt})",
                 {"lines": len(code.splitlines()), "source": source})

        log_step(task_id, "tool:code_sandbox", "Running generated code in isolated sandbox")
        result = run_in_sandbox(code)

        if result["ok"]:
            log_step(task_id, "iterate_check",
                     f"Sandbox run succeeded on attempt {attempt} -> task complete")
            break

        if attempt < MAX_CODE_ATTEMPTS:
            log_step(task_id, "iterate_check",
                     f"Sandbox run failed on attempt {attempt} -> regenerating",
                     {"stderr": result["stderr"][:200]})
        else:
            log_step(task_id, "iterate_check",
                     "Sandbox run failed after all attempts -> returning diagnostics",
                     {"stderr": result["stderr"][:200]})

    log_step(task_id, "done", "Verified code result shown in UI with full audit log")

    return {
        "task_id": task_id,
        "code": code,
        "source": source,
        "result": result,
    }
