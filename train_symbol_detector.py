#!/usr/bin/env python3
"""
UrjaKavach Engineering Symbol Detector Training Script
Trains an industrial-grade YOLOv8m detector on the leakage-free partitioned
P&ID Symbols dataset using Apple Silicon MPS acceleration.
"""

import os
import sys
import json
import torch
from pathlib import Path
from ultralytics import YOLO

def main():
    data_yaml = Path("datasets/pid_symbols_split/data.yaml")
    if not data_yaml.exists():
        print(f"Error: {data_yaml} not found.")
        sys.exit(1)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Initializing YOLO Symbol Detector on device: {device}")

    # Use YOLOv8m (Medium, 25.9M parameters) - strong industrial candidate
    model_name = "yolov8m.pt"
    print(f"Loading pretrained backbone: {model_name}...")
    model = YOLO(model_name)

    output_dir = Path("models/symbol_detector")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Beginning training run on P&ID Symbols...")
    # Train with freeze=10 and fraction=0.15 for high efficiency on M3 Apple Silicon
    results = model.train(
        data=str(data_yaml.resolve()),
        epochs=5,
        imgsz=640,
        batch=16,
        fraction=0.15,
        cache=True,
        device=device,
        workers=0,
        freeze=10,
        deterministic=False,
        project=str(output_dir),
        name="urjakavach_yolov8m_run",
        exist_ok=True,
        save=True,
        plots=True,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        weight_decay=0.0005,
        val=True
    )

    best_weights = output_dir / "urjakavach_yolov8m_run" / "weights" / "best.pt"
    print("\nTraining completed successfully!")
    print(f"Model saved to: {best_weights}")

    # Run validation on the holdout test set (drawings 440-499)
    print("\nEvaluating on holdout test set (unseen drawings)...")
    eval_model = YOLO(str(best_weights))
    test_metrics = eval_model.val(
        data=str(data_yaml.resolve()),
        split="test",
        device=device,
        project=str(output_dir),
        name="test_evaluation",
        exist_ok=True
    )

    metrics_dict = {
        "model": "yolov8m",
        "parameters": "25.9M",
        "epochs": 5,
        "device": device,
        "test_map50": float(test_metrics.box.map50),
        "test_map50_95": float(test_metrics.box.map),
        "best_weights": str(best_weights.resolve())
    }

    with open("results/symbol_detector_metrics.json", "w") as f:
        json.dump(metrics_dict, f, indent=2)

    print(f"\nFinal Test Results:")
    print(f"  Test mAP@50:    {test_metrics.box.map50 * 100:.2f}%")
    print(f"  Test mAP@50-95: {test_metrics.box.map * 100:.2f}%")
    print(f"Saved metrics to results/symbol_detector_metrics.json")

if __name__ == "__main__":
    main()
