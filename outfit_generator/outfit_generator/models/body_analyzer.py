"""
Body type analysis based on MediaPipe pose landmarks.

The module is import-safe even when MediaPipe or OpenCV are missing; route code
should surface those capability gaps as explicit diagnostics instead of failing
global startup.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image
from loguru import logger

try:
    import mediapipe as mp  # type: ignore
    import cv2  # type: ignore

    mp_solutions = getattr(mp, "solutions", None)
    if mp_solutions is None:
        raise RuntimeError(
            "Installed mediapipe package does not expose mediapipe.solutions; "
            "this body-analysis flow currently depends on the legacy solutions API."
        )

    BODY_ANALYZER_RUNTIME_AVAILABLE = True
    BODY_ANALYZER_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - depends on local optional extras
    mp = None  # type: ignore
    cv2 = None  # type: ignore
    mp_solutions = None  # type: ignore
    BODY_ANALYZER_RUNTIME_AVAILABLE = False
    BODY_ANALYZER_IMPORT_ERROR = str(exc)

from config import BODY_TYPES, BODY_TYPE_RECOMMENDATIONS


class BodyTypeAnalyzer:
    """Estimate a coarse body type from a full-body photo."""

    def __init__(self):
        if not BODY_ANALYZER_RUNTIME_AVAILABLE or mp is None or cv2 is None:
            raise RuntimeError(
                f"Body analyzer runtime is unavailable: {BODY_ANALYZER_IMPORT_ERROR or 'missing MediaPipe/OpenCV'}"
            )

        self.mp_pose = mp_solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.mp_drawing = mp_solutions.drawing_utils

    def capability_status(self) -> Dict[str, Any]:
        return {
            "runtime_available": BODY_ANALYZER_RUNTIME_AVAILABLE,
            "import_error": BODY_ANALYZER_IMPORT_ERROR or None,
        }

    def extract_keypoints(self, image: Image.Image) -> Optional[Dict[str, Tuple[float, float]]]:
        try:
            image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            results = self.pose.process(image_cv)
            if not results.pose_landmarks:
                logger.warning("No pose landmarks detected")
                return None

            height, width, _ = image_cv.shape
            landmark_names = {
                "nose": 0,
                "left_shoulder": 11,
                "right_shoulder": 12,
                "left_elbow": 13,
                "right_elbow": 14,
                "left_wrist": 15,
                "right_wrist": 16,
                "left_hip": 23,
                "right_hip": 24,
                "left_knee": 25,
                "right_knee": 26,
                "left_ankle": 27,
                "right_ankle": 28,
            }

            keypoints = {}
            for name, index in landmark_names.items():
                landmark = results.pose_landmarks.landmark[index]
                keypoints[name] = (landmark.x * width, landmark.y * height)

            logger.info(f"Extracted {len(keypoints)} body keypoints")
            return keypoints
        except Exception as exc:
            logger.error(f"Body keypoint extraction error: {exc}")
            return None

    def calculate_measurements(self, keypoints: Dict[str, Tuple[float, float]]) -> Dict[str, float]:
        def distance(point_a: Tuple[float, float], point_b: Tuple[float, float]) -> float:
            return float(np.sqrt((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2))

        try:
            shoulder_width = distance(keypoints["left_shoulder"], keypoints["right_shoulder"])
            hip_width = distance(keypoints["left_hip"], keypoints["right_hip"])
            torso_length = (
                (keypoints["left_shoulder"][1] + keypoints["right_shoulder"][1]) / 2
                - (keypoints["left_hip"][1] + keypoints["right_hip"][1]) / 2
            )
            leg_length = (
                (keypoints["left_hip"][1] + keypoints["right_hip"][1]) / 2
                - (keypoints["left_ankle"][1] + keypoints["right_ankle"][1]) / 2
            )
            waist_width = hip_width * 0.85

            measurements = {
                "shoulder_width": shoulder_width,
                "hip_width": hip_width,
                "waist_width": waist_width,
                "torso_length": abs(torso_length),
                "leg_length": abs(leg_length),
                "shoulder_to_hip_ratio": shoulder_width / (hip_width + 1e-6),
                "waist_to_hip_ratio": waist_width / (hip_width + 1e-6),
                "upper_lower_ratio": abs(torso_length) / (abs(leg_length) + 1e-6),
            }
            logger.info(f"Calculated body proportions: {measurements}")
            return measurements
        except Exception as exc:
            logger.error(f"Measurement calculation error: {exc}")
            return {}

    def classify_body_type(self, measurements: Dict[str, float]) -> str:
        try:
            shoulder_to_hip = measurements.get("shoulder_to_hip_ratio", 1.0)
            waist_to_hip = measurements.get("waist_to_hip_ratio", 1.0)

            if 0.9 <= shoulder_to_hip <= 1.1 and waist_to_hip < 0.85:
                body_type = "hourglass"
            elif shoulder_to_hip < 0.9:
                body_type = "pear"
            elif shoulder_to_hip > 1.1:
                body_type = "inverted_triangle"
            elif waist_to_hip > 0.9:
                body_type = "apple"
            else:
                body_type = "rectangle"

            logger.info(f"Classified body type: {BODY_TYPES.get(body_type, body_type)}")
            return body_type
        except Exception as exc:
            logger.error(f"Body type classification error: {exc}")
            return "rectangle"

    def get_recommendations(self, body_type: str) -> Dict[str, Any]:
        recommendations = BODY_TYPE_RECOMMENDATIONS.get(body_type, BODY_TYPE_RECOMMENDATIONS["rectangle"])
        return {
            "body_type": BODY_TYPES.get(body_type, body_type),
            "body_type_code": body_type,
            "description": recommendations["description"],
            "recommended": recommendations["good"],
            "avoid": recommendations["avoid"],
        }

    def analyze_full(self, image: Image.Image) -> Dict[str, Any]:
        keypoints = self.extract_keypoints(image)
        if not keypoints:
            return {
                "success": False,
                "error": "Could not detect a body on the image",
                "recommendations": self.get_recommendations("rectangle"),
            }

        measurements = self.calculate_measurements(keypoints)
        body_type = self.classify_body_type(measurements)
        recommendations = self.get_recommendations(body_type)
        recommendations["success"] = True
        recommendations["measurements"] = measurements
        return recommendations

    def draw_pose_landmarks(self, image: Image.Image) -> Image.Image:
        image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        results = self.pose.process(image_cv)
        if results.pose_landmarks:
            self.mp_drawing.draw_landmarks(image_cv, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
        return Image.fromarray(cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB))


def get_body_analyzer_capability_status() -> Dict[str, Any]:
    return {
        "runtime_available": BODY_ANALYZER_RUNTIME_AVAILABLE,
        "import_error": BODY_ANALYZER_IMPORT_ERROR or None,
    }
