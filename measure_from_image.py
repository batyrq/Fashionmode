from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
ImageSegmenter = mp.tasks.vision.ImageSegmenter
ImageSegmenterOptions = mp.tasks.vision.ImageSegmenterOptions
RunningMode = mp.tasks.vision.RunningMode

NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28


def euclid(p1, p2):
    return float(np.linalg.norm(np.array(p1, dtype=np.float32) - np.array(p2, dtype=np.float32)))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def largest_component(binary_mask: np.ndarray) -> np.ndarray:
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_mask.astype(np.uint8), connectivity=8)
    if num_labels <= 1:
        return binary_mask.astype(bool)
    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    return labels == largest_label


def clean_mask(mask: np.ndarray) -> np.ndarray:
    mask = mask.astype(np.uint8) * 255
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = largest_component(mask > 0)
    return mask.astype(bool)


def bbox_from_mask(mask: np.ndarray):
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        raise ValueError("No foreground body mask found.")
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def normalized_landmark_to_px(lm, width, height):
    x = int(round(lm.x * width))
    y = int(round(lm.y * height))
    return clamp(x, 0, width - 1), clamp(y, 0, height - 1)


def row_runs(row_mask: np.ndarray):
    xs = np.where(row_mask)[0]
    if xs.size == 0:
        return []

    runs = []
    start = xs[0]
    prev = xs[0]
    for x in xs[1:]:
        if x == prev + 1:
            prev = x
        else:
            runs.append((start, prev))
            start = x
            prev = x
    runs.append((start, prev))
    return runs


