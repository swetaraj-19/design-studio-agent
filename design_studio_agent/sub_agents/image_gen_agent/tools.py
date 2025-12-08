import os
import json
import base64
import logging
import requests
import warnings
import numpy as np
from dotenv import load_dotenv

from google import genai
from google.adk.tools import ToolContext

from .config import IMAGE_GENERATION_TOOL_MODEL

load_dotenv()
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")


async def generate_image_tool(
    tool_context: ToolContext,
    description: str,
    aspect_ratio: str,
    candidate_count: int,
    image_artifact_ids: list = [],
) -> dict[str, str]:
    """
    Tool to generate a new image based on a text description and the provided 
    reference image(s).

    This tool generates a new image based on the user's text description and 
    the reference image(s), provided in `image_artifact_ids`. It automatically 
    fetches the reference images from the artifacts using the id's provided in 
    the `image_artifact_ids`.

    NOTE: This tool should not be used for `image editing` tasks such as updating the 
    background of an image. For image editing tasks, delegate to `image_edit_agent`.

    Args:
        description (str): Text description describing the desired image output.
            * Be detailed and specific with describing the image.
                - e.g., "Image of a shampoo bottle on a spa counter."
        aspect_ratio (str): Desired aspect ratio for the generated image.
            * Must be one of: ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
            * Default is "1:1".
                - e.g., "1:1"
        candidate_count (int): Number of images to generate.
            * Must be between 1 to 4. Default is 1.
                - e.g., 3
        image_artifact_ids (list): List of image IDs to use as reference image.
            * For single image: provide a list with one item 
                - e.g., ["product.png"]
            * For multiple images: provide a list with multiple items 
                - e.g., ["product1.png", "product2.png"]

    Returns:
        dict: A dictionary containing the operation result:
            - 'tool_response_artifact_id': Artifact ID for the generated image
            - 'tool_input_artifact_id': Comma-separated list of input artifact IDs
            - 'used_prompt': The full image generation prompt used
            - 'status': Success or error status
            - 'message': Additional information or error details
    """
    logger.info(
        "Tool 'generate_image_tool' started. Aspect: %s, Candidates: %d, Input Images: %s",
        aspect_ratio,
        candidate_count,
        image_artifact_ids,
    )

    try:
        ALLOWED_ASPECT_RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]

        try:
            client = genai.Client(
                vertexai=True,
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION"),
            )
            logger.debug("Gen AI client instantiated successfully within tool scope.")

        except Exception as e:
            logger.critical("Failed to initialize GenAI Client: %s", e, exc_info=True)
            return {"status": "error", "message": "Internal tool configuration error."}

        if not image_artifact_ids:
            logger.warning("Execution failed: No image_artifact_ids provided.")
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": "",
                "used_prompt": description,
                "message": "No reference image provided. Please provide a reference image to generate the image.",
            }

        image_artifacts = []
        logger.info("Attempting to load %d image artifacts.", len(image_artifact_ids))

        for img_id in image_artifact_ids:
            logger.debug("Loading artifact: %s", img_id)
            artifact = await tool_context.load_artifact(filename=img_id)

            if artifact is None:
                logger.error("Artifact %s not found in tool context.", img_id)
                return {
                    "status": "error",
                    "tool_response_artifact_id": "",
                    "tool_input_artifact_id": "",
                    "used_prompt": description,
                    "message": f"Artifact {img_id} not found",
                }

            image_artifacts.append(artifact)
            logger.debug("Artifact %s loaded successfully.", img_id)

        logger.info("Successfully loaded %d image artifact(s).", len(image_artifacts))

        image_generation_prompt = (
            f"USER PROMPT: {description}.\n\n---\n"
            "**CRITICAL INSTRUCTION: YOU MUST PRESERVE THE REFERENCE PRODUCT.**\n"
            "1.  **DO NOT ALTER THE PRODUCT:** The reference product (bottle, jar, etc.) must be used *exactly* as-is.\n"
            "2.  **PRESERVE ALL TEXT:** All text, logos, and branding on the reference product must be preserved perfectly. Do not regenerate, misspell, or change any text.\n"
            "3.  **PRESERVE APPEARANCE:** The product's shape, color, design, and label must remain identical to the reference image.\n"
            "4.  **ONLY CHANGE THE BACKGROUND/SCENE:** Your only task is to place the *unaltered* product into the new scene described in the user prompt."
        )

        if not image_artifacts:
            return {
                "status": "error",
                "tool_response:artifact_id": "",
                "tool_input_artifact_id": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": "Please provide a reference image to generate the image."
            }

        logger.debug("Final augmented prompt prepared:\n%s", image_generation_prompt)
        contents = image_artifacts + [image_generation_prompt]

        if aspect_ratio not in ALLOWED_ASPECT_RATIOS:
            logger.warning(
                "Invalid aspect ratio '%s' provided. Defaulting to '1:1'.", 
                aspect_ratio
            )
            aspect_ratio = "1:1"
        
        if not (1 <= candidate_count <= 4):
            logger.warning(
                "Invalid candidate_count %d (must be 1-4). Defaulting to 1.", 
                candidate_count
            )
            candidate_count = 1
        
        logger.info(
            "Calling nano-banana API for image generation. Model: %s, Aspect: %s, Candidates: %d",
            IMAGE_GENERATION_TOOL_MODEL,
            aspect_ratio,
            candidate_count,
        )

        try:
            response = await client.aio.models.generate_content(
                model=IMAGE_GENERATION_TOOL_MODEL,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    response_modalities=["Image"],
                    candidate_count=candidate_count,
                    image_config=genai.types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                    )
                ),
            )
        
        except Exception as error:
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": f"Error generating image: {str(error)}",
            }

        logger.info("GenAI API call completed successfully.")

        if not response.candidates or not response.candidates[0].content.parts:
            logger.error(
                "API response has no candidates or content parts. Raw response: %s",
                response.text,
            )
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": "Image generation failed: API returned no image data.",
            }

        artifact_id = ""

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                artifact_id = f"generated_img_{tool_context.function_call_id}.png"

                logger.info(
                    "Saving generated image artifact: %s (MIME: %s)", 
                    artifact_id,
                    part.inline_data.mime_type
                )

                await tool_context.save_artifact(
                    filename=artifact_id, 
                    artifact=part
                )

                logger.debug("Artifact %s saved.", artifact_id)

        if not artifact_id:
            logger.error("API call succeeded but no inline image data was found to save.")
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": "Image generation failed: API returned image data but it was not inline data.",
            }

        input_ids_str = ", ".join(image_artifact_ids)
        
        return {
            "status": "success",
            "tool_response_artifact_id": artifact_id,
            "tool_input_artifact_id": input_ids_str,
            "used_prompt": image_generation_prompt,
            "message": f"Image generated successfully using {len(image_artifacts)} input image(s)",
        }

    except Exception as error:
        input_ids_str = ", ".join(image_artifact_ids) if image_artifact_ids else ""

        logger.error(
            "An unexpected error occurred in 'generate_image_tool'. Input IDs: %s. Error: %s",
            input_ids_str,
            error,
            exc_info=True
        )

        return {
            "status": "error",
            "tool_response_artifact_id": "",
            "tool_input_artifact_id": input_ids_str,
            "used_prompt": description,
            "message": f"Error generating image: {str(error)}",
        }


