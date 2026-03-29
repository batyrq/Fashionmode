const API_BASE = "";

export async function submitTryOn({
  modelUrl = "",
  clothingUrl = "",
  modelFile = null,
  clothingFile = null,
  garmentSize,
  bodyMeasurements = null,
  pose = "full body, front view, neutral stance, arms relaxed",
  background = "minimalistic studio background",
  aspectRatio = "3:4",
}) {
  const formData = new FormData();

  if (modelUrl) formData.append("model_url", modelUrl);
  if (clothingUrl) formData.append("clothing_url", clothingUrl);
  if (modelFile) formData.append("model_file", modelFile);
  if (clothingFile) formData.append("clothing_file", clothingFile);
  formData.append("garment_size", garmentSize);
  formData.append("pose", pose);
  formData.append("background", background);
  formData.append("aspect_ratio", aspectRatio);

  if (bodyMeasurements) {
    formData.append("body_measurements", JSON.stringify(bodyMeasurements));
  }

  const response = await fetch(`${API_BASE}/api/v1/claid/try-on`, {
    method: "POST",
    body: formData,
  });

  const payload = await response.json();
  if (!response.ok || !payload.success) {
    throw new Error(payload.detail || payload.message || "Try-on failed");
  }

  return payload;
}

export function getFitWarning(payload) {
  return payload?.fit_warning || payload?.fit_analysis?.fit_warning || "";
}
