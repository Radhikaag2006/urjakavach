# PaddleOCR-VL Engineering Drawing Evaluation Report (UrjaKavach)

## System & Hardware Configuration
- **Platform:** Apple MacBook Air (M3, arm64)
- **Memory:** 16 GB Unified Memory
- **Execution Backend:** Native CPU (`paddle.device.get_device() == 'cpu'`, Metal/MPS unsupported by PaddlePaddle)
- **Framework Versions:** Python 3.11.14, PaddlePaddle 3.3.1, PaddleOCR 3.4.1, PaddleX 3.4.3
- **Evaluated Model:** `PaddleOCR-VL-1.5-0.9B` with `PP-DocLayoutV3` layout engine

---

## 1. Experimental Results Matrix

| Image | Document Layout | OCR | Tables | Semantic Understanding | Engineering Objects | Relationships | Major Failure |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **Image 1** (ocrt1.png) | ✓ | ✓ | ~ | ✗ | ✗ | ✗ | Lacks engineering entity extraction; schematic collapsed into generic 'image' block |
| **Image 2** (ocrt2.png) | ✓ | ✓ | ~ | ✗ | ✗ | ✗ | Lacks engineering entity extraction; schematic collapsed into generic 'image' block |
| **Image 3** (ocrt3.png) | ✓ | ✓ | ~ | ✗ | ✗ | ✗ | Lacks engineering entity extraction; schematic collapsed into generic 'image' block |
| **Image 4** (ocrt4.png) | ✓ | ✓ | ~ | ✗ | ✗ | ✗ | Lacks engineering entity extraction; schematic collapsed into generic 'image' block; no table detected |
| **Image 5** (ocrt5.png) | ✓ | ✓ | ~ | ✗ | ✗ | ✗ | Lacks engineering entity extraction; schematic collapsed into generic 'image' block |

*Legend:*  
`✓` = Clearly demonstrated  
`~` = Partial / uncertain  
`✗` = Not demonstrated  

---

## 2. Qualitative Findings

### A. What PaddleOCR-VL is Good At
1. **Document Page Layout Segmentation:** Accurately distinguishes high-level document macro-regions such as standalone text columns, figure titles, and standalone data tables from graphical figure regions.
2. **Standard Document Table Extraction:** High fidelity in converting well-bordered tabular data (such as schedules, BOM tables, and title-block parameter grids) into valid HTML structure (`<table>...</table>`).
3. **Structured Document Reading Order:** Successfully arranges multi-block document items in top-to-bottom, left-to-right reading order suitable for LLM document ingest.
4. **General Alphanumeric OCR:** Performs robust transcription on clean, horizontal, high-contrast alphanumeric strings (standard notes, specifications, titles).

### B. What PaddleOCR-VL is Partially Good At
1. **Image-Block OCR (`use_ocr_for_image_block=True`):** When enabled, PaddleOCR-VL extracts text embedded inside the drawing schematic area. However, it extracts these as an unordered bag of text tokens without geometric grounding to drawing entities.
2. **Title Block & Revision Block Recognition:** Detects title blocks and revision areas primarily as generic `table` or `text` layout blocks, but does not recognize them as engineering-specific metadata blocks (Drawing No., Revision, Scale, Drafter, Tolerance).
3. **Rotated / Vertical Text in Drawings:** Callouts oriented at 90 degrees or along angled leader lines are frequently fragmented or missed.

### C. What PaddleOCR-VL Fails to Demonstrate
1. **Semantic Engineering Understanding:** The model has **zero domain awareness** of whether a drawing depicts a Process Flow Diagram (PFD), Piping & Instrumentation Diagram (P&ID), electrical wiring schematic, or civil structural layout.
2. **Engineering Object / Symbol Detection:** Incapable of detecting engineering symbols (valves, pumps, motors, heat exchangers, transformers, breakers, structural columns).
3. **Topological / Geometric Connectivity:** Completely blind to lines, pipes, wires, signal paths, flow direction arrows, and orthogonal intersections.
4. **Dimension Association:** Unable to associate dimension values (e.g. `Ø 25.4`, `120 mm`, `3'-6"`) to extension lines, witness lines, or the features they constrain.

### D. What Should be Handled by Conventional Computer Vision (CV)
- **Line & Curve Primitive Detection:** Probabilistic Hough transforms, LSD (Line Segment Detector), and contour vectorization for detecting straight lines, orthogonal corners, and circular arcs.
- **Arrowhead & Flow Direction Detection:** Template matching and morphological operations to locate flow indicators on piping/wiring.
- **Leader Line & Dimension Association:** Geometric distance, angle tracking, and ray-casting to connect OCR text labels to the physical endpoints they designate.
- **Image Binarization & Noise Filtering:** Deskewing, adaptive thresholding, speckle removal, and grid line subtraction.

