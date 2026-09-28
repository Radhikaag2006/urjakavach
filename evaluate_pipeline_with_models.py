#!/usr/bin/env python3
"""
UrjaKavach Pipeline Evaluation with Trained Models.
Executes the full perceptual and graph understanding pipeline across the
5 quarantined holdout test drawings (paddleocr_eval_dataset/ocrt1.png - ocrt5.png).
Demonstrates end-to-end performance of:
- Fine-tuned YOLOv8m Engineering Symbol Detector (32 classes, 98% mAP@50)
- Deep RefinerySymbolCNN Classifier (39 classes, 98.3% accuracy)
- SAM 3.1 Segmentation Refinement
- OpenCV Line Segment & Connectivity Topology Reconstruction
- Canonical Multi-Relational Engineering Graph Synthesis
"""

import os
import sys
import json
import time
from pathlib import Path
from PIL import Image
import numpy as np

from urjakavach.pipeline import UrjaKavachPipeline

def main():
    print("=" * 70)
    print("UrjaKavach Pipeline Evaluation with Trained Models")
    print("Quarantined Benchmark Drawings: ocrt1.png - ocrt5.png")
    print("=" * 70)

    eval_dir = Path("paddleocr_eval_dataset")
    results_dir = Path("results/pipeline_evaluation_with_trained_models")
    results_dir.mkdir(parents=True, exist_ok=True)

    images = [
        ("Image 1 (PFD Asphalt Shingle)", eval_dir / "ocrt1.png", Path("results/image_01/raw_result.json")),
        ("Image 2 (P&ID Amine Regeneration)", eval_dir / "ocrt2.png", Path("results/image_02/raw_result.json")),
        ("Image 3 (PFD Sulfur Recovery Unit)", eval_dir / "ocrt3.png", Path("results/image_03/raw_result.json")),
        ("Image 4 (P&ID High Pressure Separator)", eval_dir / "ocrt4.png", Path("results/image_04/raw_result.json")),
        ("Image 5 (P&ID Column Overhead Loop)", eval_dir / "ocrt5.png", Path("results/image_05/raw_result.json")),
    ]

    pipeline = UrjaKavachPipeline(min_symbol_confidence=0.25)
    print(f"\nActive Symbol Detector: {pipeline.symbol_detector.detector_name}")
    print(f"Refinery CNN Attached:  {pipeline.refinery_cnn is not None}")

    all_eval_results = []

    for name, img_path, raw_json in images:
        if not img_path.exists():
            print(f"Skipping {name}: {img_path} not found.")
            continue

        print(f"\nEvaluating {name}...")
        t0 = time.time()
        res = pipeline.process_drawing(
            image_path=img_path,
            document_id=f"benchmark_{img_path.stem}",
            cached_paddle_result_path=str(raw_json) if raw_json.exists() else None
        )
        elapsed = round(time.time() - t0, 3)

        doc = res["canonical_document"]
        graph = res["graph"]
        evidence = res["evidence_summary"]
        stats = res["stats"]

        entities_by_class = {}
        for ent in doc.entities:
            c = ent.entity_class
            entities_by_class[c] = entities_by_class.get(c, 0) + 1

        print(f"  Execution Time:          {elapsed}s")
        print(f"  Dimensions:              {res['dimensions']}")
        print(f"  Entities Detected:       {len(doc.entities)} ({entities_by_class})")
        print(f"  Line Segments:           {len(doc.lines)}")
        print(f"  Text Blocks (Paddle):    {len(doc.text_blocks)}")
        print(f"  Tables (Paddle):         {len(doc.tables)}")
        print(f"  Verified Relationships:  {len(doc.relationships)}")
        print(f"  Graph Nodes / Edges:     {graph.graph.number_of_nodes()} / {graph.graph.number_of_edges()}")

        summary_item = {
            "name": name,
            "filename": img_path.name,
            "dimensions": res["dimensions"],
            "execution_time_sec": elapsed,
            "entities_detected": len(doc.entities),
            "entity_breakdown": entities_by_class,
            "lines_extracted": len(doc.lines),
            "text_blocks": len(doc.text_blocks),
            "tables_extracted": len(doc.tables),
            "verified_relationships": len(doc.relationships),
            "graph_nodes": graph.graph.number_of_nodes(),
            "graph_edges": graph.graph.number_of_edges(),
            "sample_verified_connections": evidence.get("verified_connections", [])[:5]
        }
        all_eval_results.append(summary_item)

    # Save summary
    output_path = results_dir / "evaluation_summary.json"
    with open(output_path, "w") as f:
        json.dump(all_eval_results, f, indent=2)

    print("\n" + "=" * 70)
    print(f"Saved evaluation metrics to: {output_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()
