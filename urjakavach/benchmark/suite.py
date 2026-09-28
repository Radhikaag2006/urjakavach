"""
UrjaKavach Model Benchmarking Suite.
Enables rigorous, quality-first comparison across Detectors, Backbones, Line Extractors,
and Topology builders with memory and latency profiling.
"""

from typing import List, Dict, Any, Optional
import time
import psutil
import os
import numpy as np

from urjakavach.cv_branch.detectors.base import BaseSymbolDetector
from urjakavach.cv_branch.geometry.base import BaseGeometryExtractor
from urjakavach.cv_branch.backbone.base import BaseVisualBackbone
from urjakavach.benchmark.metrics import calculate_detection_metrics, calculate_topology_metrics

class BenchmarkSuite:
    """Manages model comparisons without sacrificing accuracy for convenience."""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def benchmark_detector(
        self,
        detector: BaseSymbolDetector,
        image_rgb: np.ndarray,
        ground_truth_boxes: Optional[List[Dict[str, Any]]] = None,
        iterations: int = 1
    ) -> Dict[str, Any]:
        """Evaluates detection accuracy, latency, and memory."""
        proc = psutil.Process(os.getpid())
        mem_before = proc.memory_info().rss / (1024 * 1024)

        t0 = time.perf_counter()
        entities = []
        for _ in range(iterations):
            entities = detector.detect_symbols(image_rgb)
        latency_sec = (time.perf_counter() - t0) / iterations

        mem_after = proc.memory_info().rss / (1024 * 1024)

        pred_boxes = [{"bbox": e.bbox.to_list(), "class": e.entity_class} for e in entities]
        accuracy_metrics = {}
        if ground_truth_boxes:
            accuracy_metrics = calculate_detection_metrics(pred_boxes, ground_truth_boxes)

        res = {
            "component": "object_detector",
            "model_name": detector.detector_name,
            "detected_count": len(entities),
            "latency_ms": round(latency_sec * 1000, 2),
            "peak_memory_mb": round(max(mem_before, mem_after), 2),
            "accuracy": accuracy_metrics
        }
        self.results.append(res)
        return res

    def benchmark_geometry(
        self,
        extractor: BaseGeometryExtractor,
        image_rgb: np.ndarray,
        iterations: int = 1
    ) -> Dict[str, Any]:
        """Evaluates line segment and junction extraction."""
        t0 = time.perf_counter()
        lines = []
        for _ in range(iterations):
            lines = extractor.extract_lines(image_rgb)
        latency_sec = (time.perf_counter() - t0) / iterations

        junctions = extractor.find_junctions(lines)
        orthogonal_count = sum(1 for l in lines if l.is_orthogonal)

        res = {
            "component": "geometry_extractor",
            "model_name": extractor.extractor_name,
            "total_lines_extracted": len(lines),
            "orthogonal_lines": orthogonal_count,
            "junctions_found": len(junctions),
            "latency_ms": round(latency_sec * 1000, 2)
        }
        self.results.append(res)
        return res