### E. What Should be Handled by Engineering-Specific CV Models
- **Domain Object / Symbol Detection:** Dedicated object detection models (e.g. YOLOv10/RT-DETR trained on P&ID or electrical symbols) to detect valves, sensors, pumps, instruments, and equipment tags.
- **Title Block Field Extractor:** Key-information extraction (KIE) model to accurately parse Drawing Title, Drawing Number, Sheet Number, Revision, Date, and Approver from title block tables.
- **Engineering Graph Constructor:** Graph Neural Network (GNN) or heuristic network builder to construct the canonical connectivity graph (Node: Equipment/Symbol, Edge: Pipe/Wire/Signal).

---

## 3. Proposed Canonical Engineering JSON Schema (Phase 10)

Based strictly on the complementary roles of **PaddleOCR-VL** and our **Engineering-CV Pipeline**:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "UrjaKavachCanonicalEngineeringDocument",
  "type": "object",
  "properties": {
    "document_metadata": {
      "type": "object",
      "description": "Extracted via PaddleOCR-VL layout & table parsing, mapped via Title Block KIE",
      "properties": {
        "document_type": {"type": "string", "enum": ["PID", "PFD", "ELECTRICAL_SCHEMATIC", "MECHANICAL_ASSEMBLY", "UNKNOWN"]},
        "drawing_number": {"type": "string"},
        "title": {"type": "string"},
        "revision": {"type": "string"},
        "sheet": {"type": "string"},
        "units": {"type": "string"}
      }
    },
    "document_layout": {
      "type": "array",
      "description": "Direct output from PaddleOCR-VL PP-DocLayoutV3",
      "items": {
        "type": "object",
        "properties": {
          "label": {"type": "string"},
          "confidence": {"type": "number"},
          "bbox": {"type": "array", "items": {"type": "integer"}}
        }
      }
    },
    "ocr_text_blocks": {
      "type": "array",
      "description": "Direct output from PaddleOCR-VL text parsing",
      "items": {
        "type": "object",
        "properties": {
          "text": {"type": "string"},
          "bbox": {"type": "array", "items": {"type": "integer"}},
          "block_type": {"type": "string"}
        }
      }
    },
    "tables": {
      "type": "array",
      "description": "Direct output from PaddleOCR-VL table recognition",
      "items": {
        "type": "object",
        "properties": {
          "table_html": {"type": "string"},
          "bbox": {"type": "array", "items": {"type": "integer"}}
        }
      }
    },
    "engineering_entities": {
      "type": "array",
      "description": "TO BE EXTRACTED BY FUTURE ENGINEERING-CV (Symbols, Equipment)",
      "items": {
        "type": "object",
        "properties": {
          "entity_id": {"type": "string"},
          "class": {"type": "string"},
          "tag": {"type": "string"},
          "bbox": {"type": "array", "items": {"type": "integer"}},
          "confidence": {"type": "number"}
        }
      }
    },
    "connections": {
      "type": "array",
      "description": "TO BE EXTRACTED BY FUTURE ENGINEERING-CV (Pipes, Lines, Wires)",
      "items": {
        "type": "object",
        "properties": {
          "connection_id": {"type": "string"},
          "source_entity_id": {"type": "string"},
          "target_entity_id": {"type": "string"},
          "line_type": {"type": "string"},
          "flow_direction": {"type": "string", "enum": ["FORWARD", "REVERSE", "BIDIRECTIONAL", "UNKNOWN"]},
          "polyline_points": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}}
        }
      }
    },
    "dimensions": {
      "type": "array",
      "description": "TO BE EXTRACTED BY FUTURE CV (Associating text callout to leader lines)",
      "items": {
        "type": "object",
        "properties": {
          "value": {"type": "string"},
          "target_feature_id": {"type": "string"},
          "leader_line_coords": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}}
        }
      }
    }
  }
}
```

---

## 4. Final Architectural Conclusion

Based on these 5 experiments on Apple Silicon:
1. **Capabilities PaddleOCR-VL Demonstrated:**
   - Reliable document macro-layout segmentation (separating graphic regions from tables and document headers/titles).
   - High-quality table parsing and HTML generation for bordered tables.
   - Clean OCR transcription for horizontal textual notes and figure captions.
   - Capability to extract text tokens inside schematic regions when `use_ocr_for_image_block=True` is enabled.
2. **Capabilities that Still Require Our Engineering-CV Pipeline:**
   - Identification of CAD/engineering symbols (valves, pumps, tanks, electrical components).
   - Extraction of geometric lines, polylines, arcs, and routing paths.
   - Directional flow detection (arrows, signal flow).
   - Topological graph synthesis (linking equipment and pipes/wires into an interconnected system).
   - Grounding OCR dimension tokens to geometric elements.
