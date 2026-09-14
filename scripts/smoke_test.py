"""
End-to-end smoke test against a RUNNING backend.

This is the check to run before every demo recording, and the first
thing to run if something looks broken. Unlike pytest (which tests the
app in-process), this exercises the real HTTP server the way the
frontend does.

    python scripts/smoke_test.py

Exits non-zero if anything fails, so it can gate a demo run.
"""
import sys
import json

import requests

BASE = "http://localhost:8000"

PASS = "  [PASS]"
FAIL = "  [FAIL]"

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"{PASS} {label}")
    else:
        print(f"{FAIL} {label} {detail}")
        failures.append(label)


def main():
    print(f"\nSmoke testing {BASE}\n" + "-" * 50)

    # 1. Health
    try:
        health = requests.get(f"{BASE}/api/health", timeout=30).json()
    except Exception as e:  # noqa: BLE001
        print(f"{FAIL} backend unreachable: {e}")
        print("\nStart it with: uvicorn app.main:app --reload --port 8000")
        sys.exit(1)

    check("health endpoint responds", health.get("status") == "ok")
    check("reports zero external calls", health.get("external_calls") == 0)

    mode = "REAL MODELS" if health.get("use_real_model") else "STUB MODE"
    print(f"\n  Running in: {mode}")
    print(f"  Reasoning:  {health.get('reasoning_model')}")
    print(f"  Code:       {health.get('code_model')}")
    print(f"  Models up:  {json.dumps(health.get('models', {}))}")
    print(f"  KB:         {health.get('knowledge_base_status', {}).get('available')}")
    print("-" * 50)

    # 2. Document flow
    print("\nScenario 1 - document flow")
    doc = requests.post(
        f"{BASE}/api/tasks/document", data={"use_sample": "true"}, timeout=180
    ).json()

    check("returns findings", len(doc.get("findings", [])) > 0)
    check("preserves equipment tags",
          any("PL-204B" in f for f in doc.get("findings", [])),
          "- OCR or reasoning step lost the tag")
    check("produces a docx", str(doc.get("output_file", "")).endswith(".docx"))

    dl = requests.get(f"{BASE}/api/outputs/{doc['output_file']}", timeout=30)
    check("docx is downloadable", dl.status_code == 200 and dl.content[:2] == b"PK")

    # 3. Code flow
    print("\nScenario 2 - code flow")
    for prompt in ["compute the average of a list", "check if a number is prime"]:
        res = requests.post(
            f"{BASE}/api/tasks/code", data={"prompt": prompt}, timeout=180
        ).json()
        check(f"{prompt!r} executes cleanly",
              res.get("result", {}).get("ok") is True,
              f"- {res.get('result', {}).get('stderr', '')[:120]}")

    # 4. Activity log
    print("\nActivity log")
    logs = requests.get(f"{BASE}/api/logs", timeout=30).json()["logs"]
    stages = {entry["stage"] for entry in logs}
    check("logs planning step", "plan" in stages)
    check("logs model routing", "route" in stages)
    check("logs tool calls", any(s.startswith("tool") for s in stages))
    check("logs completion", "done" in stages)

    # Result
    print("\n" + "=" * 50)
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED: {', '.join(failures)}")
        sys.exit(1)
    print("ALL CHECKS PASSED - safe to record the demo.")
    sys.exit(0)


if __name__ == "__main__":
    main()
