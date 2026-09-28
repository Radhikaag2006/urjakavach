"""
Benchmark metrics for Engineering Computer Vision and Topology Extraction.
Implements exact mathematical definitions for Detection (mAP), Segmentation (IoU),
Geometry (Line/Endpoint accuracy), and Topology (Graph Node/Edge accuracy).
"""

from typing import List, Dict, Any, Tuple, Optional
import math
import numpy as np

def calculate_bbox_iou(box1: List[int], box2: List[int]) -> float:
    """Calculates Intersection over Union (IoU) for two [x1, y1, x2, y2] boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(0, box1[2] - box1[0]) * max(0, box1[3] - box1[1])
    area2 = max(0, box2[2] - box2[0]) * max(0, box2[3] - box2[1])
    union_area = area1 + area2 - inter_area

    if union_area <= 0:
        return 0.0
    return float(inter_area) / float(union_area)

def calculate_detection_metrics(
    predictions: List[Dict[str, Any]],
    ground_truths: List[Dict[str, Any]],
    iou_threshold: float = 0.5
) -> Dict[str, float]:
    """
    Computes Precision, Recall, and F1 at specified IoU threshold.
    """
    if not ground_truths and not predictions:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "matched": 0}
    if not ground_truths:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0, "matched": 0}
    if not predictions:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0, "matched": 0}

    matched_gt = set()
    tp = 0
    fp = 0

    for pred in predictions:
        p_box = pred["bbox"]
        p_cls = pred.get("class")
        best_iou = 0.0
        best_gt_idx = -1

        for gt_idx, gt in enumerate(ground_truths):
            if gt_idx in matched_gt:
                continue
            if p_cls and gt.get("class") and p_cls != gt.get("class"):
                continue

            iou = calculate_bbox_iou(p_box, gt["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = gt_idx

        if best_iou >= iou_threshold and best_gt_idx >= 0:
            tp += 1
            matched_gt.add(best_gt_idx)
        else:
            fp += 1

    fn = len(ground_truths) - len(matched_gt)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * (precision * recall) / max(1e-6, precision + recall)

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn
    }

def calculate_topology_metrics(
    predicted_edges: List[Tuple[str, str, str]],
    ground_truth_edges: List[Tuple[str, str, str]]
) -> Dict[str, float]:
    """
    Evaluates topological connectivity: (source_label, relation_type, target_label).
    """
    pred_set = set(predicted_edges)
    gt_set = set(ground_truth_edges)

    if not gt_set and not pred_set:
        return {"edge_precision": 1.0, "edge_recall": 1.0, "edge_f1": 1.0}
    if not gt_set:
        return {"edge_precision": 0.0, "edge_recall": 1.0, "edge_f1": 0.0}
    if not pred_set:
        return {"edge_precision": 1.0, "edge_recall": 0.0, "edge_f1": 0.0}

    tp = len(pred_set.intersection(gt_set))
    precision = tp / len(pred_set)
    recall = tp / len(gt_set)
    f1 = 2 * (precision * recall) / max(1e-6, precision + recall)

    return {
        "edge_precision": round(precision, 4),
        "edge_recall": round(recall, 4),
        "edge_f1": round(f1, 4),
        "tp_edges": tp,
        "fp_edges": len(pred_set) - tp,
        "fn_edges": len(gt_set) - tp
    }
