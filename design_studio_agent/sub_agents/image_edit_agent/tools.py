import os
from PIL import Image
import io
import json
import base64
import logging
import requests
import numpy as np
from dotenv import load_dotenv
import traceback
from datetime import datetime, timedelta

from google import genai
from google.adk.tools import ToolContext
from google.cloud import storage
import google.genai.types as types

from .utils import change_image_background

load_dotenv()


client = genai.Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
)


async def change_background_fast_tool(
    tool_context: ToolContext,
    description: str,
    image_artifact_id: str,
    aspect_ratio: str,
    sample_count: int = 1
):
    """
    Tool for changing the background based on a user-provided description, 
    while strictly preserving the integrity of the reference product itself.

    This tool is optimized for product photography editing. It loads a 
    single reference product image, crafts a specific set of instructions to 
    ensure the external model *only* alters the background, sets the aspect 
    ratio and then sends the request synchronously to the Imagen API. The 
    generated images are then decoded and saved back to the artifact store. The 
    tools returns the artifact Id of the edited image.

    Args:
        tool_context: The execution context, which provides asynchronous methods 
                      for loading input artifacts and saving output artifacts.
        description (str): The user's natural language prompt detailing the 
                           desired new background, scene, or environment (e.g., 
                           "on a snowy mountain peak at sunset").
        image_artifact_id (str): The unique ID or filename of the reference 
                                 product image artifact to be used as input.
        aspect_ratio (str): The aspect ratio for the generated output image.
                             Supported values are: "1:1", "4:3", "3:4", "9:16", 
                             and "16:9".
        sample_count (int): The number of images to generate. Default is 1.

    Returns:
        dict: A structured dictionary reporting the tool's execution result:
            - "status" (str): "success" or "error".
            - "tool_response_artifact_ids" (str): Comma-separated list of IDs for 
              the newly generated image artifacts, if successful.
            - "tool_input_artifact_id" (str): The ID of the original input image.
            - "used_prompt" (str): The final, augmented prompt sent to the API, 
              including critical preservation instructions.
            - "message" (str): A human-readable status or error message.
    """
    try:
        if not image_artifact_id:
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_ids": "",
                "used_prompt": description,
                "message": "No reference image provided. Please provide a reference image to change the background of.",
            }

        logging.info("... Attempting to load the image artifact")

        image_artifact = await tool_context.load_artifact(filename=image_artifact_id)

        logging.info(">>> Image artifact loaded successfully")

        if image_artifact is None:
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_ids": "",
                "used_prompt": description,
                "message": f"Artifact {image_artifact_id} not found",
            }

        change_background_prompt = (
            f"USER PROMPT: {description}.\n\n---\n"
            "**CRITICAL INSTRUCTION: YOU MUST PRESERVE THE REFERENCE PRODUCT.**\n"
            "1.  **DO NOT ALTER THE PRODUCT:** The reference product (bottle, jar, etc.) must be used *exactly* as-is.\n"
            "2.  **PRESERVE ALL TEXT:** All text, logos, and branding on the reference product must be preserved perfectly. Do not regenerate, misspell, or change any text.\n"
            "3.  **PRESERVE APPEARANCE:** The product's shape, color, design, and label must remain identical to the reference image.\n"
            "4.  **ONLY CHANGE THE BACKGROUND/SCENE:** Your only task is to place the *unaltered* product into the new scene described in the user prompt."
        )

        logging.info(f"... Calling the imagen API. B64 img: {image_artifact.inline_data.data[:10]}...")

        base64_img_string = base64.b64encode(image_artifact.inline_data.data).decode('utf-8')

        supported_aspect_ratios = ["1:1", "4:3", "3:4", "9:16", "16:9"]
        aspect_ratio = aspect_ratio if aspect_ratio in supported_aspect_ratios else "1:1"

        if not sample_count:
            sample_count = 1
        elif sample_count > 4:
            sample_count = 4
        else:
            sample_count = int(sample_count)

        response = change_image_background(
            prompt=change_background_prompt,
            negativePrompt = "Dark colors",
            mode = "backgroundEditing",
            base64_encoded_image = base64_img_string,
            sampleImageSize = 1024,
            sampleCount = sample_count,
            guidanceScale = "14",
            seed = 257,
            isProductImage = True,
            disablePersonFace = True,
            aspect_ratio = aspect_ratio,
            author_func = "change_background_fast_tool"
        )

        logging.info(">>> Imagen API returned response successfully")

        json_response = json.loads(response.text)

        try:
            logging.info(f"Imagen Response Keys: {json_response.keys()}")
        except: pass

        if 'error' in list(json_response.keys()):
            return {
                "status": "error",
                "message": f"An error occured: {json_response['error']}",
            }

        predictions = json_response['predictions']

        logging.info(f">>> Predictions Response: {predictions[0]['bytesBase64Encoded'][:10]}...")

        artifact_ids = []

        logging.info("... Looking for edited image")

        if predictions:
            for index, key in enumerate(predictions):
                artifact_id = f"edited_img_bkg_{tool_context.function_call_id}_{index}.png"

                generated_image_artifact = types.Part.from_bytes(
                    data=predictions[index]['bytesBase64Encoded'],
                    mime_type="image/png"
                )
                # io.BytesIO(base64.b64decode())

                await tool_context.save_artifact(
                    filename=artifact_id, 
                    artifact=generated_image_artifact
                )

                logging.info(f"...  Edited image with id {artifact_id} saved to artifact store")

                artifact_ids.append(artifact_id)

            return {
                "status": "success",
                "tool_response_artifact_ids": ", ".join(artifact_ids) if artifact_ids else "",
                "tool_input_artifact_id": image_artifact_id,
                "used_prompt": change_background_prompt,
                "message": f"Input image updated successfully.",
            }

        else:
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": image_artifact_id,
                "used_prompt": change_background_prompt,
                "message": f"No images generated",
            }

    except Exception as e:
        traceback_str = traceback.format_exc()
        logging.error(f"Critical error in change_background_tool:\n{traceback_str}")

        return {
            "status": "error",
            "tool_response_artifact_id": "",
            "tool_input_artifact_ids": image_artifact_id,
            "used_prompt": description,
            "message": f"Error generating image: {str(e)}",
            "traceback_details": traceback_str 
        }


