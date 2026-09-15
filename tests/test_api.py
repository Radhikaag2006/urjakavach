"""
API-layer tests — every endpoint, end to end, without a running server.
Run: pytest -v
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import auth as _auth

client = TestClient(app)


# ---------------------------------------------------------------------------
# Auth helpers — register a test user once per module and share the token
# ---------------------------------------------------------------------------
_TEST_IDENTIFIER = "testuser@urjakavach.local"
_TEST_PASSWORD   = "testpassword123"

def _get_test_token() -> str:
    """Register the test user (idempotent) and return a valid bearer token."""
    try:
        _auth.register_user(
            _TEST_IDENTIFIER, _TEST_PASSWORD,
            name="Test User", profession="Engineer",
            country="India", emp_code="123456", github_id="testgithub",
        )
    except ValueError:
        pass  # already registered
    return _auth.authenticate_user(_TEST_IDENTIFIER, _TEST_PASSWORD)

_TOKEN = _get_test_token()
_AUTH_HEADERS = {"Authorization": f"Bearer {_TOKEN}"}


class TestHealth:
    def test_health_ok(self):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["external_calls"] == 0

    def test_health_reports_model_mode(self):
        data = client.get("/api/health").json()
        assert "use_real_model" in data
        assert "reasoning_model" in data
        assert "code_model" in data


class TestDocumentFlow:
    def test_sample_document_flow(self):
        res = client.post("/api/tasks/document", data={"use_sample": "true"}, headers=_AUTH_HEADERS)
        assert res.status_code == 200

        data = res.json()
        assert len(data["task_id"]) == 8
        assert len(data["findings"]) > 0
        assert data["output_file"].endswith(".docx")
        # domain tags must be preserved through the whole pipeline
        assert any("PL-204B" in f for f in data["findings"])

    def test_generated_docx_is_downloadable(self):
        data = client.post("/api/tasks/document", data={"use_sample": "true"}, headers=_AUTH_HEADERS).json()
        res = client.get(f"/api/outputs/{data['output_file']}")
        assert res.status_code == 200
        assert res.content[:2] == b"PK"

    def test_rejects_path_traversal(self):
        res = client.get("/api/outputs/../config.py")
        assert res.status_code in (400, 404)

    def test_missing_output_404s(self):
        res = client.get("/api/outputs/does_not_exist.docx")
        assert res.status_code == 404

    def test_rejects_empty_upload(self):
        res = client.post(
            "/api/tasks/document",
            data={"use_sample": "false"},
            files={"file": ("empty.png", b"", "image/png")},
            headers=_AUTH_HEADERS,
        )
        assert res.status_code == 400

    def test_rejects_corrupt_image(self):
        res = client.post(
            "/api/tasks/document",
            data={"use_sample": "false"},
            files={"file": ("fake.png", b"this is not a real image", "image/png")},
            headers=_AUTH_HEADERS,
        )
        assert res.status_code == 400


class TestCodeFlow:
    @pytest.mark.parametrize("prompt", ["average", "prime", "sort"])
    def test_known_prompts_execute_successfully(self, prompt):
        res = client.post("/api/tasks/code", data={"prompt": prompt})
        assert res.status_code == 200

        data = res.json()
        assert data["result"]["ok"] is True
        assert len(data["result"]["stdout"]) > 0

    def test_empty_prompt_rejected(self):
        res = client.post("/api/tasks/code", data={"prompt": "   "})
        assert res.status_code == 400

    def test_rejects_whitespace_only_prompt(self):
        res = client.post("/api/tasks/code", data={"prompt": "     "})
        assert res.status_code == 400

    def test_rejects_overly_long_prompt(self):
        res = client.post("/api/tasks/code", data={"prompt": "x" * 3000})
        assert res.status_code == 400


class TestActivityLog:
    def test_log_captures_every_stage(self):
        client.post("/api/tasks/code", data={"prompt": "average"})
        logs = client.get("/api/logs").json()["logs"]

        stages = [entry["stage"] for entry in logs]
        assert "plan" in stages
        assert "route" in stages
        assert "tool:code_gen" in stages
        assert "tool:code_sandbox" in stages
        assert "done" in stages

    def test_log_entries_well_formed(self):
        client.post("/api/tasks/code", data={"prompt": "sort"})
        logs = client.get("/api/logs").json()["logs"]

        for entry in logs:
            assert {"ts", "task_id", "stage", "detail", "meta"} <= set(entry)

    def test_document_flow_logs_model_routing(self):
        """The ROUTE lines are the demo's visual proof of multi-model
        routing — they must actually be written."""
        client.post("/api/tasks/document", data={"use_sample": "true"}, headers=_AUTH_HEADERS)
        logs = client.get("/api/logs").json()["logs"]

        route_lines = [e["detail"] for e in logs if e["stage"] == "route"]
        assert len(route_lines) >= 2
        assert any("Tesseract" in line for line in route_lines)


class TestChatDocumentMemory:
    def test_chat_with_document_attachment_creates_memory(self):
        """Attaching a document in chat runs OCR, extracts findings, stores into session memory (M1), and assigns message IDs."""
        with open("app/samples/inspection_report.png", "rb") as f:
            img_bytes = f.read()

        res = client.post(
            "/api/chat",
            data={"message": "Summarize this inspection report"},
            files={"file": ("report.png", img_bytes, "image/png")},
            headers=_AUTH_HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert "message_id" in data
        assert "user_message_id" in data
        assert len(data.get("findings", [])) > 0
        assert data["grounded"] is True

        # Verify session storage has document_context and message IDs
        session_id = data["session_id"]
        sess_res = client.get(f"/api/chat/sessions/{session_id}", headers=_AUTH_HEADERS)
        assert sess_res.status_code == 200
        sess_data = sess_res.json()
        assert sess_data["document_context"] is not None
        assert sess_data["document_context"]["source_name"] == "report.png"
        assert len(sess_data["document_context"]["findings"]) > 0

        # Check messages
        messages = sess_data["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["id"] is not None
        assert messages[0]["document"]["filename"] == "report.png"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["id"] is not None

    def test_followup_message_retains_document_memory(self):
        """A subsequent prompt in the same session without an attachment must remain grounded in the document context."""
        # 1. Start chat with attachment
        with open("app/samples/inspection_report.png", "rb") as f:
            img_bytes = f.read()

        res1 = client.post(
            "/api/chat",
            data={"message": "Analyze report"},
            files={"file": ("report.png", img_bytes, "image/png")},
            headers=_AUTH_HEADERS,
        )
        session_id = res1.json()["session_id"]

        # 2. Send follow-up prompt without re-attaching document
        res2 = client.post(
            "/api/chat",
            data={"session_id": session_id, "message": "What is the recommended action?"},
            headers=_AUTH_HEADERS,
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert any(d.get("source_name") == "report.png" or d.get("name") == "report.png" for d in data2.get("all_documents", [])) or "report.png" in data2["reply"] or "Document Memory Grounding" in data2["reply"]

    def test_chat_document_only_without_prompt(self):
        """User can attach a document without typing a prompt; it defaults gracefully."""
        with open("app/samples/inspection_report.png", "rb") as f:
            img_bytes = f.read()

        res = client.post(
            "/api/chat",
            data={},
            files={"file": ("doc_only.png", img_bytes, "image/png")},
            headers=_AUTH_HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["grounded"] is True
        assert len(data["findings"]) > 0

    def test_multi_document_upload_in_single_prompt(self):
        """Attach multiple files in one message; verify all are parsed and recorded."""
        doc1_content = b"Unit 1: Data Structures\nArrays, Linked Lists, Trees and Graphs\nMidterm: Oct 20"
        doc2_content = b"class Calculator:\n    def add(self, a, b):\n        return a + b\ncalc = Calculator()"

        res = client.post(
            "/api/chat",
            data={"message": "Review syllabus and code"},
            files=[
                ("files", ("syllabus.txt", doc1_content, "text/plain")),
                ("files", ("calculator.py", doc2_content, "text/x-python")),
            ],
            headers=_AUTH_HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["grounded"] is True
        assert len(data.get("documents", [])) == 2
        doc_names = [d["filename"] for d in data["documents"]]
        assert "syllabus.txt" in doc_names
        assert "calculator.py" in doc_names

        # Verify session stores both documents
        session_id = data["session_id"]
        sess = client.get(f"/api/chat/sessions/{session_id}", headers=_AUTH_HEADERS).json()
        assert len(sess.get("documents", [])) == 2

    def test_multi_turn_documents_accumulate_and_coexist(self):
        """Documents uploaded in separate turns must accumulate rather than overwriting previous documents."""
        # Turn 1: Upload syllabus
        res1 = client.post(
            "/api/chat",
            data={"message": "Here is the course syllabus"},
            files={"file": ("syllabus.txt", b"Course: Advanced Algorithms\nTopics: DP, Greedy, Graphs", "text/plain")},
            headers=_AUTH_HEADERS,
        )
        assert res1.status_code == 200
        session_id = res1.json()["session_id"]
        assert len(res1.json().get("all_documents", [])) == 1

        # Turn 2: Upload C++ OOPs code in the same session
        res2 = client.post(
            "/api/chat",
            data={"session_id": session_id, "message": "Here is my C++ OOP code"},
            files={"file": ("oops_code.cpp", b"#include <iostream>\nclass Vehicle { virtual void run() = 0; };", "text/x-c++src")},
            headers=_AUTH_HEADERS,
        )
        assert res2.status_code == 200
        data2 = res2.json()
        all_docs = data2.get("all_documents", [])
        assert len(all_docs) == 2
        all_doc_names = [d["source_name"] for d in all_docs]
        assert "syllabus.txt" in all_doc_names
        assert "oops_code.cpp" in all_doc_names

        # Turn 3: Follow-up question without attachment — both contexts must remain active
        res3 = client.post(
            "/api/chat",
            data={"session_id": session_id, "message": "Can you summarize both files I gave you?"},
            headers=_AUTH_HEADERS,
        )
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["grounded"] is True
        assert len(data3.get("all_documents", [])) == 2

    def test_unified_chat_autonomous_code_execution(self):
        """Unified chat autonomously detects coding request, executes in sandbox, and returns code_result."""
        res = client.post(
            "/api/chat",
            data={"message": "Write a python script to calculate the average of numbers"},
            headers=_AUTH_HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("code_result") is not None
        assert data["code_result"]["ok"] is True
        assert len(data["code_result"]["stdout"]) > 0
        assert len(data["reply"]) > 0

        # Check session message persistence
        session_id = data["session_id"]
        sess = client.get(f"/api/chat/sessions/{session_id}", headers=_AUTH_HEADERS).json()
        assistant_msg = next(m for m in sess["messages"] if m["role"] == "assistant")
        assert assistant_msg.get("code_result") is not None

    def test_unified_chat_autonomous_docx_deliverable(self):
        """Unified chat autonomously generates .docx approval note when requested."""
        with open("app/samples/inspection_report.png", "rb") as f:
            img_bytes = f.read()

        res = client.post(
            "/api/chat",
            data={"message": "Please draft an approval note for this inspection report"},
            files={"file": ("inspection_report.png", img_bytes, "image/png")},
            headers=_AUTH_HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("doc_result") is not None
        doc_res = data["doc_result"]
        assert doc_res["output_file"].endswith(".docx")
        assert doc_res["download_url"].startswith("/api/download/")

        # Verify output file is actually downloadable
        dl_res = client.get(f"/api/outputs/{doc_res['output_file']}")
        assert dl_res.status_code == 200
        assert dl_res.content[:2] == b"PK"

    def test_universal_file_upload_tabular_csv(self):
        """Universal file upload cleanly parses spreadsheets (.csv) and stores tabular structure in memory."""
        csv_bytes = b"Sensor_ID,Pressure_PSI,Temperature_C,Status\nSEN-101,142.5,68.2,Normal\nSEN-102,189.0,91.4,Warning\n"
        res = client.post(
            "/api/chat",
            data={"message": "Analyze sensor readings"},
            files={"file": ("readings.csv", csv_bytes, "text/csv")},
            headers=_AUTH_HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["grounded"] is True
        assert len(data.get("documents", [])) == 1
        assert data["documents"][0]["filename"] == "readings.csv"



