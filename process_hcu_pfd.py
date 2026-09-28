#!/usr/bin/env python3
"""
UrjaKavach Processing & Evaluation on User-Uploaded Drawing:
HCU-PFD-001 (Hydrogenation Unit Process Flow Diagram / P&ID)
"""

import os
import sys
import time
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

from urjakavach.pipeline import UrjaKavachPipeline

def render_detection_overlay(img_bgr, entities, output_path):
    """Renders symbol detection bounding boxes and canonical taxonomy tags."""
    vis = img_bgr.copy()
    
    # Color palette by entity category
    category_colors = {
        "valve": (0, 0, 230),       # Red
        "instrument": (230, 100, 0), # Blue
        "equipment": (0, 180, 0),    # Green
        "fitting": (180, 0, 180),    # Magenta
        "flow": (0, 180, 230),       # Orange
        "line": (100, 100, 100)      # Gray
    }
    
    for ent in entities:
        b = ent.bbox
        cat = ent.entity_class
        color = category_colors.get(cat, (0, 150, 255))
        
        cv2.rectangle(vis, (b.x1, b.y1), (b.x2, b.y2), color, 2)
        
        # Label string
        label = ent.label or cat
        conf_str = f"{ent.confidence:.2f}"
        
        # If refinery CNN refined this valve
        cnn_refined = ent.attributes.get("refinery_cnn_class")
        if cnn_refined:
            tag = f"{label} [{cnn_refined}] ({conf_str})"
        else:
            tag = f"{label} ({conf_str})"
            
        (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        # Background box for text
        text_y = max(b.y1 - 4, th + 2)
        cv2.rectangle(vis, (b.x1, text_y - th - 2), (b.x1 + tw + 4, text_y + 2), color, -1)
        cv2.putText(vis, tag, (b.x1 + 2, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        
    cv2.imwrite(str(output_path), vis)
    print(f"Saved detection overlay: {output_path}")

def render_topology_overlay(img_bgr, doc, graph, output_path):
    """Renders extracted pipe lines, detected components, and verified connectivity graph."""
    vis = img_bgr.copy()
    
    # 1. Dim background slightly for high contrast
    vis = cv2.addWeighted(vis, 0.4, np.full_like(vis, 255), 0.6, 0)
    
    # 2. Draw extracted pipe line segments (Dark Cyan)
    for line in doc.lines:
        pt1 = (int(line.start.x), int(line.start.y))
        pt2 = (int(line.end.x), int(line.end.y))
        cv2.line(vis, pt1, pt2, (200, 100, 0), 2, cv2.LINE_AA)
        
    # 3. Draw entities as green nodes
    node_centers = {}
    for ent in doc.entities:
        c = ent.bbox.center
        cx, cy = int(c.x), int(c.y)
        node_centers[ent.id] = (cx, cy)
        cv2.circle(vis, (cx, cy), 6, (0, 180, 0), -1)
        cv2.circle(vis, (cx, cy), 8, (0, 100, 0), 2)
        
    # 4. Draw verified relationships (CONNECTED_TO edges in red/magenta)
    for rel in doc.relationships:
        u_id = rel.source_id
        v_id = rel.target_id
        if u_id in node_centers and v_id in node_centers:
            p1 = node_centers[u_id]
            p2 = node_centers[v_id]
            cv2.line(vis, p1, p2, (0, 0, 220), 2, cv2.LINE_AA)
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            cv2.circle(vis, mid, 3, (0, 0, 255), -1)
            
    cv2.imwrite(str(output_path), vis)
    print(f"Saved topology overlay: {output_path}")

def main():
    img_path = Path("test_images/hcu_pfd_001.png")
    out_dir = Path("results/hcu_pfd_001")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    cached_paddle = out_dir / "paddle_raw.json"
    paddle_override = None
    if not cached_paddle.exists():
        print("Note: paddle_raw.json not found yet; running CV perception with standard text stub...")
        paddle_override = {
            "width": 1024,
            "height": 682,
            "text_observations": [],
            "table_observations": [],
            "layout_boxes": []
        }
            
    print("\nInitializing UrjaKavachPipeline with trained models...")
    pipeline = UrjaKavachPipeline(min_symbol_confidence=0.18)
    
    t0 = time.time()
    result = pipeline.process_drawing(
        image_path=img_path,
        document_id="HCU-PFD-001",
        cached_paddle_result_path=cached_paddle if cached_paddle.exists() else None,
        paddle_data_override=paddle_override
    )
    proc_time = time.time() - t0
    
    doc = result["canonical_document"]
    graph = result["graph"]
    evidence = result["evidence_summary"]
    
    # Save canonical document JSON
    with open(out_dir / "canonical_document.json", "w") as f:
        f.write(doc.model_dump_json(indent=2))
        
    # Save evidence summary
    with open(out_dir / "evidence_summary.json", "w") as f:
        json.dump(evidence, f, indent=2)
        
    # Generate Visual Overlays
    img_bgr = cv2.imread(str(img_path))
    render_detection_overlay(img_bgr, doc.entities, out_dir / "detected_symbols_overlay.png")
    render_topology_overlay(img_bgr, doc, graph, out_dir / "topology_graph_overlay.png")
    
    # Print Detailed Technical Audit
    print("\n" + "=" * 70)
    print("URJAKAVACH PIPELINE AUDIT REPORT: HCU-PFD-001")
    print("=" * 70)
    print(f"Total Processing Time:       {proc_time:.2f}s")
    print(f"Image Dimensions:            {result['dimensions']}")
    print(f"Entities (Symbols) Detected: {len(doc.entities)}")
    print(f"Line Segments Extracted:     {len(doc.lines)}")
    print(f"Text Blocks Extracted:       {len(doc.text_blocks)}")
    print(f"Tables Extracted:            {len(doc.tables)}")
    print(f"Topological Relationships:   {len(doc.relationships)}")
    print(f"Graph Nodes / Edges:         {graph.graph.number_of_nodes()} / {graph.graph.number_of_edges()}")
    
    print("\n--- DETECTED ENGINEERING ENTITIES BREAKDOWN ---")
    cat_counts = {}
    for ent in doc.entities:
        cat_counts[ent.entity_class] = cat_counts.get(ent.entity_class, 0) + 1
    for cat, count in sorted(cat_counts.items()):
        print(f"  {cat.upper():<15}: {count}")
        
    print("\n--- SAMPLE DETECTED SYMBOLS ---")
    for ent in doc.entities[:12]:
        ref = f" -> {ent.attributes.get('refinery_cnn_class')}" if "refinery_cnn_class" in ent.attributes else ""
        print(f"  [{ent.entity_class}] {ent.label}{ref} (conf={ent.confidence:.2f}, bbox={ent.bbox.to_list()})")
        
    print("\n--- EXTRACTED TEXT OBSERVATIONS (SAMPLE) ---")
    for txt in doc.text_blocks[:15]:
        print(f"  {txt.text.strip():<35} (bbox={txt.bbox.to_list()})")
        
    print("\n--- EXTRACTED TITLE / METADATA ---")
    print(f"  Title:          {doc.metadata.title}")
    print(f"  Drawing Number: {doc.metadata.drawing_number}")
    print(f"  Doc Type:       {doc.metadata.document_type}")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
