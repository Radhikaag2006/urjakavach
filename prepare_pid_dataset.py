#!/usr/bin/env python3
"""
Prepares the P&ID Symbols dataset with a strict, leakage-free whole-drawing partition.
Drawings 0-379 -> Train
Drawings 380-439 -> Validation
Drawings 440-499 -> Test
"""

import os
import sys
import zipfile
import shutil
from pathlib import Path

images_zip = "/tmp/images.zip"
labels_zip = "/tmp/pid_labels.zip"
out_dir = Path("datasets/pid_symbols_split")

if not os.path.exists(images_zip):
    print(f"Waiting for {images_zip} to finish downloading...")
    sys.exit(1)

if not os.path.exists(labels_zip):
    print(f"Missing {labels_zip}")
    sys.exit(1)

print("Setting up directory structure...")
for split in ["train", "val", "test"]:
    (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
    (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

# Determine partition based on drawing ID (0 to 499)
def get_split(drawing_id_str):
    try:
        did = int(drawing_id_str)
    except ValueError:
        did = hash(drawing_id_str) % 500
    if did < 380:
        return "train"
    elif did < 440:
        return "val"
    else:
        return "test"

print("Reading and partitioning labels...")
label_zf = zipfile.ZipFile(labels_zip)
label_names = [n for n in label_zf.namelist() if n.endswith('.txt')]

label_counts = {"train": 0, "val": 0, "test": 0}
for name in label_names:
    drawing_id = name.split('_')[0]
    split = get_split(drawing_id)
    content = label_zf.read(name)
    target_path = out_dir / "labels" / split / name
    with open(target_path, "wb") as f:
        f.write(content)
    label_counts[split] += 1

print(f"Labels extracted: {label_counts}")

print("Extracting images into drawing-partitioned splits...")
img_zf = zipfile.ZipFile(images_zip)
img_names = [n for n in img_zf.namelist() if n.lower().endswith(('.jpg', '.jpeg', '.png'))]

img_counts = {"train": 0, "val": 0, "test": 0}
for i, name in enumerate(img_names):
    # Some zips have subfolder prefix like 'images/...'
    base_name = os.path.basename(name)
    if not base_name: continue
    drawing_id = base_name.split('_')[0]
    split = get_split(drawing_id)
    content = img_zf.read(name)
    target_path = out_dir / "images" / split / base_name
    with open(target_path, "wb") as f:
        f.write(content)
    img_counts[split] += 1
    if (i + 1) % 5000 == 0:
        print(f"Extracted {i + 1}/{len(img_names)} images...")

print(f"Images extracted: {img_counts}")

# Assert zero leakage
train_drawings = set(f.name.split('_')[0] for f in (out_dir / "images" / "train").glob("*.jpg"))
val_drawings = set(f.name.split('_')[0] for f in (out_dir / "images" / "val").glob("*.jpg"))
test_drawings = set(f.name.split('_')[0] for f in (out_dir / "images" / "test").glob("*.jpg"))

overlap_tv = train_drawings.intersection(val_drawings)
overlap_tt = train_drawings.intersection(test_drawings)
overlap_vt = val_drawings.intersection(test_drawings)

assert len(overlap_tv) == 0, f"Data leakage between train and val: {overlap_tv}"
assert len(overlap_tt) == 0, f"Data leakage between train and test: {overlap_tt}"
assert len(overlap_vt) == 0, f"Data leakage between val and test: {overlap_vt}"

print(f"VERIFIED: Zero drawing-level leakage across splits!")
print(f"Unique drawings: Train={len(train_drawings)}, Val={len(val_drawings)}, Test={len(test_drawings)}")

# Write data.yaml
yaml_content = f"""# UrjaKavach P&ID Symbol Dataset Configuration
# Partition: Leakage-free whole-drawing split
path: {out_dir.resolve()}
train: images/train
val: images/val
test: images/test

names:
  0: Not_used
  1: Gate_Valve
  2: Ball_Valve
  3: Globe_valve_NO
  4: Gate_valve_NO
  5: Globe_valve_NO_alt
  6: Butterfly_valve
  7: Plug_valve
  8: Check_valve
  9: Diaphragm_valve
  10: Needle_valve
  11: Half_Filled_Gate_Valve
  12: Gate_Valve_NC
  13: Globe_valve_NC
  14: Control_Valve
  15: Rotary_Valve
  16: Ball_valve_NC
  17: Paddle_blind
  18: Spectacle_blind_Closed
  19: Spectacle_blind_Open
  20: Reducer
  21: Flange_or_Nozzle
  22: Rupture_disk
  23: Pipe_Insulation_or_Tracing
  24: Flow_Arrow
  25: sight_glass
  26: Instrument_Field
  27: Instrument_Field_alt
  28: Instrument_Panel
  29: Instrument_Aux_Panel
  30: box
  31: Instrument_Panel_alt
  32: box_alt
"""

with open(out_dir / "data.yaml", "w") as f:
    f.write(yaml_content)

print(f"Wrote {out_dir / 'data.yaml'}")
