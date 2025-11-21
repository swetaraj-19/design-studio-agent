import os
import json
import requests
import subprocess

import google.auth
import google.auth.transport.requests

from .config import IMAGE_BACKGROUND_CAPABILITY_TOOL_MODEL, IMAGE_BACKGROUND_FAST_TOOL_MODEL


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
    disablePersonFace: bool,
    aspect_ratio: str,
    author_func: str = "change_background_fast_tool"
):
    PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
    REGION = os.getenv("GOOGLE_CLOUD_LOCATION")

    if not PROJECT_ID or not REGION:
        raise ValueError("PROJECT ID or REGION not found in .env file")

    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials, project_id = google.auth.default(scopes=scopes)

    request = google.auth.transport.requests.Request()
    credentials.refresh(request)

    ACCESS_TOKEN = credentials.token

    if author_func == "change_background_fast_tool":
        IMAGEN_MODEL = IMAGE_BACKGROUND_FAST_TOOL_MODEL

        ENDPOINT_URL = f"projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/{IMAGEN_MODEL}"

        #result = subprocess.run(
        #    ['gcloud', 'auth', 'print-access-token'],
        #    capture_output=True,
        #    text=True,
        #    check=True
        #)
        
        #ACCESS_TOKEN = result.stdout.strip()

        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Content-Type': 'application/json; charset=UTF-8'
        }

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
                    "aspectRatio": aspect_ratio,
                    "IsProductImage": isProductImage,
                    "mode": mode,
                    "sampleImageSize": sampleImageSize,
                    "sampleCount": sampleCount,
                    "guidanceScale":15
                }
        }

        if disablePersonFace:
            data["parameters"]["disablePersonFace"] = disablePersonFace

    else:
        IMAGEN_MODEL = IMAGE_BACKGROUND_CAPABILITY_TOOL_MODEL

        ENDPOINT_URL = f"projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/{IMAGEN_MODEL}"

        #result = subprocess.run(
        #    ['gcloud', 'auth', 'print-access-token'],
        #    capture_output=True,
        #    text=True,
        #    check=True
        #)

        #ACCESS_TOKEN = result.stdout.strip()

        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Content-Type': 'application/json; charset=UTF-8'
        }

        data = {
            "instances": [
                {
                "prompt": prompt,
                "referenceImages": [
                    {
                        "referenceType": "REFERENCE_TYPE_RAW",
                        "referenceId": 1,
                        "referenceImage": {
                            "bytesBase64Encoded": base64_encoded_image
                        }
                    },
                    {
                        "referenceType": "REFERENCE_TYPE_MASK",
                        "referenceId": 2,
                        "referenceImage": {
                            "bytesBase64Encoded": base64_encoded_image
                        },
                        "maskImageConfig": {
                            "maskMode": "MASK_MODE_BACKGROUND",
                            "dilation": 0.0,
                            "maskClasses": [115]  # masks "bottle". ref: Imagen REST API > Edit Images > Class Ids
                        }
                    }
                ]
                }
            ],
            "parameters": {
                "editConfig": {
                    "baseSteps": 65
                },
                "editMode": "EDIT_MODE_BGSWAP",
                "sampleCount": sampleCount,
                "guidanceScale": guidanceScale,
                "personGeneration": "allow_all",
            }
        }

    if seed:
        data["parameters"]["seed"] = seed
    if negativePrompt:
        data["parameters"]["negativePrompt"] = negativePrompt

    response = requests.post(
        f'https://{REGION}-aiplatform.googleapis.com/v1/{ENDPOINT_URL}:predict', 
        data=json.dumps(data), 
        headers=headers
    )

    return response
