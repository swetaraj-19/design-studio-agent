import os
import json
import logging
import requests
import warnings
import subprocess
from dotenv import load_dotenv

import google.auth
import google.auth.transport.requests

from .config import ( 
    IMAGE_BACKGROUND_FAST_TOOL_MODEL,
    IMAGE_BACKGROUND_CAPABILITY_TOOL_MODEL
)

load_dotenv()
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")


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
    logger.info("Image background function called by author: %s", author_func)

    PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
    REGION = os.getenv("GOOGLE_CLOUD_LOCATION")

    if not PROJECT_ID or not REGION:
        logger.critical("PROJECT ID or REGION not found in .env file.")
        raise ValueError("PROJECT ID or REGION not found in .env file")
    
    logger.debug("Using Project ID: %s and Region: %s", PROJECT_ID, REGION)

    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        logger.debug("Attempting to get default credentials with scopes: %s", scopes)
        credentials, project_id = google.auth.default(scopes=scopes)

        request = google.auth.transport.requests.Request()
        credentials.refresh(request)

        acess_token = credentials.token
        logger.info("Successfully refreshed Google Access Token.")

    except Exception as error:
        logger.critical(
            "Failed to obtain/refresh Google Cloud credentials. Check IAM/authentication setup. Error: %s", 
            error, 
            exc_info=True
        )
        raise RuntimeError("Authentication failed for Google Cloud API.") from error

    if author_func == "change_background_fast_tool":
        IMAGEN_MODEL = IMAGE_BACKGROUND_FAST_TOOL_MODEL
        ENDPOINT_URL = f"projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/{IMAGEN_MODEL}"

        logger.info("Using FAST tool model: %s", IMAGEN_MODEL)

        headers = {
            'Authorization': f'Bearer {acess_token}',
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

        logger.debug(
            "Fast Tool Parameters: aspectRatio=%s, sampleCount=%d",
            aspect_ratio,
            sampleCount
        )

        if disablePersonFace:
            data["parameters"]["disablePersonFace"] = disablePersonFace
            logger.debug("Parameter 'disablePersonFace' set to True.")

    else:
        IMAGEN_MODEL = IMAGE_BACKGROUND_CAPABILITY_TOOL_MODEL
        ENDPOINT_URL = f"projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/{IMAGEN_MODEL}"

        logger.info("Using CAPABILITY tool model: %s", IMAGEN_MODEL)

        headers = {
            'Authorization': f'Bearer {acess_token}',
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
                            "maskClasses": [115]
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

        logger.debug(
            "Capability Tool Parameters: editMode=%s, guidanceScale=%d, sampleCount=%d",
            data["parameters"]["editMode"],
            guidanceScale,
            sampleCount
        )

    if seed:
        data["parameters"]["seed"] = seed
        logger.debug("Adding seed: %d", seed)

    if negativePrompt:
        data["parameters"]["negativePrompt"] = negativePrompt
        logger.debug("Adding negative prompt: %s", str(negativePrompt))

    try:
        response = requests.post(
            f'https://{REGION}-aiplatform.googleapis.com/v1/{ENDPOINT_URL}:predict', 
            data=json.dumps(data), 
            headers=headers
        )

        logger.info(
            "Imagen API call finished. Status Code: %d", 
            response.status_code
        )
        logger.debug("Response text start: %s", response.text[:200])

        return response
    
    except requests.exceptions.RequestException as error:
        logger.error(
            "Network/Request error during POST to Imagen API: %s", 
            error, 
            exc_info=True
        )
        raise
