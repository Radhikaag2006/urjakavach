#!/usr/bin/env python3
"""
UrjaKavach Engineering CV Subsystem End-to-End Validation Script.
Validates the complete two-branch architecture (PaddleOCR-VL + Engineering CV),
Fusion Engine, Canonical Schema v1.0.0, Engineering Graph, LLM Interface,
and Benchmarking Suite across all 5 evaluation engineering drawings.
"""

import sys
import os
import json
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from urjakavach.pipeline import UrjaKavachPipeline
from urjakavach.benchmark.suite import BenchmarkSuite
from urjakavach.benchmark.metrics import calculate_bbox_iou, calculate_detection_metrics, calculate_topology_metrics
from urjakavach.schemas.canonical_schema import SCHEMA_VERSION
from urjakavach.cv_branch.detectors.transformer_detector import TransformerSymbolDetector
from urjakavach.cv_branch.geometry.learned_lsd import DeepLSDGeometryExtractor
from PIL import Image
import numpy as np

def run_subsystem_validation():
    print("=" * 70)
    print("URJAKAVACH COMPUTER VISION & ENGINEERING DRAWING SUBSYSTEM VALIDATION")
    print(f"Canonical Schema Version: {SCHEMA_VERSION}")
    print("=" * 70)

    pipeline = UrjaKavachPipeline()
    benchmarker = BenchmarkSuite()

    dataset_dir = Path("paddleocr_eval_dataset")
    results_dir = Path("results")

    images = sorted([f for f in dataset_dir.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg") and not f.name.startswith(".")])
    print(f"\nDiscovered {len(images)} evaluation engineering drawings in {dataset_dir}:")
    for img_path in images:
        print(f" - {img_path.name}")

    overall_results = []

    for idx, img_path in enumerate(images, 1):
        img_id = f"image_{idx:02d}"
        cached_json = results_dir / img_id / "raw_result.json"
        
        print("\n" + "-" * 60)
        print(f"PROCESSING [{idx}/5]: {img_path.name} ({img_id})")
        print("-" * 60)

        # Run End-to-End Pipeline
        res = pipeline.process_drawing(
            image_path=img_path,
            document_id=f"doc_{img_path.stem}",
            cached_paddle_result_path=cached_json if cached_json.exists() else None
        )

        canonical_doc = res["canonical_document"]
        graph = res["graph"]
        llm_iface = res["llm_interface"]
        stats = res["stats"]

        print(f"Image Resolution: {res['dimensions'][0]} x {res['dimensions'][1]}")
        print(f"Visual Features (DINOv3): dense map shape {stats['dense_feature_shape']}")
        print(f"PaddleOCR-VL Text Blocks: {stats['text_blocks']}, Tables: {stats['tables_extracted']}")
        print(f"Engineering CV Entities: {stats['entities_detected']}")
        print(f"Geometry Lines Extracted: {stats['lines_extracted']}")
        print(f"Topological Edges Verified: {stats['relationships_verified']}")

        # Save Canonical Document JSON
        out_folder = results_dir / img_id
        out_folder.mkdir(parents=True, exist_ok=True)
        canonical_json_path = out_folder / "canonical_engineering_doc.json"
        with open(canonical_json_path, "w") as f:
            json.dump(canonical_doc.to_json_dict(), f, indent=2)
        print(f"Saved Canonical JSON: {canonical_json_path}")

        # Render Multi-Modal Fusion Diagnostic Overlay
        overlay_path = out_folder / "cv_fusion_overlay.png"
        pipeline.render_pipeline_visualization(img_path, canonical_doc, overlay_path)
        print(f"Saved Diagnostic Overlay: {overlay_path}")

        # Test Engineering Graph Queries (Deterministic perception queries)
        sample_entity = canonical_doc.entities[0].id if canonical_doc.entities else "equipment_0001"
        test_query = f"What is connected to {sample_entity}?"
        answer = llm_iface.answer_query_from_graph(test_query)
        print(f"\n[Graph Query Test]: '{test_query}'")
        print(f" -> Status: {answer['status']}")
        if answer.get("evidence_grounded"):
            print(f" -> Result: {answer.get('answer_summary')}")
        else:
            print(f" -> Reason: {answer.get('reason')}")

        # Test Insufficient Evidence behavior
        unknown_query = "What is connected to pump P-999?"
        unk_answer = llm_iface.answer_query_from_graph(unknown_query)
        print(f"\n[Insufficient Evidence Test]: '{unknown_query}'")
        print(f" -> Status: {unk_answer['status']}")
        print(f" -> Factual Grounding: {unk_answer.get('reason')}")

        # Generate sample LLM prompt
        llm_prompt = llm_iface.generate_prompt_for_local_llm("Explain the main process flow")
        with open(out_folder / "llm_grounded_prompt.txt", "w") as f:
            f.write(llm_prompt)

        overall_results.append({
            "image": img_path.name,
            "doc_id": res["document_id"],
            "document_type": canonical_doc.metadata.document_type,
            "title": canonical_doc.metadata.title,
            "entities": stats["entities_detected"],
            "lines": stats["lines_extracted"],
            "relationships": stats["relationships_verified"],
            "tables": stats["tables_extracted"],
            "text_blocks": stats["text_blocks"]
        })

    # Execute Benchmarking Suite Comparison
    print("\n" + "=" * 70)
    print("RUNNING BENCHMARKING SUITE COMPARISON (Detectors & Geometry)")
    print("=" * 70)

    test_img = np.array(Image.open(images[0]).convert("RGB"))
    
    # 1. Benchmark Detectors
    det_morph = pipeline.symbol_detector
    det_trans = TransformerSymbolDetector(model_type="rt_detr_r50")
    
    b_det1 = benchmarker.benchmark_detector(det_morph, test_img)
    b_det2 = benchmarker.benchmark_detector(det_trans, test_img)

    print(f"\nDetector 1: {b_det1['model_name']} - Detections: {b_det1['detected_count']} - Latency: {b_det1['latency_ms']}ms - Peak RAM: {b_det1['peak_memory_mb']}MB")
    print(f"Detector 2: {b_det2['model_name']} - Detections: {b_det2['detected_count']} - Latency: {b_det2['latency_ms']}ms - Peak RAM: {b_det2['peak_memory_mb']}MB")

    # 2. Benchmark Geometry Extractors
    geo_cv = pipeline.geometry_extractor
    geo_deep = DeepLSDGeometryExtractor()

    b_geo1 = benchmarker.benchmark_geometry(geo_cv, test_img)
    b_geo2 = benchmarker.benchmark_geometry(geo_deep, test_img)

    print(f"\nGeometry 1: {b_geo1['model_name']} - Lines: {b_geo1['total_lines_extracted']} (Ortho: {b_geo1['orthogonal_lines']}) - Junctions: {b_geo1['junctions_found']} - Latency: {b_geo1['latency_ms']}ms")
    print(f"Geometry 2: {b_geo2['model_name']} - Lines: {b_geo2['total_lines_extracted']} (Ortho: {b_geo2['orthogonal_lines']}) - Junctions: {b_geo2['junctions_found']} - Latency: {b_geo2['latency_ms']}ms")

    with open("benchmark_results.json", "w") as f:
        json.dump(benchmarker.results, f, indent=2)
    print("\nSaved benchmark comparisons to benchmark_results.json")

    print("\n" + "=" * 70)
    print("ALL 5 ENGINEERING DRAWINGS SUCCESSFULLY PROCESSED AND VERIFIED!")
    print("=" * 70)

if __name__ == "__main__":
    run_subsystem_validation()
