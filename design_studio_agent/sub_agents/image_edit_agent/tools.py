import io
import os
import json
import base64
import logging
import requests
import warnings
import numpy as np
from PIL import Image
from dotenv import load_dotenv
from datetime import datetime, timedelta

import google.genai.types as types

from google import genai
from google.adk.tools import ToolContext
from google.cloud import storage

from .utils import change_image_background

load_dotenv()
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")


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

    NOTE: This tool should not be used for `image generation` tasks such as 
    generating new images in different styles, orientation etc. For image 
    generation tasks, delegate to `image_gen_agent`.

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
            - "tool_response_artifact_id" (str): Comma-separated list of IDs for 
              the newly generated image artifacts, if successful.
            - "tool_input_artifact_id" (str): The ID of the original input image.
            - "used_prompt" (str): The final, augmented prompt sent to the API, 
              including critical preservation instructions.
            - "message" (str): A human-readable status or error message.
    """
    logger.info(
        "Tool 'change_background_fast_tool' started. Artifact ID: %s, Samples: %d",
        image_artifact_id,
        sample_count,
    )
    logger.debug(
        "User description: '%s', Aspect Ratio: %s", 
        description, 
        aspect_ratio
    )

    try:
        if not image_artifact_id:
            logger.warning("Execution failed: No image_artifact_id provided.")

            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": "",
                "used_prompt": description,
                "message": "No reference image provided. Please provide a reference image to change the background of.",
            }

        logger.info("... Attempting to load the image artifact: %s", image_artifact_id)
        image_artifact = await tool_context.load_artifact(filename=image_artifact_id)

        if image_artifact is None:
            logger.error("Artifact %s not found in tool context.", image_artifact_id)
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": "",
                "used_prompt": description,
                "message": f"Artifact {image_artifact_id} not found",
            }

        logger.info(">>> Image artifact loaded successfully.")

        change_background_prompt = (
            f"USER PROMPT: {description}.\n\n---\n"
            "**CRITICAL INSTRUCTION: YOU MUST PRESERVE THE REFERENCE PRODUCT.**\n"
            "1.  **DO NOT ALTER THE PRODUCT:** The reference product (bottle, jar, etc.) must be used *exactly* as-is.\n"
            "2.  **PRESERVE ALL TEXT:** All text, logos, and branding on the reference product must be preserved perfectly. Do not regenerate, misspell, or change any text.\n"
            "3.  **PRESERVE APPEARANCE:** The product's shape, color, design, and label must remain identical to the reference image.\n"
            "4.  **ONLY CHANGE THE BACKGROUND/SCENE:** Your only task is to place the *unaltered* product into the new scene described in the user prompt."
        )

        logger.debug("Final augmented prompt prepared:\n%s", change_background_prompt)
        base64_img_string = base64.b64encode(image_artifact.inline_data.data).decode('utf-8')

        logger.debug(
            "Base64 encoded image data length: %d bytes. MIME type: %s", 
            len(base64_img_string),
            image_artifact.inline_data.mime_type
        )

        supported_aspect_ratios = ["1:1", "4:3", "3:4", "9:16", "16:9"]
        
        if aspect_ratio not in supported_aspect_ratios:
            logger.warning(
                "Unsupported aspect ratio '%s' received. Defaulting to '1:1'.", 
                aspect_ratio
            )
            aspect_ratio = "1:1"

        if not sample_count:
            sample_count = 1
            logger.debug("Sample count was zero, set to default 1.")
        
        elif sample_count > 4:
            logger.warning("Sample count %d exceeds maximum limit of 4. Clamping to 4.", sample_count)
            sample_count = 4
        
        else:
            sample_count = int(sample_count)

        logger.info(
            "Calling external image background editing service (Aspect: %s, Samples: %d)",
            aspect_ratio,
            sample_count
        )

        try:
            response = change_image_background(
                prompt=change_background_prompt,
                negativePrompt = "Dark colors, dark background, low res, low quality",
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
        
        except Exception as error:
            logger.error("Error calling Imagen API: %s", error, exc_info=True)
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": image_artifact_id,
                "used_prompt": description,
                "message": f"Error changing background: {str(error)}",
            }

        logging.info("Imagen API returned response.")
        json_response = json.loads(response.text)

        if 'error' in list(json_response.keys()):
            error_msg = json_response.get('error', 'Unknown API Error')
            logger.error("Imagen API execution error: %s", error_msg)

            return {
                "status": "error",
                "message": f"An error occured: {error_msg}",
            }

        predictions = json_response['predictions']

        if not predictions:
            logger.error("Imagen API succeeded but returned zero predictions.")
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": image_artifact_id,
                "used_prompt": change_background_prompt,
                "message": f"No images generated",
            }

        artifact_ids = []
        logger.info("Processing %d generated images.", len(predictions))

        for index, prediction in enumerate(predictions):
            artifact_id = f"edited_img_bkg_{tool_context.function_call_id}_{index}.png"

            base64_data = prediction.get('bytesBase64Encoded')
            if not base64_data:
                 logger.error("Prediction %d is missing 'bytesBase64Encoded' data. Skipping.", index)
                 continue

            # [FIXED] Decode base64 string to bytes before creating Artifact
            image_raw_bytes = base64.b64decode(base64_data)

            generated_image_artifact = types.Part.from_bytes(
                data=image_raw_bytes,
                mime_type="image/png"
            )

            await tool_context.save_artifact(
                filename=artifact_id, 
                artifact=generated_image_artifact
            )

            logging.info("Edited image with id %s saved to artifact store", artifact_id)
            artifact_ids.append(artifact_id)

        logger.info(
            "Successfully generated and saved %d new artifacts.", 
            len(artifact_ids)
        )

        return {
            "status": "success",
            "tool_response_artifact_id": ", ".join(artifact_ids) if artifact_ids else "",
            "tool_input_artifact_id": image_artifact_id,
            "used_prompt": change_background_prompt,
            "message": f"Input image updated successfully.",
        }

    except requests.exceptions.HTTPError as http_err:
        logger.error(
            "HTTP Error during API call: %s. Response: %s", 
            http_err, 
            http_err.response.text if http_err.response is not None else "No response",
            exc_info=True
        )

        return {
            "status": "error",
            "tool_response_artifact_id": "",
            "tool_input_artifact_id": image_artifact_id,
            "used_prompt": description,
            "message": f"HTTP Error generating image: {str(http_err)}",
        }

    except Exception as error:
        logger.error(
            "An unexpected error occurred in 'change_background_fast_tool': %s", 
            error, 
            exc_info=True
        )

        return {
            "status": "error",
            "tool_response_artifact_id": "",
            "tool_input_artifact_id": image_artifact_id,
            "used_prompt": description,
            "message": f"Error generating image: {str(error)}",
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

    NOTE: This tool should not be used for `image generation` tasks such as 
    generating new images in different styles, orientation etc. For image 
    generation tasks, delegate to `image_gen_agent`.

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
            - "tool_response_artifact_id" (str): Comma-separated list of IDs for 
              the newly generated image artifacts, if successful.
            - "tool_input_artifact_id" (str): The ID of the original input image.
            - "used_prompt" (str): The final, augmented prompt sent to the API, 
              including critical preservation instructions.
            - "message" (str): A human-readable status or error message.
    """
    logger.info(
        "Tool 'change_background_capability_tool' started. Artifact ID: %s, Samples: %d",
        image_artifact_id,
        sample_count,
    )
    logger.debug("User description: '%s'", description)

    try:
        if not image_artifact_id:
            logger.warning("Execution failed: No image_artifact_id provided.")
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": "",
                "used_prompt": description,
                "message": "No reference image provided. Please provide a reference image to change the background of.",
            }

        logger.info("... Attempting to load the image artifact: %s", image_artifact_id)
        image_artifact = await tool_context.load_artifact(filename=image_artifact_id)

        if image_artifact is None:
            logger.error("Artifact %s not found in tool context.", image_artifact_id)
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": "",
                "used_prompt": description,
                "message": f"Artifact {image_artifact_id} not found",
            }

        logger.info("Image artifact loaded successfully.")

        change_background_prompt = (
            f"USER PROMPT: {description}.\n\n---\n"
            "**CRITICAL INSTRUCTION: YOU MUST PRESERVE THE REFERENCE PRODUCT.**\n"
            "1.  **DO NOT ALTER THE PRODUCT:** The reference product (bottle, jar, etc.) must be used *exactly* as-is.\n"
            "2.  **PRESERVE ALL TEXT:** All text, logos, and branding on the reference product must be preserved perfectly. Do not regenerate, misspell, or change any text.\n"
            "3.  **PRESERVE APPEARANCE:** The product's shape, color, design, and label must remain identical to the reference image.\n"
            "4.  **ONLY CHANGE THE BACKGROUND/SCENE:** Your only task is to place the *unaltered* product into the new scene described in the user prompt."
        )

        logger.debug("Final augmented prompt prepared:\n%s", change_background_prompt)
        base64_img_string = base64.b64encode(image_artifact.inline_data.data).decode('utf-8')

        logger.debug(
            "Base64 encoded image data length: %d bytes. MIME type: %s", 
            len(base64_img_string),
            image_artifact.inline_data.mime_type
        )

        if not sample_count:
            sample_count = 1
            logger.debug("Sample count was zero, set to default 1.")
        elif sample_count > 4:
            sample_count = 4
            logger.warning("Sample count %d exceeds maximum limit of 4. Clamping to 4.", sample_count)
        else:
            sample_count = int(sample_count)

        logger.info("Calling Imagen background editing service (Samples: %d)", sample_count)

        try:
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
                author_func="change_background_capability_tool"
            )
        
        except Exception as error:
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": image_artifact_id,
                "used_prompt": description,
                "message": f"Error changing background: {str(error)}",
            }

        logging.info("Imagen API returned response successfully")
        json_response = json.loads(response.text)

        if 'error' in list(json_response.keys()):
            error_msg = json_response.get('error', 'Unknown API Error')
            logger.error("Imagen API execution error: %s", error_msg)
            return {
                "status": "error",
                "message": f"An error occured: {error_msg}",
            }

        predictions = json_response.get('predictions', [])

        if not predictions:
            logger.error("Imagen API succeeded but returned zero predictions.")
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": image_artifact_id,
                "used_prompt": change_background_prompt,
                "message": f"No images generated",
            }

        artifact_ids = []
        logger.info("Processing %d edited images.", len(predictions))

        for index, prediction in enumerate(predictions):
            artifact_id = f"edited_img_bkg_{tool_context.function_call_id}_{index}.png"

            base64_data = prediction.get('bytesBase64Encoded')
            if not base64_data:
                 logger.error("Prediction %d is missing 'bytesBase64Encoded' data. Skipping.", index)
                 continue

            # [FIXED] Decode base64 string to bytes before creating Artifact
            image_raw_bytes = base64.b64decode(base64_data)

            generated_image_artifact = types.Part.from_bytes(
                data=image_raw_bytes,
                mime_type="image/png"
            )

            await tool_context.save_artifact(
                filename=artifact_id, 
                artifact=generated_image_artifact
            )

            logger.info(
                "Edited image with id %s saved to artifact store.", 
                artifact_id
            )

            artifact_ids.append(artifact_id)
        
        logger.info(
            "Successfully edited and saved %d new artifacts.", 
            len(artifact_ids)
        )

        return {
            "status": "success",
            "tool_response_artifact_id": ", ".join(artifact_ids) if artifact_ids else "",
            "tool_input_artifact_id": image_artifact_id,
            "used_prompt": change_background_prompt,
            "message": f"Input image updated successfully.",
        }

    except requests.exceptions.HTTPError as http_err:
        logger.error(
            "HTTP Error during API call: %s. Response: %s", 
            http_err, 
            http_err.response.text if http_err.response is not None else "No response",
            exc_info=True
        )
        return {
            "status": "error",
            "tool_response_artifact_id": "",
            "tool_input_artifact_id": image_artifact_id,
            "used_prompt": description,
            "message": f"HTTP Error generating image: {str(http_err)}",
        }

    except Exception as error:
        logger.error(
            "An unexpected error occurred in 'change_background_capability_tool': %s", 
            error, 
            exc_info=True
        )
        return {
            "status": "error",
            "tool_response_artifact_id": "",
            "tool_input_artifact_id": image_artifact_id,
            "used_prompt": description,
            "message": f"Error generating image: {str(error)}",
        }