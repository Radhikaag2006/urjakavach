"""
Refinery Symbol Convolutional Neural Network Architecture.
Deep feature extractor and classifier for 39 fine-grained industrial/refinery symbols.
"""

import json
import torch
import torch.nn as nn
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

class RefinerySymbolCNN(nn.Module):
    """
    4-Block Deep CNN with Batch Normalization, Dropout, and Adaptive Pooling.
    Trained on 39 refinery classes from SiED (Oil & Gas P&IDs).
    """

    def __init__(self, num_classes: int = 39):
        super().__init__()
        self.num_classes = num_classes
        self.features = nn.Sequential(
            # Block 1: 100x100 -> 50x50
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 2: 50x50 -> 25x25
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 3: 25x25 -> 12x12
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 4: 12x12 -> 4x4
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((4, 4))
        )

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256 * 4 * 4, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.4),
            nn.Linear(512, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.features(x)
        return self.classifier(feat)

    @classmethod
    def load_trained(
        cls,
        weights_path: str = "models/refinery_valve_classifier/best_refinery_symbol_cnn.pth",
        classes_path: str = "models/refinery_valve_classifier/classes.json",
        device: str = "cpu"
    ) -> Tuple["RefinerySymbolCNN", Dict[int, str]]:
        """Loads trained weights and returns the model and index-to-class dictionary."""
        w_path = Path(weights_path)
        c_path = Path(classes_path)
        if not w_path.exists() or not c_path.exists():
            raise FileNotFoundError(f"Missing weights ({w_path}) or classes ({c_path})")

        with open(c_path) as f:
            meta = json.load(f)

        idx_to_class = {int(k): v for k, v in meta["idx_to_class"].items()}
        model = cls(num_classes=meta["num_classes"])
        model.load_state_dict(torch.load(w_path, map_location=device))
        model.to(device)
        model.eval()
        return model, idx_to_class
