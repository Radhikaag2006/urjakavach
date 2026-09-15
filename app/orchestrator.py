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
from . import chat_store

MAX_CODE_ATTEMPTS = 2


def run_document_flow(
    image_path: str, source_name: str, session_id: str | None = None
) -> dict:
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
    if not session_id or chat_store.load(session_id) is None:
        session_id = chat_store.new_session()
    chat_store.append_message(
        session_id, "user", f"Ran Document Flow on {source_name}."
    )
    findings_text = "\n".join(f"- {f}" for f in findings)
    chat_store.append_message(
        session_id, "assistant",
        f"Document Flow findings:\n{findings_text}\n\n"
        f"Extracted document text:\n{raw_text[:3000]}"
    )

    log_step(task_id, "done", "Deliverable ready, shown in UI with full audit log")

    return {
        "task_id": task_id,
        "session_id": session_id,
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

def run_chat_flow(
    session_id: str,
    message: str,
    attachment_path: str | None = None,
    attachment_type: str | None = None,
) -> dict:
    """General-purpose chat: answer a free-form question, optionally
    grounded in an uploaded file and/or the knowledge base, using the
    reasoning model. History persists per session on disk."""
    task_id = str(uuid.uuid4())[:8]
    log_step(
        task_id, "plan",
        f"Chat message received -> {message[:80]!r}",
    )

    chat_store.append_message(session_id, "user", message)

    attached_text = ""
    if attachment_path:
        if attachment_type and attachment_type.startswith("image/"):
            log_step(
                task_id, "route",
                f"Routed attachment to {model_router.model_name_for('ocr')}",
            )
            attached_text = ocr_image(attachment_path)
            log_step(
                task_id, "tool:vision_ocr",
                "Extracted text from attached image",
            )
        else:
            try:
                with open(
                    attachment_path, "r",
                    encoding="utf-8", errors="ignore",
                ) as f:
                    attached_text = f.read()[:8000]
                log_step(task_id, "tool:file_read", "Read attached document")
            except Exception:  # noqa: BLE001
                attached_text = ""

    kb_context = ""
    if config.USE_KNOWLEDGE_BASE:
        kb_context = retrieve_context(message)
        if kb_context:
            log_step(
                task_id, "tool:knowledge_base",
                "Retrieved relevant plant reference material",
            )

    log_step(
        task_id, "route",
        f"Routed chat subtask to {model_router.model_name_for('reasoning')}",
    )

    session = chat_store.load(session_id)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in session["messages"][-10:]
    ]

    reply, source = model_router.chat(history, kb_context, attached_text)
    log_step(
        task_id, "tool:reasoning",
        "Generated chat reply", {"source": source},
    )

    chat_store.append_message(session_id, "assistant", reply)
    log_step(
        task_id, "done",
        "Chat reply ready, shown in UI with full audit log",
    )

    return {
        "task_id": task_id,
        "session_id": session_id,
        "reply": reply,
        "source": source,
        "grounded": bool(kb_context),
    }
