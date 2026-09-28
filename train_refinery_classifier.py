#!/usr/bin/env python3
"""
UrjaKavach Refinery Symbol Classifier
Trains a deep convolutional neural network with Apple Silicon MPS acceleration
on the SiED (Symbols in Engineering Drawings) 39-class industrial dataset.
"""

import os
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Check device: Apple Silicon MPS or CPU
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
print(f"Using compute device: {device}")

# Output directories
os.makedirs("models/refinery_valve_classifier", exist_ok=True)
os.makedirs("results/refinery_classifier", exist_ok=True)

csv_path = "datasets/sied/Symbols_pixel.csv"
if not os.path.exists(csv_path):
    raise FileNotFoundError(f"Missing {csv_path}")

print(f"Loading {csv_path}...")
df = pd.read_csv(csv_path)
print(f"Loaded shape: {df.shape}")

# Features & Labels
X = df.iloc[:, :-1].values.astype(np.float32) / 255.0  # Normalize to [0, 1]
raw_labels = df.iloc[:, -1].astype(str).values

# Class mapping
unique_classes = sorted(list(set(raw_labels)))
num_classes = len(unique_classes)
class_to_idx = {c: i for i, c in enumerate(unique_classes)}
idx_to_class = {i: c for i, c in enumerate(unique_classes)}
y = np.array([class_to_idx[l] for l in raw_labels], dtype=np.int64)

print(f"Total instances: {len(y)}, Total unique classes: {num_classes}")

# Save class index mapping
with open("models/refinery_valve_classifier/classes.json", "w") as f:
    json.dump({
        "num_classes": num_classes,
        "class_to_idx": class_to_idx,
        "idx_to_class": idx_to_class
    }, f, indent=2)

# Compute class weights for imbalanced handling
class_counts = np.bincount(y, minlength=num_classes)
weights = len(y) / (num_classes * (class_counts + 1e-5))
weights = np.clip(weights, 0.2, 5.0)  # Bound extreme weights
class_weights_t = torch.tensor(weights, dtype=torch.float32).to(device)

# Robust partition handling rare industrial classes:
train_indices, val_indices, test_indices = [], [], []

for cls_idx in range(num_classes):
    cls_items = np.where(y == cls_idx)[0]
    np.random.seed(42)
    np.random.shuffle(cls_items)
    n = len(cls_items)
    if n >= 10:
        n_val = max(1, int(n * 0.10))
        n_test = max(1, int(n * 0.10))
        val_indices.extend(cls_items[:n_val])
        test_indices.extend(cls_items[n_val:n_val + n_test])
        train_indices.extend(cls_items[n_val + n_test:])
    elif n >= 4:
        val_indices.append(cls_items[0])
        test_indices.append(cls_items[1])
        train_indices.extend(cls_items[2:])
    elif n >= 2:
        val_indices.append(cls_items[0])
        train_indices.extend(cls_items[1:])
    else:
        # Rare singletons (Barred Tee, Ultrasonic Flow Meter) go to train
        train_indices.extend(cls_items)

train_indices = np.array(train_indices)
val_indices = np.array(val_indices)
test_indices = np.array(test_indices)

X_train, y_train = X[train_indices], y[train_indices]
X_val, y_val = X[val_indices], y[val_indices]
X_test, y_test = X[test_indices], y[test_indices]

print(f"Train samples: {len(y_train)}, Val samples: {len(y_val)}, Test samples: {len(y_test)}")

# Reshape to (N, 1, 100, 100)
X_train = X_train.reshape((-1, 1, 100, 100))
X_val = X_val.reshape((-1, 1, 100, 100))
X_test = X_test.reshape((-1, 1, 100, 100))

# PyTorch Dataset
class SymbolDataset(Dataset):
    def __init__(self, images, labels, augment=False):
        self.images = images
        self.labels = labels
        self.augment = augment

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        img = self.images[idx].copy()
        lbl = self.labels[idx]

        if self.augment:
            # Random horizontal flip
            if np.random.rand() > 0.5:
                img = np.flip(img, axis=2).copy()
            # Random 90-degree rotation (P&ID symbols appear at orthogonal angles)
            k = np.random.randint(0, 4)
            if k > 0:
                img = np.rot90(img, k, (1, 2)).copy()

        return torch.from_numpy(img), torch.tensor(lbl, dtype=torch.long)

train_ds = SymbolDataset(X_train, y_train, augment=True)
val_ds = SymbolDataset(X_val, y_val, augment=False)
test_ds = SymbolDataset(X_test, y_test, augment=False)

train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)
test_loader = DataLoader(test_ds, batch_size=64, shuffle=False)

# Deep Model Architecture
class RefinerySymbolCNN(nn.Module):
    def __init__(self, num_classes=39):
        super().__init__()
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

            # Block 4: 12x12 -> 6x6
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

    def forward(self, x):
        feat = self.features(x)
        out = self.classifier(feat)
        return out

