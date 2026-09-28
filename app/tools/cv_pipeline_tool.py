"""
Adapter for the standalone CV engineering-drawing pipeline
(urjakavach/pipeline.py's UrjaKavachPipeline) — symbol detection,
geometry/line extraction, and topology reconstruction for attached P&ID/PFD
images.

Gated behind config.USE_CV_PIPELINE (off by default). Runs alongside plain
OCR, never in place of it: any failure here (missing weights, an
unreachable PaddleOCR-VL model download, a corrupt image, ...) degrades
silently to None so the caller always still has the OCR text to fall back
on — same resilience pattern as kb_tool.py and model_router's stub fallback.

The pipeline itself is expensive to construct (it loads several models), so
it is built once per process and reused, not per request.
"""
_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from urjakavach.pipeline import UrjaKavachPipeline

        _pipeline = UrjaKavachPipeline()
    return _pipeline


def analyze_engineering_drawing(image_path: str) -> dict | None:
    """Runs the CV pipeline on an image and returns a JSON-safe evidence
    dict (verified entities, connections, drawing metadata, stats), or
    None on any failure."""
    try:
        pipeline = _get_pipeline()
        result = pipeline.process_drawing(image_path)
        evidence = result["graph"].get_evidence_summary()
        evidence["stats"] = result.get("stats", {})
        return evidence
    except Exception:  # noqa: BLE001 - any failure -> OCR-only fallback, never a crash
        return None
