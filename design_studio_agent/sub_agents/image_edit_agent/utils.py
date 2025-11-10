import requests
import json
import os
import subprocess

from .config import IMAGE_BACKGROUND_TOOL_MODEL

def change_image_background(
    prompt: str,
    negativePrompt: str,
    mode: str,
    base64_encoded_image: str,
    sampleImageSize: int,
    sampleCount: int,
    guidanceScale: int,
    seed: int,
    isProductImage: bool,
    disablePersonFace: bool):
    PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
    REGION = os.getenv("GOOGLE_CLOUD_LOCATION")

    if not PROJECT_ID or not REGION:
        raise ValueError("PROJECT ID or REGION not found in .env file")

    ENDPOINT_URL = f"projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/{IMAGE_BACKGROUND_TOOL_MODEL}"

    result = subprocess.run(
        ['gcloud', 'auth', 'print-access-token'],
        capture_output=True,
        text=True,
        check=True
    )

    ACCESS_TOKEN = result.stdout.strip()

    headers = {
      'Authorization': f'Bearer {ACCESS_TOKEN}',
      'Content-Type': 'application/json; charset=UTF-8'
    }
    # "x-goog-api-key: $GEMINI_API_KEY"

    data = {
        "instances":
        [
            {
                "prompt": prompt,
                "image": {
                    "bytesBase64Encoded": base64_encoded_image
                }
            }
        ],
        "parameters":
            {
                "IsProductImage": isProductImage,
                "mode": mode,
                "sampleImageSize": sampleImageSize,
                "sampleCount": sampleCount,
                "guidanceScale":15
            }
    }

    if seed:
        data["parameters"]["seed"] = seed
    if negativePrompt:
        data["parameters"]["negativePrompt"] = negativePrompt
    if disablePersonFace:
        data["parameters"]["disablePersonFace"] = disablePersonFace

    response = requests.post(
        f'https://{REGION}-aiplatform.googleapis.com/v1/{ENDPOINT_URL}:predict', 
        data=json.dumps(data), 
        headers=headers
    )

    return response