model = RefinerySymbolCNN(num_classes=num_classes).to(device)
criterion = nn.CrossEntropyLoss(weight=class_weights_t, label_smoothing=0.05)
optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=30, eta_min=1e-5)

print("\nStarting model training...")
num_epochs = 30
history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}
best_val_acc = 0.0
best_model_path = "models/refinery_valve_classifier/best_refinery_symbol_cnn.pth"

for epoch in range(1, num_epochs + 1):
    # Train
    model.train()
    running_loss, correct, total = 0.0, 0, 0
    for imgs, targets in train_loader:
        imgs, targets = imgs.to(device), targets.to(device)
        optimizer.zero_grad()
        outputs = model(imgs)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * imgs.size(0)
        _, preds = torch.max(outputs, 1)
        correct += (preds == targets).sum().item()
        total += targets.size(0)

    scheduler.step()
    train_loss = running_loss / total
    train_acc = correct / total

    # Validation
    model.eval()
    val_loss_sum, val_correct, val_total = 0.0, 0, 0
    with torch.no_grad():
        for imgs, targets in val_loader:
            imgs, targets = imgs.to(device), targets.to(device)
            outputs = model(imgs)
            loss = criterion(outputs, targets)
            val_loss_sum += loss.item() * imgs.size(0)
            _, preds = torch.max(outputs, 1)
            val_correct += (preds == targets).sum().item()
            val_total += targets.size(0)

    val_loss = val_loss_sum / val_total
    val_acc = val_correct / val_total

    history["train_loss"].append(train_loss)
    history["val_loss"].append(val_loss)
    history["train_acc"].append(train_acc)
    history["val_acc"].append(val_acc)

    if val_acc > best_val_acc:
        best_val_acc = val_acc
        torch.save(model.state_dict(), best_model_path)
        star = " ★ (Best)"
    else:
        star = ""

    if epoch % 5 == 0 or epoch == 1 or epoch == num_epochs:
        print(f"Epoch [{epoch:02d}/{num_epochs:02d}] "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.3f} | "
              f"Val Loss: {val_loss:.4f} Acc: {val_acc:.3f}{star}")

print(f"\nTraining Complete. Best Validation Accuracy: {best_val_acc * 100:.2f}%")

# Load best checkpoint for test evaluation
print("Loading best checkpoint for holdout testing...")
model.load_state_dict(torch.load(best_model_path, map_location=device))
model.eval()

all_preds = []
all_targets = []

with torch.no_grad():
    for imgs, targets in test_loader:
        imgs = imgs.to(device)
        outputs = model(imgs)
        _, preds = torch.max(outputs, 1)
        all_preds.extend(preds.cpu().numpy())
        all_targets.extend(targets.numpy())

test_acc = accuracy_score(all_targets, all_preds)
print(f"\nHoldout Test Accuracy: {test_acc * 100:.2f}%")

# Unique target classes in test set
present_labels = sorted(list(set(all_targets).union(set(all_preds))))
target_names = [idx_to_class[i] for i in present_labels]

report = classification_report(all_targets, all_preds, labels=present_labels, target_names=target_names, zero_division=0)
print("\nClassification Report on Test Split:")
print(report)

# Save metrics
metrics_summary = {
    "num_epochs": num_epochs,
    "best_val_accuracy": float(best_val_acc),
    "test_accuracy": float(test_acc),
    "device_used": str(device),
    "total_train_samples": len(y_train),
    "total_val_samples": len(y_val),
    "total_test_samples": len(y_test)
}

with open("results/refinery_classifier/training_metrics.json", "w") as f:
    json.dump(metrics_summary, f, indent=2)

# Save plot of training curves
plt.figure(figsize=(10, 4))
plt.subplot(1, 2, 1)
plt.plot(range(1, num_epochs + 1), history["train_loss"], label="Train Loss", color="blue")
plt.plot(range(1, num_epochs + 1), history["val_loss"], label="Val Loss", color="red")
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.title("Cross-Entropy Loss")
plt.legend()
plt.grid(True, linestyle="--", alpha=0.5)

plt.subplot(1, 2, 2)
plt.plot(range(1, num_epochs + 1), history["train_acc"], label="Train Acc", color="blue")
plt.plot(range(1, num_epochs + 1), history["val_acc"], label="Val Acc", color="red")
plt.xlabel("Epoch")
plt.ylabel("Accuracy")
plt.title("Classification Accuracy")
plt.legend()
plt.grid(True, linestyle="--", alpha=0.5)

plt.tight_layout()
plt.savefig("results/refinery_classifier/loss_curves.png", dpi=200)
plt.close()
print("Saved training curves to results/refinery_classifier/loss_curves.png")