def width_at_y(mask: np.ndarray, y: int, center_x: int, band: int = 4):
    h, w = mask.shape
    rows = range(max(0, y - band), min(h, y + band + 1))

    widths = []
    best_lr = None
    best_dist = 10**9

    for r in rows:
        runs = row_runs(mask[r])
        if not runs:
            continue

        containing = [run for run in runs if run[0] <= center_x <= run[1]]
        if containing:
            run = max(containing, key=lambda t: t[1] - t[0])
        else:
            run = min(runs, key=lambda t: min(abs(center_x - t[0]), abs(center_x - t[1])))

        left, right = run
        widths.append(right - left + 1)

        dist = abs((left + right) // 2 - center_x)
        if dist < best_dist:
            best_dist = dist
            best_lr = (left, right)

    if not widths or best_lr is None:
        return None, None

    return float(np.median(widths)), best_lr


def draw_measure_line(img, y, left, right, color=(0, 255, 0), label=None):
    cv2.line(img, (left, y), (right, y), color, 2)
    cv2.circle(img, (left, y), 4, color, -1)
    cv2.circle(img, (right, y), 4, color, -1)
    if label:
        cv2.putText(img, label, (left, max(20, y - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)


def detect_pose_and_mask(image_bgr: np.ndarray, pose_model_path: str, seg_model_path: str):
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)

    pose_options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=pose_model_path),
        running_mode=RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    seg_options = ImageSegmenterOptions(
        base_options=BaseOptions(model_asset_path=seg_model_path),
        running_mode=RunningMode.IMAGE,
        output_category_mask=True,
        output_confidence_masks=False,
    )

    with PoseLandmarker.create_from_options(pose_options) as pose_landmarker:
        pose_result = pose_landmarker.detect(mp_image)

    with ImageSegmenter.create_from_options(seg_options) as segmenter:
        seg_result = segmenter.segment(mp_image)

    if not pose_result.pose_landmarks:
        raise ValueError("No pose detected.")
    if seg_result.category_mask is None:
        raise ValueError("No category mask returned by segmenter.")

    category_mask = seg_result.category_mask.numpy_view()
    if category_mask.shape[:2] != image_bgr.shape[:2]:
        category_mask = cv2.resize(
            category_mask.astype(np.uint8),
            (image_bgr.shape[1], image_bgr.shape[0]),
            interpolation=cv2.INTER_NEAREST
        )

    body_mask = clean_mask(category_mask > 0)
    return pose_result.pose_landmarks[0], body_mask


def score_to_size(value, thresholds):
    sizes = ["XS", "S", "M", "L", "XL", "XXL"]
    idx = 0
    while idx < len(thresholds) and value >= thresholds[idx]:
        idx += 1
    return sizes[idx]


def top2_sizes_from_scores(scores):
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ordered[:2]


def recommend_size(measurements):
    h = measurements["height_input_cm"]
    chest = measurements["chest_front_width_cm"]
    waist = measurements["waist_front_width_cm"]
    hip = measurements["hip_front_width_cm"]
    shoulder = measurements["shoulder_width_cm"]
    torso = measurements["torso_length_cm"]

    chest_ratio = chest / h
    waist_ratio = waist / h
    shoulder_ratio = shoulder / h
    torso_ratio = torso / h

    # Rough buckets, meant only for coarse recommendation
    chest_size = score_to_size(chest_ratio, [0.23, 0.255, 0.28, 0.305, 0.33])
    waist_size = score_to_size(waist_ratio, [0.22, 0.245, 0.27, 0.295, 0.32])
    shoulder_size = score_to_size(shoulder_ratio, [0.17, 0.185, 0.20, 0.215, 0.23])
    torso_size = score_to_size(torso_ratio, [0.255, 0.275, 0.295, 0.315, 0.335])

    scores = {s: 0.0 for s in ["XS", "S", "M", "L", "XL", "XXL"]}

    scores[chest_size] += 0.40
    scores[waist_size] += 0.20
    scores[shoulder_size] += 0.25
    scores[torso_size] += 0.15

    warnings = []

    if waist > chest * 1.08:
        warnings.append("waist estimate unusually larger than chest")
        for k in scores:
            scores[k] *= 0.88

    if hip < waist * 0.82:
        warnings.append("hip estimate unusually small relative to waist")
        for k in scores:
            scores[k] *= 0.88

    if shoulder < chest * 0.55:
        warnings.append("shoulder estimate looks narrow relative to chest")
        for k in scores:
            scores[k] *= 0.92

    top2 = top2_sizes_from_scores(scores)
    total = sum(scores.values())
    probs = []
    for size, sc in top2:
        p = 0.0 if total == 0 else sc / total
        probs.append((size, round(p, 3)))

    confidence = "high"
    if len(warnings) == 1:
        confidence = "medium"
    elif len(warnings) >= 2:
        confidence = "low"

    relaxed = top2[0][0]
    fallback = top2[1][0] if len(top2) > 1 else top2[0][0]

    return {
        "recommended_size": relaxed,
        "second_size": fallback,
        "confidence": confidence,
        "top2_probabilities": probs,
        "size_votes": {
            "from_chest": chest_size,
            "from_waist": waist_size,
            "from_shoulders": shoulder_size,
            "from_torso": torso_size,
        },
        "warnings": warnings,
    }


def measure_from_front_image(image_path: str, height_cm: float, pose_model_path: str, seg_model_path: str,
                             save_overlay_path: str | None = None):
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise ValueError(f"Could not read image: {image_path}")

    h, w = image_bgr.shape[:2]
    landmarks, body_mask = detect_pose_and_mask(image_bgr, pose_model_path, seg_model_path)

    x1, y1, x2, y2 = bbox_from_mask(body_mask)
    pixel_height = y2 - y1 + 1
    if pixel_height < 50:
        raise ValueError("Body mask too small.")

    cm_per_px = height_cm / pixel_height

    pts = {i: normalized_landmark_to_px(landmarks[i], w, h) for i in [
        NOSE,
        LEFT_SHOULDER, RIGHT_SHOULDER,
        LEFT_ELBOW, RIGHT_ELBOW,
        LEFT_WRIST, RIGHT_WRIST,
        LEFT_HIP, RIGHT_HIP,
        LEFT_KNEE, RIGHT_KNEE,
        LEFT_ANKLE, RIGHT_ANKLE
    ]}

    shoulder_mid_y = int(round((pts[LEFT_SHOULDER][1] + pts[RIGHT_SHOULDER][1]) / 2))
    hip_mid_y = int(round((pts[LEFT_HIP][1] + pts[RIGHT_HIP][1]) / 2))
    torso_h_px = max(1, hip_mid_y - shoulder_mid_y)

    chest_y = int(round(shoulder_mid_y + 0.22 * torso_h_px))
    waist_y = int(round(shoulder_mid_y + 0.68 * torso_h_px))
    hip_y = hip_mid_y
    center_x = int(round((pts[LEFT_HIP][0] + pts[RIGHT_HIP][0]) / 2))

    chest_px, chest_lr = width_at_y(body_mask, chest_y, center_x)
    waist_px, waist_lr = width_at_y(body_mask, waist_y, center_x)
    hip_px, hip_lr = width_at_y(body_mask, hip_y, center_x)

    if chest_px is None or waist_px is None or hip_px is None:
        raise ValueError("Failed to extract one or more silhouette widths.")

    shoulder_width_px = euclid(pts[LEFT_SHOULDER], pts[RIGHT_SHOULDER])

    left_sleeve_px = euclid(pts[LEFT_SHOULDER], pts[LEFT_ELBOW]) + euclid(pts[LEFT_ELBOW], pts[LEFT_WRIST])
    right_sleeve_px = euclid(pts[RIGHT_SHOULDER], pts[RIGHT_ELBOW]) + euclid(pts[RIGHT_ELBOW], pts[RIGHT_WRIST])
    sleeve_px = (left_sleeve_px + right_sleeve_px) / 2.0

    left_leg_px = euclid(pts[LEFT_HIP], pts[LEFT_KNEE]) + euclid(pts[LEFT_KNEE], pts[LEFT_ANKLE])
    right_leg_px = euclid(pts[RIGHT_HIP], pts[RIGHT_KNEE]) + euclid(pts[RIGHT_KNEE], pts[RIGHT_ANKLE])
    leg_px = (left_leg_px + right_leg_px) / 2.0

    torso_len_px = euclid(
        ((pts[LEFT_SHOULDER][0] + pts[RIGHT_SHOULDER][0]) / 2, (pts[LEFT_SHOULDER][1] + pts[RIGHT_SHOULDER][1]) / 2),
        ((pts[LEFT_HIP][0] + pts[RIGHT_HIP][0]) / 2, (pts[LEFT_HIP][1] + pts[RIGHT_HIP][1]) / 2)
    )

    results = {
        "height_input_cm": round(height_cm, 2),
        "pixel_height_used": int(pixel_height),
        "cm_per_pixel": round(cm_per_px, 5),
        "shoulder_width_cm": round(shoulder_width_px * cm_per_px, 2),
        "chest_front_width_cm": round(chest_px * cm_per_px, 2),
        "waist_front_width_cm": round(waist_px * cm_per_px, 2),
        "hip_front_width_cm": round(hip_px * cm_per_px, 2),
        "torso_length_cm": round(torso_len_px * cm_per_px, 2),
        "sleeve_length_cm": round(sleeve_px * cm_per_px, 2),
        "leg_length_cm": round(leg_px * cm_per_px, 2),
    }

    size_info = recommend_size(results)
    results["size_recommendation"] = size_info

    if save_overlay_path is not None:
        overlay = image_bgr.copy()

        cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 255, 0), 2)
        cv2.line(overlay, (center_x, y1), (center_x, y2), (100, 100, 255), 1)

        draw_measure_line(overlay, chest_y, chest_lr[0], chest_lr[1], (0, 255, 0), f"chest {results['chest_front_width_cm']} cm")
        draw_measure_line(overlay, waist_y, waist_lr[0], waist_lr[1], (0, 200, 255), f"waist {results['waist_front_width_cm']} cm")
        draw_measure_line(overlay, hip_y, hip_lr[0], hip_lr[1], (255, 0, 255), f"hip {results['hip_front_width_cm']} cm")

        for _, p in pts.items():
            cv2.circle(overlay, p, 4, (0, 0, 255), -1)

        rec = results["size_recommendation"]
        txt1 = f"size: {rec['recommended_size']} / {rec['second_size']}"
        txt2 = f"confidence: {rec['confidence']}"

        cv2.putText(overlay, txt1, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(overlay, txt2, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.imwrite(save_overlay_path, overlay)

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--height_cm", required=True, type=float)
    parser.add_argument("--pose_model", required=True)
    parser.add_argument("--seg_model", required=True)
    parser.add_argument("--overlay_out", default="overlay_measurements.jpg")
    args = parser.parse_args()

    results = measure_from_front_image(
        image_path=args.image,
        height_cm=args.height_cm,
        pose_model_path=args.pose_model,
        seg_model_path=args.seg_model,
        save_overlay_path=args.overlay_out,
    )

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