async def change_background_capability_tool(
    tool_context: ToolContext,
    description: str,
    image_artifact_id: str,
    sample_count: int = 1
):
    """
    Tool for changing the background based on a user-provided description, 
    while strictly preserving the integrity of the reference product itself.

    This tool is optimized for product photography editing. It loads a 
    single reference product image, crafts a specific set of instructions to 
    ensure the external model *only* alters the background, and then sends the 
    request synchronously to the Imagen API. The generated images are then 
    decoded and saved back to the artifact store. The tools returns the 
    artifact Id of the edited image.

    Args:
        tool_context: The execution context, which provides asynchronous methods 
                      for loading input artifacts and saving output artifacts.
        description (str): The user's natural language prompt detailing the 
                           desired new background, scene, or environment (e.g., 
                           "on a snowy mountain peak at sunset").
        image_artifact_id (str): The unique ID or filename of the reference 
                                 product image artifact to be used as input.
        sample_count (int): The number of images to generate. Default is 1.

    Returns:
        dict: A structured dictionary reporting the tool's execution result:
            - "status" (str): "success" or "error".
            - "tool_response_artifact_ids" (str): Comma-separated list of IDs for 
              the newly generated image artifacts, if successful.
            - "tool_input_artifact_id" (str): The ID of the original input image.
            - "used_prompt" (str): The final, augmented prompt sent to the API, 
              including critical preservation instructions.
            - "message" (str): A human-readable status or error message.
    """
    try:
        if not image_artifact_id:
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_ids": "",
                "used_prompt": description,
                "message": "No reference image provided. Please provide a reference image to change the background of.",
            }

        logging.info("... Attempting to load the image artifact")

        image_artifact = await tool_context.load_artifact(filename=image_artifact_id)

        logging.info(">>> Image artifact loaded successfully")

        if image_artifact is None:
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_ids": "",
                "used_prompt": description,
                "message": f"Artifact {image_artifact_id} not found",
            }

        change_background_prompt = (
            f"USER PROMPT: {description}.\n\n---\n"
            "**CRITICAL INSTRUCTION: YOU MUST PRESERVE THE REFERENCE PRODUCT.**\n"
            "1.  **DO NOT ALTER THE PRODUCT:** The reference product (bottle, jar, etc.) must be used *exactly* as-is.\n"
            "2.  **PRESERVE ALL TEXT:** All text, logos, and branding on the reference product must be preserved perfectly. Do not regenerate, misspell, or change any text.\n"
            "3.  **PRESERVE APPEARANCE:** The product's shape, color, design, and label must remain identical to the reference image.\n"
            "4.  **ONLY CHANGE THE BACKGROUND/SCENE:** Your only task is to place the *unaltered* product into the new scene described in the user prompt."
        )

        logging.info(f"... Calling the imagen API. B64 img: {image_artifact.inline_data.data[:10]}...")

        base64_img_string = base64.b64encode(image_artifact.inline_data.data).decode('utf-8')

        if not sample_count:
            sample_count = 1
        elif sample_count > 4:
            sample_count = 4
        else:
            sample_count = int(sample_count)

        response = change_image_background(
            prompt=change_background_prompt,
            negativePrompt = "Dark colors",
            mode = "backgroundEditing",
            base64_encoded_image = base64_img_string,
            sampleImageSize = 1024,
            sampleCount = sample_count,
            guidanceScale = "14",
            seed = 257,
            isProductImage = True,
            disablePersonFace = True,
            aspect_ratio="1:1",
            author_func = "change_background_capability_tool"
        )

        logging.info(">>> Imagen API returned response successfully")

        json_response = json.loads(response.text)

        try:
            logging.info(f"Imagen Response Keys: {json_response.keys()}")
        except: pass

        if 'error' in list(json_response.keys()):
            return {
                "status": "error",
                "message": f"An error occured: {json_response['error']}",
            }

        predictions = json_response['predictions']

        logging.info(f">>> Predictions Response: {predictions[0]['bytesBase64Encoded'][:10]}...")

        artifact_ids = []

        logging.info("... Looking for edited image")

        if predictions:
            for index, key in enumerate(predictions):
                artifact_id = f"edited_img_bkg_{tool_context.function_call_id}_{index}.png"

                generated_image_artifact = types.Part.from_bytes(
                    data=predictions[index]['bytesBase64Encoded'],
                    mime_type="image/png"
                )
                # io.BytesIO(base64.b64decode())

                await tool_context.save_artifact(
                    filename=artifact_id, 
                    artifact=generated_image_artifact
                )

                logging.info(f"...  Edited image with id {artifact_id} saved to artifact store")

                artifact_ids.append(artifact_id)

            return {
                "status": "success",
                "tool_response_artifact_ids": ", ".join(artifact_ids) if artifact_ids else "",
                "tool_input_artifact_id": image_artifact_id,
                "used_prompt": change_background_prompt,
                "message": f"Input image updated successfully.",
            }

        else:
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": image_artifact_id,
                "used_prompt": change_background_prompt,
                "message": f"No images generated",
            }

    except Exception as e:
        traceback_str = traceback.format_exc()
        logging.error(f"Critical error in change_background_tool:\n{traceback_str}")

        return {
            "status": "error",
            "tool_response_artifact_id": "",
            "tool_input_artifact_ids": image_artifact_id,
            "used_prompt": description,
            "message": f"Error generating image: {str(e)}",
            "traceback_details": traceback_str 
        }