async def generate_image_without_labels_tool(
    tool_context: ToolContext,
    description: str,
    aspect_ratio: str,
    candidate_count: int,
    image_artifact_ids: list = [],
) -> dict[str, str]:
    """
    Tool to generate a new image based on a text description and the provided 
    reference image(s). This tool removes the labels from the product bottle.

    This tool generates a new image based on the user's text description and 
    the reference image(s), provided in `image_artifact_ids` and removes all 
    labels from the product bottle. It automatically fetches the reference 
    images from the artifacts using the id's provided in the `image_artifact_ids`.

    NOTE: This tool should not be used for `image editing` tasks such as changing the 
    background of an image. For image editing tasks, delegate to `image_edit_agent`.

    Args:
        description (str): Text description describing the desired image output.
            * Be detailed and specific with describing the image. 
            * IMPORTANT: You MUST request the model to remove all the labels from 
              the product image, while only retaining the colour and the physical 
              appearence of the bottle. 
            * The product in the generated image MUST be devoid of all text and 
              graphics, while strictly preserving the original physical appearance, 
              color, and shape of the reference object.
                - e.g., "Image of a shampoo bottle on a spa counter. Remove all labels from the bottle."
        aspect_ratio (str): Desired aspect ratio for the generated image.
            * Must be one of: ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
            * Default is "1:1".
                - e.g., "1:1"
        candidate_count (int): Number of images to generate.
            * Must be between 1 to 4. Default is 1.
                - e.g., 3
        image_artifact_ids (list): List of image IDs to use as reference image.
            * For single image: provide a list with one item 
                - e.g., ["product.png"]
            * For multiple images: provide a list with multiple items 
                - e.g., ["product1.png", "product2.png"]

    Returns:
        dict: A dictionary containing the operation result:
            - 'tool_response_artifact_id': Artifact ID for the generated image
            - 'tool_input_artifact_id': Comma-separated list of input artifact IDs
            - 'used_prompt': The full image generation prompt used
            - 'status': Success or error status
            - 'message': Additional information or error details
    """
    logger.info(
        "Tool 'generate_image_tool' started. Aspect: %s, Candidates: %d, Input Images: %s",
        aspect_ratio,
        candidate_count,
        image_artifact_ids,
    )

    try:
        ALLOWED_ASPECT_RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]

        try:
            client = genai.Client(
                vertexai=True,
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION"),
            )
            logger.debug("Gen AI client instantiated successfully within tool scope.")

        except Exception as e:
            logger.critical("Failed to initialize GenAI Client: %s", e, exc_info=True)
            return {"status": "error", "message": "Internal tool configuration error."}

        if not image_artifact_ids:
            logger.warning("Execution failed: No image_artifact_ids provided.")
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": "",
                "used_prompt": description,
                "message": "No reference image provided. Please provide a reference image to generate the image.",
            }

        image_artifacts = []
        logger.info("Attempting to load %d image artifacts.", len(image_artifact_ids))

        for img_id in image_artifact_ids:
            logger.debug("Loading artifact: %s", img_id)
            artifact = await tool_context.load_artifact(filename=img_id)

            if artifact is None:
                logger.error("Artifact %s not found in tool context.", img_id)
                return {
                    "status": "error",
                    "tool_response_artifact_id": "",
                    "tool_input_artifact_id": "",
                    "used_prompt": description,
                    "message": f"Artifact {img_id} not found",
                }

            image_artifacts.append(artifact)
            logger.debug("Artifact %s loaded successfully.", img_id)

        logger.info("Successfully loaded %d image artifact(s).", len(image_artifacts))

        image_generation_prompt = (
            f"USER PROMPT: {description}.\n\n---\n"
            "The product in the generated image must be devoid of all text and graphics, while strictly preserving the original physical appearance, color, and shape of the reference object.\n\n"
            "### **CRITICAL INSTRUCTION: GENERATE AN UNBRANDED, BLANK VERSION OF THE REFERENCE PRODUCT WITH ALL ORIGINAL COLOURS PRESERVED.**\n"
            "1.  **GEOMETRY & MATERIAL ONLY:** Retain the exact physical shape, 3D geometry, material finish, and lighting of the reference bottle. However, treat the surface as a blank canvas while preserving the actual colours of the product bottle.\n"
            "2.  **STRICT TEXT REMOVAL:** The product must be completely devoid of any typography, alphanumeric characters, logos, or barcodes. There should be zero writing on the container.\n"
            "3.  **SURFACE CONTINUITY:** The bottle body must appear as a smooth, continuous surface. Where the label used to be, fill the area with the base material or the color as appropriate.\n"
            "4.  **FACTORY BLANK APPEARANCE:** The object should look like a factory prototype or a stock photo prop before the printing stage, but with all the colours preserved. It is an unbranded, generic container, with colours as that of the actual reference product, that strictly mimics the form factor of the reference.\n"
        )

        if not image_artifacts:
            return {
                "status": "error",
                "tool_response:artifact_id": "",
                "tool_input_artifact_id": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": "Please provide a reference image to generate the image."
            }

        logger.debug("Final augmented prompt prepared:\n%s", image_generation_prompt)
        contents = image_artifacts + [image_generation_prompt]

        if aspect_ratio not in ALLOWED_ASPECT_RATIOS:
            logger.warning(
                "Invalid aspect ratio '%s' provided. Defaulting to '1:1'.", 
                aspect_ratio
            )
            aspect_ratio = "1:1"
        
        if not (1 <= candidate_count <= 4):
            logger.warning(
                "Invalid candidate_count %d (must be 1-4). Defaulting to 1.", 
                candidate_count
            )
            candidate_count = 1
        
        logger.info(
            "Calling nano-banana API for image generation. Model: %s, Aspect: %s, Candidates: %d",
            IMAGE_GENERATION_TOOL_MODEL,
            aspect_ratio,
            candidate_count,
        )

        try:
            response = await client.aio.models.generate_content(
                model=IMAGE_GENERATION_TOOL_MODEL,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    response_modalities=["Image"],
                    candidate_count=candidate_count,
                    image_config=genai.types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                    )
                ),
            )
        
        except Exception as error:
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": f"Error generating image: {str(error)}",
            }

        logger.info("GenAI API call completed successfully.")

        if not response.candidates or not response.candidates[0].content.parts:
            logger.error(
                "API response has no candidates or content parts. Raw response: %s",
                response.text,
            )
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": "Image generation failed: API returned no image data.",
            }

        artifact_id = ""

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                artifact_id = f"generated_img_{tool_context.function_call_id}.png"

                logger.info(
                    "Saving generated image artifact: %s (MIME: %s)", 
                    artifact_id,
                    part.inline_data.mime_type
                )

                await tool_context.save_artifact(
                    filename=artifact_id, 
                    artifact=part
                )

                logger.debug("Artifact %s saved.", artifact_id)

        if not artifact_id:
            logger.error("API call succeeded but no inline image data was found to save.")
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_id": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": "Image generation failed: API returned image data but it was not inline data.",
            }

        input_ids_str = ", ".join(image_artifact_ids)
        
        return {
            "status": "success",
            "tool_response_artifact_id": artifact_id,
            "tool_input_artifact_id": input_ids_str,
            "used_prompt": image_generation_prompt,
            "message": f"Image generated successfully using {len(image_artifacts)} input image(s)",
        }

    except Exception as error:
        input_ids_str = ", ".join(image_artifact_ids) if image_artifact_ids else ""

        logger.error(
            "An unexpected error occurred in 'generate_image_tool'. Input IDs: %s. Error: %s",
            input_ids_str,
            error,
            exc_info=True
        )

        return {
            "status": "error",
            "tool_response_artifact_id": "",
            "tool_input_artifact_id": input_ids_str,
            "used_prompt": description,
            "message": f"Error generating image: {str(error)}",
        }
