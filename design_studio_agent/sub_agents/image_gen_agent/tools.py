import os
import uuid
import logging
from datetime import datetime

import base64
from PIL import Image
from io import BytesIO
from typing import Any, Dict, Optional

from google import genai
from google.genai import types
from google.genai.types import GenerateContentConfig, Modality

from google.adk.tools import ToolContext
from google.adk.agents.callback_context import CallbackContext

from .config import IMAGE_GENERATION_TOOL_MODEL


def _init_gemini_client():
    PROJECT_ID = str(os.environ.get("GOOGLE_CLOUD_PROJECT"))

    if not PROJECT_ID:
        raise ValueError("'GOOGLE_CLOUD_PROJECT' env variable is missing.")

    LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    return client


def save_generated_image(
    image_bytes: bytes, 
    file_extension:str, 
    tool_context: ToolContext
) -> Dict[str, Any]:
    if file_extension and not file_extension.startswith("."):
        file_extension = "." + file_extension

    mime_type = f"image/{file_extension.lstrip('.')}" if file_extension else "image/png"
    filename = f"generated_image_{uuid.uuid4()}{file_extension if file_extension else '.png'}"

    artifact_version = None

    try:
        artifact_part = types.Part(
            inline_data = types.Blob(data=image_bytes, mime_type=mime_type)
        )

        artifact_version = tool_context.save_artifact(
            filename=filename,
            artifact=artifact_part
        )

        return {
            "status": "success",
            "filename": filename,
            "artifact_version": artifact_version,
            "message": "Image generated and saved as artifact."
        }

    except Exception as error:
        return {
            "status": "error",
            "error": str(error) 
        }


def generate_image_tool(description: str, tool_context: ToolContext):
    """
    Tool to generate a new image based on a text prompt and a reference image.

    This function generates a new image based on the text description and the
    reference image. It processes the base64-encoded response data and attempts 
    to convert the resulting image bytes into a PIL Image object.

    Args:
        description (str): Text description describing the desired image output.
            - Example: "Image of a shampoo bottle on a spa counter."
        tool_context (ToolContext): Tool Context

    Returns:
        dict: A dictionary containing the generation result:
            "status": str The operation status: "success", "fail", or "error.
            "message": A descriptive message indicating the operation result.
    """
    client = _init_gemini_client()

    try:
        response = client.models.generate_content(
            model=IMAGE_GENERATION_TOOL_MODEL,
            contents=description,
            config=GenerateContentConfig(
                response_modalities=[Modality.TEXT, Modality.IMAGE],
                candidate_count=1
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data:
                try:
                    image = Image.open(BytesIO((part.inline_data.data)))
                    image.save("sample.png")

                    b64 = part.inline_data.data
                    data = base64.b64decode(b64)

                    artifact_result = save_generated_image(data, ".png", tool_context)

                    if "error" in artifact_result:
                        error_message = f"Image generated. Artifact save failed.\n\nError: {artifact_result.get("error")}"

                        return {
                            "status": "error",
                            "message": error_message
                        }

                    else:
                        return artifact_result

                except Exception as error:
                    return {
                        "status": "error",
                        "message": f"Unable to save the generated image: {str(error)}"
                    }

    except Exception as error:
        return {
            "status": "error",
            "message": str(error)
        }