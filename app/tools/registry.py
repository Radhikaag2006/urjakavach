"""Common Tools Registry for UrjaKavach.

Maintains a catalog of all registered tools with capability metadata,
descriptions, and suggestion logic for newly onboarded agents.
"""

from typing import Any, Dict, List, Optional

REGISTERED_TOOLS: Dict[str, Dict[str, Any]] = {
    "deliverable_builder": {
        "id": "deliverable_builder",
        "name": "Multi-Format Deliverable Generator",
        "category": "Deliverables & Reporting",
        "description": "Synthesizes presentation decks (.pptx), styled spreadsheets (.xlsx), and clean datasets (.csv).",
        "capabilities": ["pptx", "xlsx", "csv", "presentations", "spreadsheets"],
        "is_default": True,
    },
    "sandbox_tool": {
        "id": "sandbox_tool",
        "name": "Python Sandbox Execution Environment",
        "category": "Code & Compute",
        "description": "Executes Python code in an isolated subprocess with timeout protection, returning stdout, stderr, and execution status.",
        "capabilities": ["python", "math", "algorithms", "data_processing", "simulation"],
        "is_default": True,
    },
    "doc_extractor": {
        "id": "doc_extractor",
        "name": "Multi-Format Document & OCR Parser",
        "category": "Document Ingestion",
        "description": "Extracts text and tables from PDFs, Word documents (.docx), plain text files, and scanned images via Tesseract OCR.",
        "capabilities": ["pdf", "docx", "ocr", "images", "text_extraction"],
        "is_default": True,
    },
    "docgen_tool": {
        "id": "docgen_tool",
        "name": "Official Approval Note & Word Generator",
        "category": "Deliverables & Reporting",
        "description": "Generates formal engineering approval notes and Word documents (.docx) adhering to standard PSU memo layouts.",
        "capabilities": ["docx", "approval_note", "formal_memo"],
        "is_default": True,
    },
    "kb_tool": {
        "id": "kb_tool",
        "name": "Plant Knowledge Base & Grounding Tool",
        "category": "Domain Grounding",
        "description": "Retrieves internal refinery standards, equipment specs, and operational parameters for RAG grounding.",
        "capabilities": ["rag", "grounding", "refinery_standards", "equipment_specs"],
        "is_default": False,
    },
}


def list_tools() -> List[Dict[str, Any]]:
    """Return all registered tools as a list of dicts."""
    return list(REGISTERED_TOOLS.values())


def get_tool(tool_id: str) -> Optional[Dict[str, Any]]:
    """Get metadata for a specific tool by ID."""
    return REGISTERED_TOOLS.get(tool_id)


def suggest_tools_for_intent(text: str) -> List[str]:
    """Suggest relevant tool IDs based on keywords or intent in a use case / description."""
    text_lower = text.lower()
    suggested = set()

    # Core always suggested for general engineering
    suggested.add("deliverable_builder")
    suggested.add("sandbox_tool")

    if any(k in text_lower for k in ["pdf", "ocr", "scan", "extract", "document", "docx", "image", "paper"]):
        suggested.add("doc_extractor")

    if any(k in text_lower for k in ["approval", "memo", "note", "letter", "formal", "docx", "report"]):
        suggested.add("docgen_tool")

    if any(k in text_lower for k in ["refinery", "standard", "mrpl", "spec", "equipment", "manual", "asme", "api", "sop"]):
        suggested.add("kb_tool")

    return list(suggested)
