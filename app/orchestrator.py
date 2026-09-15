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
from .tools.doc_extractor import extract_file_content
from .tools.sandbox_tool import run_in_sandbox
from .tools.docgen_tool import draft_approval_note
from .tools.deliverable_builder import generate_presentation, generate_spreadsheet, parse_tabular_data
from .tools.kb_tool import retrieve_context
from . import chat_store
from .agents.agent_store import agent_store

MAX_CODE_ATTEMPTS = 2


def run_document_flow(
    image_path: str,
    source_name: str,
    session_id: str | None = None,
    user_id: str = "default",
) -> dict:
    """Scanned document -> OCR -> findings -> approval note.

    After the flow completes the raw OCR text and extracted findings are
    persisted on the session via chat_store.set_document_context so that
    any subsequent chat message in the same session is automatically
    grounded in the analysed document.
    """
    task_id = str(uuid.uuid4())[:8]
    log_step(task_id, "plan", "Task received: read scanned report and draft an approval note")

    # Step 1 — vision/OCR/text extraction tool
    log_step(task_id, "route", f"Routed extraction subtask to {model_router.model_name_for('ocr')}")
    raw_text = extract_file_content(image_path, filename=source_name)
    log_step(task_id, "tool:doc_extractor", "Extracted content from document",
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

    # Step 6 — persist to session so follow-up chat is grounded in this doc
    if not session_id or chat_store.load(session_id) is None:
        session_id = chat_store.new_session(user_id=user_id)

    # Store structured document context — this is the key memory link
    doc_meta = chat_store.add_document_context(
        session_id,
        source_name=source_name,
        raw_text=raw_text,
        findings=findings,
        summary=f"Extracted {len(findings)} findings from {source_name}",
    )
    log_step(task_id, "tool:memory", "Document context stored in session memory",
             {"session_id": session_id, "findings_count": len(findings)})

    findings_text = "\n".join(f"- {f}" for f in findings)
    doc_payload = {"filename": source_name, "findings": findings, "chars": len(raw_text)}
    chat_store.append_message(
        session_id,
        "user",
        f"Ran Document Flow on {source_name}.",
        prompt=f"Ran Document Flow on {source_name}.",
        document=doc_payload,
        documents=[doc_payload],
    )
    chat_store.append_message(
        session_id,
        "assistant",
        f"Document Flow completed for {source_name}.\nExtracted {len(findings)} findings.\nApproval Note saved to `{os.path.basename(out_path)}`.\n\nKey Highlights:\n{findings_text}",
        source=source,
        grounded=bool(kb_context),
    )

    log_step(task_id, "done", "Deliverable ready, shown in UI with full audit log")

    return {
        "task_id": task_id,
        "session_id": session_id,
        "raw_text": raw_text,
        "findings": findings,
        "output_file": os.path.basename(out_path),
        "document_path": out_path,
        "download_url": f"/api/download/{os.path.basename(out_path)}",
        "source": source,
        "grounded": bool(kb_context),
    }


def run_code_flow(prompt: str) -> dict:
    """Sandboxed code generation, execution, and self-correction."""
    task_id = str(uuid.uuid4())[:8]
    log_step(task_id, "plan", f"Task received: coding request -> {prompt!r}")

    log_step(task_id, "route", f"Routed code subtask to {model_router.model_name_for('code')}")

    code = ""
    source = "stub"
    result = {"ok": False, "stdout": "", "stderr": "No code generated yet", "returncode": 1}
    last_error = ""

    for attempt in range(1, MAX_CODE_ATTEMPTS + 1):
        try:
            code, source = model_router.generate_code(prompt, last_error=last_error)
        except TypeError:
            code, source = model_router.generate_code(prompt)

        log_step(task_id, "tool:code_gen", f"Code generated (attempt {attempt})",
                 {"lines": len(code.splitlines()), "source": source, "attempt": attempt})

        log_step(task_id, "tool:code_sandbox", "Running generated code in isolated sandbox")
        result = run_in_sandbox(code)

        if result.get("ok"):
            log_step(task_id, "iterate_check",
                     f"Sandbox run succeeded on attempt {attempt} -> task complete")
            break
        else:
            if attempt < MAX_CODE_ATTEMPTS:
                log_step(task_id, "iterate_check",
                         f"Sandbox run failed on attempt {attempt} -> regenerating",
                         {"stderr": result["stderr"][:200]})
                last_error = result["stderr"]
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
    attachment_name: str | None = None,
    attachments: list[dict] | None = None,
    agent_id: str | None = None,
) -> dict:
    """General-purpose chat: answer a free-form question with multi-document and agent support.

    If an agent_id is provided, the agent's domain SKILL.md, system prompt,
    and permitted tools are dynamically bound to the execution pipeline.
    """
    task_id = str(uuid.uuid4())[:8]
    if not session_id or chat_store.load(session_id) is None:
        session_id = chat_store.new_session()

    active_agent = agent_store.get_agent(agent_id) if agent_id else None
    if active_agent:
        log_step(
            task_id, "agent:context",
            f"Active Agent: {active_agent['name']} ({active_agent['id']})",
            {"department": active_agent.get("department"), "tools": active_agent.get("tool_ids", [])}
        )

    # Normalize single attachment args into attachments list
    effective_attachments: list[dict] = []
    if attachments:
        effective_attachments.extend(attachments)
    elif attachment_path:
        effective_attachments.append({
            "path": attachment_path,
            "type": attachment_type,
            "name": attachment_name or os.path.basename(attachment_path),
        })

    att_summary = ", ".join(a.get("name", "doc") for a in effective_attachments)
    log_step(
        task_id, "plan",
        f"Chat message received -> {message[:80]!r}" + (f" (with {len(effective_attachments)} attachment(s): {att_summary})" if effective_attachments else "") + (f" [Agent: {active_agent['name']}]" if active_agent else ""),
    )

    extracted_texts = []
    new_docs_payload = []
    kb_contexts = []

    # Process all incoming attachments
    for att in effective_attachments:
        a_path = att.get("path")
        if not a_path or not os.path.exists(a_path):
            continue
        a_name = att.get("name") or os.path.basename(a_path)
        a_type = att.get("type")

        log_step(
            task_id, "route",
            f"Extracting content from '{a_name}' via doc_extractor",
        )
        text = extract_file_content(a_path, content_type=a_type, filename=a_name)
        log_step(
            task_id, "tool:doc_extractor",
            f"Extracted content from '{a_name}'",
            {"chars": len(text)},
        )

        doc_kb = ""
        if config.USE_KNOWLEDGE_BASE and text:
            doc_kb = retrieve_context(text)
            if doc_kb:
                kb_contexts.append(doc_kb)

        # Extract findings & summary from this document
        findings, doc_src = model_router.summarize_findings(text, doc_kb)
        log_step(
            task_id, "tool:reasoning",
            f"Extracted {len(findings)} key findings/highlights from {a_name}",
            {"source": doc_src},
        )

        # Append to Session Memory M1
        chat_store.add_document_context(
            session_id,
            source_name=a_name,
            raw_text=text,
            findings=findings,
            summary=f"Extracted {len(findings)} observations from {a_name}",
        )
        log_step(
            task_id, "tool:memory",
            f"Document context saved to Session Memory M1: {a_name}",
            {"findings_count": len(findings)},
        )

        new_docs_payload.append({
            "filename": a_name,
            "findings": findings,
            "chars": len(text),
        })
        extracted_texts.append(f"### [ATTACHED DOCUMENT: {a_name}]\n{text}")

    combined_attached_text = "\n\n".join(extracted_texts)

    # If no attachments in this turn, check KB for message
    if not effective_attachments and config.USE_KNOWLEDGE_BASE:
        msg_kb = retrieve_context(message)
        if msg_kb:
            kb_contexts.append(msg_kb)
            log_step(
                task_id, "tool:knowledge_base",
                "Retrieved relevant plant reference material",
            )

    if active_agent:
        agent_context_block = (
            f"=== ACTIVE AGENT: {active_agent['name']} ===\n"
            f"Department: {active_agent.get('department', 'Engineering')}\n"
            f"Role Instructions: {active_agent.get('system_prompt', '')}\n\n"
            f"=== DOMAIN SKILL SPECIFICATION ({active_agent.get('skill_filename', 'SKILL.md')}) ===\n"
            f"{active_agent.get('skill_content', '')}\n"
        )
        kb_contexts.insert(0, agent_context_block)

    combined_kb_context = "\n\n".join(filter(None, kb_contexts))

    # Backward compatibility payload
    doc_payload = new_docs_payload[0] if new_docs_payload else None

    # Record User Message with unique message_id and documents
    user_msg_id = chat_store.append_message(
        session_id,
        role="user",
        content=message,
        prompt=message,
        document=doc_payload,
        documents=new_docs_payload,
    )

    # Retrieve all co-existing documents in session memory
    all_session_docs = chat_store.get_all_documents(session_id)
    doc_context = chat_store.get_document_context(session_id)

    if all_session_docs and not effective_attachments:
        doc_names = ", ".join(d.get("source_name", "?") for d in all_session_docs)
        log_step(
            task_id, "tool:memory",
            f"Grounding query on {len(all_session_docs)} active document(s) in Session Memory M1: {doc_names}",
            {"doc_count": len(all_session_docs)},
        )

    all_findings = [f for d in all_session_docs for f in d.get("findings", [])] or (doc_context.get("findings", []) if doc_context else [])
    msg_lower = (message or "").lower()

    # Autonomous Subtask 1: Code Generation and Sandbox Execution
    code_deliverable = None
    coding_triggers = [
        "write code", "generate code", "python script", "code for", "implement",
        "calculate", "run code", "execute code", "run in sandbox", "sandbox",
        "algorithm", "average", "prime", "sort", "simulation", "compute",
        "write a script", "write python", "function", "program", "code"
    ]
    has_code_attachment = any(
        (att.get("name") or "").lower().endswith(ext)
        for att in effective_attachments
        for ext in [".py", ".cpp", ".c", ".h", ".java", ".js", ".ts", ".sh", ".sql"]
    )
    should_run_code = any(k in msg_lower for k in coding_triggers) or (
        has_code_attachment and any(w in msg_lower for w in ["run", "execute", "test", "output", "verify", "debug", "solve", "compile", "calculate"])
    )

    # Enforce agent tool permissions if restricted
    permitted_tools = set(active_agent.get("tool_ids", [])) if (active_agent and active_agent.get("tool_ids")) else None
    if permitted_tools is not None:
        if "sandbox_tool" not in permitted_tools:
            should_run_code = False

    if should_run_code:
        log_step(
            task_id, "route",
            f"Autonomous subtask routed to {model_router.model_name_for('code')}",
        )
        code_prompt = message
        if combined_attached_text and not any(k in msg_lower for k in ["average", "prime"]):
            code_prompt = f"{message}\n\nContext Reference:\n{combined_attached_text[:1200]}"

        code_flow_res = run_code_flow(code_prompt)
        c_code = code_flow_res.get("code", "")
        c_res = code_flow_res.get("result", {})
        c_src = code_flow_res.get("source", "stub")
        code_deliverable = {
            "code": c_code,
            "stdout": c_res.get("stdout", ""),
            "stderr": c_res.get("stderr", ""),
            "ok": c_res.get("ok", False),
            "returncode": c_res.get("returncode", 0),
            "source": c_src,
            "filename": "solution.py",
        }
        status_str = "Execution Succeeded (exit code 0)" if code_deliverable["ok"] else f"Execution Failed (exit code {code_deliverable['returncode']})"
        combined_attached_text += (
            f"\n\n### [AUTONOMOUS CODE SUBTASK RESULT]\n"
            f"Generated Python Code:\n```python\n{c_code}\n```\n"
            f"Execution Status: {status_str}\n"
            f"Sandbox Stdout:\n{code_deliverable['stdout']}\n"
        )

    # Autonomous Subtask 2: Multi-Format Deliverable Generation (PPT, Excel, CSV, Word)
    doc_deliverable = None
    ppt_triggers = ["ppt", "pptx", "presentation", "slide", "powerpoint", "deck"]
    excel_triggers = ["excel", "xlsx", "spreadsheet", "sheet", "tabular excel"]
    csv_triggers = ["csv", "comma separated", "export csv", "save as csv"]
    docx_triggers = [
        "approval note", "draft note", "generate document", "create docx",
        "formal report", "formal note", "deliverable", "export to word",
        "generate approval", "draft report", "create deliverable", "word doc"
    ]

    should_ppt = any(k in msg_lower for k in ppt_triggers)
    should_excel = any(k in msg_lower for k in excel_triggers)
    should_csv = any(k in msg_lower for k in csv_triggers)
    should_docx = any(k in msg_lower for k in docx_triggers) or (
        not (should_ppt or should_excel or should_csv) and any(k in msg_lower for k in ["report", "deliverable"])
    )

    if permitted_tools is not None:
        if "deliverable_builder" not in permitted_tools:
            should_ppt = False
            should_excel = False
            should_csv = False
        if "docgen_tool" not in permitted_tools:
            should_docx = False

    if should_ppt or should_excel or should_csv or should_docx:
        source_doc_name = (
            effective_attachments[0].get("name")
            if effective_attachments
            else (all_session_docs[0].get("source_name") if all_session_docs else "Technical_Report")
        )
        if not all_findings and combined_attached_text:
            extracted_f, _ = model_router.summarize_findings(combined_attached_text)
            all_findings.extend(extracted_f)

        if should_ppt:
            log_step(
                task_id, "tool:file_write",
                "Autonomous deliverable generation: structuring PowerPoint slide deck (.pptx) via model",
            )
            pres_data, pres_src = model_router.generate_presentation_content(
                message,
                context=combined_attached_text,
                findings=all_findings,
            )
            doc_filename = generate_presentation(
                pres_data,
                task_id=task_id,
            )
            doc_deliverable = {
                "output_file": doc_filename,
                "document_path": os.path.join(config.OUTPUTS_DIR, doc_filename),
                "download_url": f"/api/download/{doc_filename}",
                "file_type": "pptx",
                "findings": all_findings,
                "title": pres_data.get("title", "Presentation"),
            }
        elif should_excel or should_csv:
            fmt = "csv" if (should_csv and not should_excel) else "xlsx"
            log_step(
                task_id, "tool:file_write",
                f"Autonomous deliverable generation: structuring tabular dataset (.{fmt}) via model",
            )
            tbl_data, tbl_src = model_router.generate_table_content(
                message,
                context=combined_attached_text,
                findings=all_findings,
            )
            doc_filename = generate_spreadsheet(
                tbl_data.get("title", "Report"),
                tbl_data.get("headers", ["ID", "Parameter", "Status"]),
                tbl_data.get("rows", []),
                task_id=task_id,
                fmt=fmt,
            )
            doc_deliverable = {
                "output_file": doc_filename,
                "document_path": os.path.join(config.OUTPUTS_DIR, doc_filename),
                "download_url": f"/api/download/{doc_filename}",
                "file_type": fmt,
                "findings": all_findings,
                "title": tbl_data.get("title", "Dataset"),
            }
        else:
            log_step(
                task_id, "tool:file_write",
                "Autonomous deliverable generation: drafting approval note (.docx)",
            )
            doc_path = draft_approval_note(source_doc_name, all_findings, task_id)
            doc_filename = os.path.basename(doc_path)
            doc_deliverable = {
                "output_file": doc_filename,
                "document_path": doc_path,
                "download_url": f"/api/download/{doc_filename}",
                "file_type": "docx",
                "findings": all_findings,
            }

        combined_attached_text += (
            f"\n\n### [GENERATED DELIVERABLE]\n"
            f"An official {doc_deliverable.get('file_type', 'document').upper()} deliverable was generated: '{doc_filename}'. "
            f"Download available at: {doc_deliverable['download_url']}\n"
        )

    log_step(
        task_id, "route",
        f"Routed chat subtask to {model_router.model_name_for('reasoning')}",
    )

    session = chat_store.load(session_id)
    history = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in (session["messages"][-10:] if session else [])
    ]

    reply, source = model_router.chat(
        history,
        combined_kb_context,
        combined_attached_text,
        doc_context=doc_context,
        documents=all_session_docs,
    )
    log_step(
        task_id, "tool:reasoning",
        "Generated chat reply", {"source": source},
    )

    # Record Assistant Message with unique message_id and deliverables
    assistant_msg_id = chat_store.append_message(
        session_id,
        role="assistant",
        content=reply,
        source=source,
        grounded=bool(combined_kb_context or all_session_docs),
        code_result=code_deliverable,
        doc_result=doc_deliverable,
    )

    text_deliverable = {
        "title": "Analysis & Findings" if all_findings else "Technical Response",
        "content": reply,
        "findings": all_findings,
        "grounded": bool(combined_kb_context or all_session_docs),
    }

    return {
        "task_id": task_id,
        "session_id": session_id,
        "message_id": assistant_msg_id,
        "user_message_id": user_msg_id,
        "reply": reply,
        "source": source,
        "grounded": bool(combined_kb_context or all_session_docs),
        "findings": all_findings,
        "document": doc_payload,
        "documents": new_docs_payload,
        "all_documents": all_session_docs,
        "code_result": code_deliverable,
        "doc_result": doc_deliverable,
        "text_deliverable": text_deliverable,
        "agent": active_agent,
    }
