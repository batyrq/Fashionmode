from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import requests


class ClaidError(RuntimeError):
    pass


class ClaidQuotaError(ClaidError):
    pass


class ClaidTimeoutError(ClaidError):
    pass


class ClaidResponseError(ClaidError):
    pass


def _extract_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        error_message = payload.get("error_message")
        if isinstance(error_message, str) and error_message.strip():
            return error_message.strip()
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict):
                msg = first.get("msg") or first.get("message")
                if msg:
                    return str(msg)
        message = payload.get("message")
        if message:
            return str(message)
        error = payload.get("error")
        if error:
            return str(error)
        error_type = payload.get("error_type")
        if error_type:
            return f"{error_type}: {payload.get('error_message') or payload.get('message') or 'unknown error'}"
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    return "Unknown Claid API error"


@dataclass
class ClaidClient:
    api_key: str
    base_url: str = "https://api.claid.ai/v1"
    timeout_seconds: int = 45

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session = requests.Session()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def close(self) -> None:
        self.session.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        response = self.session.request(
            method,
            url,
            headers={**self.headers, **kwargs.pop("headers", {})},
            timeout=kwargs.pop("timeout", self.timeout_seconds),
            **kwargs,
        )
        return response

    def _raise_for_response(self, response: requests.Response, stage: str) -> None:
        if response.ok:
            return

        payload: Any
        try:
            payload = response.json()
        except Exception:
            payload = response.text

        message = _extract_error_message(payload)
        if response.status_code in {402, 429}:
            raise ClaidQuotaError(f"{stage} failed: {message}") from None
        raise ClaidResponseError(f"{stage} failed: {message}") from None

    def upload_image(
        self,
        image_bytes: bytes,
        filename: str,
        content_type: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Dict[str, Any]:
        upload_url = f"{self.base_url}/image/edit/upload"
        operations: Dict[str, Any] = {}
        if width and height:
            operations["resizing"] = {"width": int(width), "height": int(height)}

        files = {
            "file": (filename or "image.jpg", image_bytes, content_type or "application/octet-stream"),
        }
        data = {
            "data": json.dumps({"operations": operations}),
        }
        response = self._request("POST", upload_url, files=files, data=data)
        self._raise_for_response(response, "Claid upload")
        body = response.json()
        data = body.get("data", {})
        output = data.get("output", {})
        tmp_url = output.get("tmp_url")
        if not tmp_url:
            raise ClaidResponseError("Claid upload failed: missing temporary URL")
        return {"tmp_url": tmp_url, "raw": data}

    def create_ai_fashion_model(
        self,
        clothing_urls: Iterable[str],
        model_url: Optional[str] = None,
        pose: str = "full body, front view, neutral stance, arms relaxed",
        background: str = "minimalistic studio background",
        aspect_ratio: str = "3:4",
        number_of_images: int = 1,
    ) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/image/ai-fashion-models"
        payload: Dict[str, Any] = {
            "input": {"clothing": list(clothing_urls)},
            "options": {
                "pose": pose,
                "background": background,
                "aspect_ratio": aspect_ratio,
            },
            "output": {
                "number_of_images": max(1, min(int(number_of_images), 4)),
                "format": "png",
            },
        }
        if model_url:
            payload["input"]["model"] = model_url

        response = self._request("POST", endpoint, json=payload)
        self._raise_for_response(response, "Claid try-on request")
        body = response.json()
        data = body.get("data", {})
        result_url = data.get("result_url")
        task_id = data.get("id")
        if not result_url or task_id is None:
            raise ClaidResponseError("Claid try-on failed: missing task metadata")
        return {"task_id": task_id, "result_url": result_url, "raw": data}

    def poll_result(
        self,
        result_url: str,
        timeout_seconds: int = 90,
        interval_seconds: float = 2.0,
    ) -> Dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        last_status = "UNKNOWN"

        while True:
            response = self._request("GET", result_url)

            if response.status_code == 429:
                if time.monotonic() >= deadline:
                    raise ClaidTimeoutError(f"Timed out while polling Claid result (last status: {last_status})")
                time.sleep(interval_seconds)
                continue

            self._raise_for_response(response, "Claid result polling")
            body = response.json()
            data = body.get("data", {})
            status = data.get("status") or "UNKNOWN"
            last_status = status

            if status in {"DONE", "ERROR"}:
                return data

            if time.monotonic() >= deadline:
                raise ClaidTimeoutError(f"Timed out while polling Claid result (last status: {last_status})")

            time.sleep(interval_seconds)
