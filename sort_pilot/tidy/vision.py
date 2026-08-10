from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
from PIL import Image

from .types import Feature

COCO = ("person bicycle car motorcycle airplane bus train truck boat traffic_light fire_hydrant stop_sign parking_meter bench bird cat dog horse sheep cow elephant bear zebra giraffe backpack umbrella handbag tie suitcase frisbee skis snowboard sports_ball kite baseball_bat baseball_glove skateboard surfboard tennis_racket bottle wine_glass cup fork knife spoon bowl banana apple sandwich orange broccoli carrot hot_dog pizza donut cake chair couch potted_plant bed dining_table toilet tv laptop mouse remote keyboard cell_phone microwave oven toaster sink refrigerator book clock vase scissors teddy_bear hair_drier toothbrush").split()


def _iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1]); x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2-x1) * max(0, y2-y1)
    return inter / max((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter, 1e-9)


def postprocess(output: np.ndarray, conf=.15, iou=.45) -> list[dict]:
    rows = np.squeeze(output).T
    candidates = []
    for row in rows:
        cls = int(np.argmax(row[4:])); score = float(row[4+cls])
        if score < conf: continue
        cx, cy, width, height = map(float, row[:4]); box = (cx-width/2, cy-height/2, cx+width/2, cy+height/2)
        candidates.append({"class": COCO[cls], "confidence": score, "box": box})
    kept = []
    for det in sorted(candidates, key=lambda x: x["confidence"], reverse=True):
        if all(det["class"] != other["class"] or _iou(det["box"], other["box"]) <= iou for other in kept): kept.append(det)
    return kept


def derived(detections: list[dict]) -> list[Feature]:
    grouped = {}
    for det in detections: grouped.setdefault(det["class"], []).append(det)
    features = [Feature(f"obj:{name}", "obj", min(len(items), 3) * sum(x["confidence"] for x in items)/len(items)) for name, items in grouped.items()]
    top = sorted(grouped, key=lambda name: max(x["confidence"] for x in grouped[name]), reverse=True)[:5]
    for a, b in combinations(sorted(top), 2):
        features.append(Feature(f"pair:{a}+{b}", "pair", min(max(x["confidence"] for x in grouped[a]), max(x["confidence"] for x in grouped[b]))))
    people = len(grouped.get("person", [])); features.append(Feature(f"n_person:{'5+' if people >= 5 else '2-4' if people >= 2 else people}", "obj"))
    total = len(detections); features.append(Feature(f"n_objects:{'5+' if total >= 5 else total}", "obj"))
    if detections:
        largest = max((b[2]-b[0])*(b[3]-b[1]) for b in (x["box"] for x in detections)) / (640*640)
        features.append(Feature("subject:large" if largest > .4 else "subject:small", "obj"))
    return features


def infer(path: Path, model: Path) -> tuple[list[Feature], list[dict]]:
    import onnxruntime as ort
    image = Image.open(path).convert("RGB"); image.thumbnail((640, 640))
    canvas = Image.new("RGB", (640, 640), (114, 114, 114)); canvas.paste(image, ((640-image.width)//2, (640-image.height)//2))
    tensor = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
    session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    detections = postprocess(session.run(None, {session.get_inputs()[0].name: tensor})[0])
    return derived(detections), detections

