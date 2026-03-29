"""
Claid try-on prompt builder.

This module is intentionally separate from the chatbot wrapper so virtual try-on
prompt logic stays isolated from conversational outfit generation.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class ClaidTryOnPromptBuilder:
    """Build conservative, realistic prompts for Claid virtual try-on."""

    SIZE_ORDER = ["XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "ONE SIZE"]
    TOP_SIZE_CHART_CM = {
        "XXXS": {"chest_width": 38.0, "shoulder_width": 34.0, "length": 54.0},
        "XXS": {"chest_width": 40.0, "shoulder_width": 36.0, "length": 56.0},
        "XS": {"chest_width": 42.5, "shoulder_width": 38.0, "length": 58.0},
        "S": {"chest_width": 45.0, "shoulder_width": 40.0, "length": 60.0},
        "M": {"chest_width": 48.0, "shoulder_width": 42.0, "length": 62.0},
        "L": {"chest_width": 51.0, "shoulder_width": 44.0, "length": 64.0},
        "XL": {"chest_width": 54.0, "shoulder_width": 46.0, "length": 66.0},
        "XXL": {"chest_width": 57.0, "shoulder_width": 48.0, "length": 68.0},
        "XXXL": {"chest_width": 60.0, "shoulder_width": 50.0, "length": 70.0},
    }

    @staticmethod
    def _normalize_garment_analysis(garment_analysis: Dict[str, Any]) -> Dict[str, Any]:
        confidence = garment_analysis.get("confidence", {}) if isinstance(garment_analysis, dict) else {}
        dominant_colors = garment_analysis.get("dominant_colors") if isinstance(garment_analysis, dict) else None
        if not isinstance(dominant_colors, list) or not dominant_colors:
            dominant_colors = ["unknown"]

        return {
            "analysis_type": "clip",
            "summary": str(garment_analysis.get("summary") or "Unclear garment"),
            "category": str(garment_analysis.get("category") or "unknown"),
            "dominant_colors": [str(color) for color in dominant_colors[:3]],
            "pattern": str(garment_analysis.get("pattern") or "unknown"),
            "material": str(garment_analysis.get("material") or "unknown"),
            "fit": str(garment_analysis.get("fit") or "unknown"),
            "sleeve_length": str(garment_analysis.get("sleeve_length") or "unknown"),
            "seasonality": str(garment_analysis.get("seasonality") or "all-season"),
            "formality": str(garment_analysis.get("formality") or "unknown"),
            "confidence": {
                "category": float(confidence.get("category", 0.0) or 0.0),
                "colors": float(confidence.get("colors", 0.0) or 0.0),
                "pattern": float(confidence.get("pattern", 0.0) or 0.0),
                "material": float(confidence.get("material", 0.0) or 0.0),
                "fit": float(confidence.get("fit", 0.0) or 0.0),
                "sleeve_length": float(confidence.get("sleeve_length", 0.0) or 0.0),
                "seasonality": float(confidence.get("seasonality", 0.0) or 0.0),
                "formality": float(confidence.get("formality", 0.0) or 0.0),
            },
        }

    @staticmethod
    def _claid_guidance_sentence(analysis: Dict[str, Any]) -> str:
        dominant_colors = [color for color in analysis.get("dominant_colors", []) if color and color != "unknown"]
        pattern = (analysis.get("pattern") or "unknown").lower()
        sleeve_length = (analysis.get("sleeve_length") or "unknown").lower()
        category = (analysis.get("category") or "unknown").lower()
        summary = (analysis.get("summary") or "").lower()
        parts: List[str] = []

        if category == "dress":
            parts.append("replace the person's current outfit with the reference dress")
        else:
            parts.append("replace the person's current top with the reference garment")

        if analysis.get("category") and analysis.get("category") != "unknown":
            parts.append(f"keep the garment category as {analysis['category']}")
        if dominant_colors:
            parts.append(f"preserve the dominant colors {', '.join(dominant_colors[:2])}")
        if pattern in {"logo_print", "graphic_print"}:
            parts.append("remove visible text or logos and keep the shirt plain")
        elif pattern != "unknown":
            parts.append(f"preserve the {pattern.replace('_', ' ')} pattern")
        if sleeve_length == "short_sleeve":
            parts.append("make it a short sleeve t-shirt and do not keep long sleeves from the original outfit")
        elif sleeve_length == "sleeveless":
            parts.append("make it sleeveless and do not keep sleeves from the original outfit")
        elif sleeve_length == "long_sleeve":
            parts.append("keep the long sleeve length from the reference garment")
        if category == "dress":
            parts.append(
                "make the dress drape naturally with gravity, fit the body realistically, follow the waist and hips, "
                "avoid an oversized bell shape, avoid a floating hem, and keep the skirt volume believable"
            )
            parts.append("use soft fabric folds that hang from the body instead of a rigid cone, and let the skirt fall naturally")
        detail_bits: List[str] = [
            "preserve all visible garment details from the reference image",
            "do not simplify the garment into a plain t-shirt or generic top",
        ]
        if any(word in summary for word in ["polo", "collar", "button", "placket"]):
            detail_bits.append("keep the collar, placket, and buttons visible if they are present in the reference garment")
        if any(word in summary for word in ["cuff", "trim", "rib", "stitch"]):
            detail_bits.append("preserve cuffs, trim, and stitching details")
        if any(word in summary for word in ["logo", "graphic", "print", "text"]):
            detail_bits.append("keep the print or logo placement and style unless the source image is explicitly plain")
        if any(word in summary for word in ["texture", "woven", "knit", "ribbed"]):
            detail_bits.append("preserve the fabric texture and surface pattern")
        parts.extend(detail_bits)
        if analysis.get("fit") and analysis.get("fit") != "unknown":
            parts.append(f"keep the {analysis['fit']} fit")
        if analysis.get("material") and analysis.get("material") != "unknown":
            parts.append(f"retain the {analysis['material']} material look")

        if not parts:
            return "preserve the original garment exactly as visible in the reference image"

        return "; ".join(parts)

    @classmethod
    def _normalize_size(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip().upper()
        if text in cls.SIZE_ORDER:
            return text
        return None

    @classmethod
    def _size_index(cls, value: Optional[str]) -> Optional[int]:
        normalized = cls._normalize_size(value)
        if normalized is None:
            return None
        try:
            return cls.SIZE_ORDER.index(normalized)
        except ValueError:
            return None

    @classmethod
    def _estimate_garment_dimensions(cls, garment_size: Optional[str], category: str) -> Dict[str, Optional[float]]:
        size = cls._normalize_size(garment_size)
        if category not in {"top", "dress"} or size is None:
            return {"chest_width_cm": None, "shoulder_width_cm": None, "length_cm": None}

        if size == "ONE SIZE":
            return {"chest_width_cm": None, "shoulder_width_cm": None, "length_cm": None}

        chart = cls.TOP_SIZE_CHART_CM.get(size)
        if not chart:
            return {"chest_width_cm": None, "shoulder_width_cm": None, "length_cm": None}

        return {
            "chest_width_cm": float(chart["chest_width"]),
            "shoulder_width_cm": float(chart["shoulder_width"]),
            "length_cm": float(chart["length"]),
        }

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    def _estimate_fit_scale(
        self,
        garment_dimensions: Dict[str, Optional[float]],
        measurements: Dict[str, Any],
        fit_style: str = "realistic",
        size_delta: Optional[int] = None,
    ) -> float:
        body_chest = measurements.get("chest_front_width_cm")
        garment_chest = garment_dimensions.get("chest_width_cm")
        if body_chest in (None, "", 0) or garment_chest in (None, "", 0):
            return 1.0
        try:
            ratio = float(garment_chest) / float(body_chest)
        except (TypeError, ValueError, ZeroDivisionError):
            return 1.0
        ratio = self._clamp(ratio, 0.55, 1.35)

        if fit_style == "undersized":
            undersize_factor = 1.0
            if size_delta is not None:
                if size_delta <= -3:
                    undersize_factor = 0.68
                elif size_delta == -2:
                    undersize_factor = 0.74
                elif size_delta == -1:
                    undersize_factor = 0.84
            ratio *= undersize_factor
            ratio = min(ratio, 0.78)
        elif fit_style == "oversized":
            oversize_factor = 1.0
            if size_delta is not None:
                if size_delta >= 3:
                    oversize_factor = 1.20
                elif size_delta == 2:
                    oversize_factor = 1.14
                elif size_delta == 1:
                    oversize_factor = 1.08
            ratio *= oversize_factor
            ratio = max(ratio, 1.05)

        return round(self._clamp(ratio, 0.48, 1.40), 3)

    def _build_fit_analysis(
        self,
        garment_analysis: Dict[str, Any],
        fit_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        fit_context = fit_context or {}
        body_measurements = fit_context.get("body_measurements") if isinstance(fit_context, dict) else {}
        if not isinstance(body_measurements, dict):
            body_measurements = {}

        size_recommendation = body_measurements.get("size_recommendation") if isinstance(body_measurements, dict) else {}
        if not isinstance(size_recommendation, dict):
            size_recommendation = {}

        garment_size = self._normalize_size(fit_context.get("garment_size"))
        recommended_size = self._normalize_size(size_recommendation.get("recommended_size"))
        second_size = self._normalize_size(size_recommendation.get("second_size"))
        category = str(garment_analysis.get("category") or "unknown").lower()
        garment_dimensions = self._estimate_garment_dimensions(garment_size, category)

        match_state = "unknown"
        size_delta: Optional[int] = None
        fit_note = "use a realistic fit"
        fit_style = "realistic"
        fit_warning = "Fit should be close to the reference garment photo."

        garment_idx = self._size_index(garment_size)
        recommended_idx = self._size_index(recommended_size)
        if garment_idx is not None and recommended_idx is not None:
            size_delta = garment_idx - recommended_idx
            if size_delta == 0:
                match_state = "true_to_size"
                fit_style = "true_to_size"
                fit_note = f"fit the body as a true-to-size {garment_size} with natural ease"
                fit_warning = "Fit should stay close to the clothing photo."
            elif size_delta > 0:
                match_state = "oversized"
                fit_style = "oversized"
                if size_delta >= 2:
                    fit_note = (
                        f"show a visibly oversized fit for size {garment_size} with clear extra room, "
                        f"loose drape, and the body not filling the garment"
                    )
                else:
                    fit_note = (
                        f"show a looser fit for size {garment_size} with visible ease around the body "
                        f"and a natural drape"
                    )
                fit_warning = "This garment may appear more oversized on the person than it looks in the reference photo."
            else:
                match_state = "undersized"
                fit_style = "undersized"
                if size_delta <= -2:
                    fit_note = (
                        f"show a visibly undersized fit for size {garment_size} with tight shoulders and chest, "
                        f"a higher hem, sleeves riding up, and clear pulling across the body"
                    )
                else:
                    fit_note = (
                        f"show a slightly undersized fit for size {garment_size} with visible tension at the shoulders, "
                        f"chest, and waist, and a shorter-looking hem"
                    )
                fit_warning = "This garment may appear more undersized on the person than it looks in the reference photo."
        elif garment_size:
            match_state = "garment_size_provided"
            fit_style = "realistic"
            fit_note = f"fit the garment size {garment_size} realistically on the body"
            fit_warning = "Fit is estimated from the selected garment size only."
        elif recommended_size:
            match_state = "body_recommended"
            fit_style = "realistic"
            fit_note = f"fit the body realistically around the recommended size {recommended_size}"
            fit_warning = "Fit is estimated from the body recommendation only."

        measurements_summary = {
            "height_input_cm": body_measurements.get("height_input_cm"),
            "shoulder_width_cm": body_measurements.get("shoulder_width_cm"),
            "chest_front_width_cm": body_measurements.get("chest_front_width_cm"),
            "waist_front_width_cm": body_measurements.get("waist_front_width_cm"),
            "hip_front_width_cm": body_measurements.get("hip_front_width_cm"),
            "torso_length_cm": body_measurements.get("torso_length_cm"),
            "sleeve_length_cm": body_measurements.get("sleeve_length_cm"),
            "leg_length_cm": body_measurements.get("leg_length_cm"),
        }

        return {
            "garment_size": garment_size,
            "garment_dimensions": garment_dimensions,
            "recommended_size": recommended_size,
            "second_size": second_size,
            "confidence": size_recommendation.get("confidence"),
            "size_delta": size_delta,
            "match_state": match_state,
            "fit_note": fit_note,
            "fit_style": fit_style,
            "fit_warning": fit_warning,
            "measurements": measurements_summary,
            "warnings": list(size_recommendation.get("warnings") or []),
            "top2_probabilities": size_recommendation.get("top2_probabilities") or [],
        }

    def build_prompt(
        self,
        garment_analysis: Dict[str, Any],
        model_context: Optional[Dict[str, Any]] = None,
        fit_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_analysis = self._normalize_garment_analysis(garment_analysis)
        fit_analysis = self._build_fit_analysis(normalized_analysis, fit_context)
        preserve_sentence = self._claid_guidance_sentence(normalized_analysis)
        aspect_ratio = str((model_context or {}).get("aspect_ratio") or "3:4")
        fit_note = fit_analysis.get("fit_note") or "use a realistic fit"
        fit_style = fit_analysis.get("fit_style") or "realistic"
        fit_warning = fit_analysis.get("fit_warning") or ""
        size_delta = fit_analysis.get("size_delta")
        measurements = fit_analysis.get("measurements") or {}
        garment_dimensions = fit_analysis.get("garment_dimensions") or {}
        fit_scale = self._estimate_fit_scale(garment_dimensions, measurements, fit_style=fit_style, size_delta=size_delta)
        measurement_bits = []
        for label, key in [
            ("shoulders", "shoulder_width_cm"),
            ("chest", "chest_front_width_cm"),
            ("waist", "waist_front_width_cm"),
            ("hips", "hip_front_width_cm"),
        ]:
            value = measurements.get(key)
            if value not in (None, "", "unknown"):
                measurement_bits.append(f"{label} {value} cm")
        measurement_clause = ""
        if measurement_bits:
            measurement_clause = "Body measurements: " + ", ".join(measurement_bits) + "."

        dimension_bits = []
        if fit_analysis.get("garment_size"):
            dimension_bits.append(f"garment size {fit_analysis['garment_size']}")
        for label, key in [
            ("chest", "chest_width_cm"),
            ("shoulders", "shoulder_width_cm"),
            ("length", "length_cm"),
        ]:
            value = garment_dimensions.get(key)
            if value not in (None, "", "unknown"):
                dimension_bits.append(f"{label} {value} cm")
        dimension_clause = ""
        if dimension_bits:
            dimension_clause = "Garment measurements: " + ", ".join(dimension_bits) + "."

        prompt = f"full body, front view, standing naturally with arms relaxed at the sides; {preserve_sentence}; {fit_note}"
        if "gravity" not in prompt.lower():
            prompt = f"{prompt}; make the garment drape naturally with gravity and fit the body realistically"
        if "exaggerated volume" not in prompt.lower():
            prompt = f"{prompt}; avoid exaggerated volume or rigid shapes"
        if fit_style == "oversized":
            prompt = (
                f"{prompt}; the garment is larger than the body recommendation, so show visible looseness and extra space; "
                f"do not make it body-hugging or stretched tight; keep room at the chest, waist, and hem"
            )
            if normalized_analysis.get("category") == "dress":
                prompt = (
                    f"{prompt}; let the skirt and waist fall with natural ease, with extra drape rather than a slim silhouette"
                )
        elif fit_style == "undersized":
            prompt = (
                f"{prompt}; the garment is smaller than the body recommendation, so do not make it fit comfortably; "
                f"show it as too small with visible pulling at the shoulders, chest, and waist, a shorter hem, sleeves that ride up, "
                f"and a tighter chest opening or collar if the garment has one; "
                f"show horizontal tension lines across the chest and placket if visible; "
                f"keep all garment construction details visible and do not convert the source garment into a plain t-shirt"
            )
            if normalized_analysis.get("category") == "top":
                prompt = (
                    f"{prompt}; keep the top visibly compressed on the torso, with the hem sitting higher than a true-to-size fit"
                )
            if normalized_analysis.get("summary"):
                prompt = (
                    f"{prompt}; preserve the garment-specific details from the reference such as collar, placket, trim, and texture"
                )
        if measurement_clause:
            prompt = f"{prompt}; {measurement_clause}"
        if dimension_clause:
            prompt = f"{prompt}; {dimension_clause}"
        if fit_style == "undersized" and garment_dimensions.get("chest_width_cm") is not None and measurements.get("chest_front_width_cm") is not None:
            chest_gap = float(measurements["chest_front_width_cm"]) - float(garment_dimensions["chest_width_cm"])
            shoulder_gap = float(measurements.get("shoulder_width_cm") or 0) - float(garment_dimensions.get("shoulder_width_cm") or 0)
            length_gap = float(measurements.get("torso_length_cm") or 0) - float(garment_dimensions.get("length_cm") or 0)
            prompt = (
                f"{prompt}; the garment chest width is about {garment_dimensions['chest_width_cm']} cm versus a body chest of {measurements['chest_front_width_cm']} cm, "
                f"so it should be visibly too small"
            )
            if shoulder_gap > 0:
                prompt = f"{prompt}; the shoulders are also smaller by about {round(shoulder_gap, 1)} cm"
            if length_gap > 0:
                prompt = f"{prompt}; the garment length is shorter than the torso by about {round(length_gap, 1)} cm"
        if normalized_analysis.get("sleeve_length") == "short_sleeve" and "short sleeve" not in prompt.lower():
            prompt = f"{prompt}; use a short sleeve t-shirt silhouette and do not keep long sleeves from the original outfit"
        elif normalized_analysis.get("sleeve_length") == "sleeveless" and "sleeveless" not in prompt.lower():
            prompt = f"{prompt}; use a sleeveless silhouette and do not keep sleeves from the original outfit"
        elif normalized_analysis.get("sleeve_length") == "long_sleeve" and "long sleeve" not in prompt.lower():
            prompt = f"{prompt}; use a long sleeve silhouette that matches the reference garment"

        return {
            "pose": prompt,
            "background": "minimalistic studio background",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio if aspect_ratio else "3:4",
            "safety_notes": [
                "preserve garment identity",
                "replace the worn top rather than recoloring the existing shirt",
                "make the garment follow realistic human anatomy and gravity",
                "avoid exaggerated volume or rigid shapes",
                "use the provided garment size and body measurements for realistic fit",
                "if the garment is larger than the body recommendation, show it as visibly loose or oversized",
                "if the garment is smaller than the body recommendation, show it as visibly undersized rather than comfortable",
                "for undersized tops, show tight shoulders, a higher hem, and tension across the chest and placket",
                "when garment measurements are smaller than body measurements, make the fit visibly too small on the body",
                "do not invent accessories",
                "do not alter silhouette or colors",
                "do not add visible text or logos unless explicitly requested",
            ],
            "analysis": normalized_analysis,
            "fit_analysis": fit_analysis,
            "fit_scale": fit_scale,
            "fit_strength": "strong" if fit_style in {"undersized", "oversized"} else "normal",
            "fit_warning": fit_warning,
        }
