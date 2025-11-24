import os
import logging
import warnings
from dotenv import load_dotenv

from google import genai
from google.adk.tools import ToolContext
from .config import IMAGE_GENERATION_TOOL_MODEL

load_dotenv()
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")

# REMOVED GLOBAL CLIENT INIT FROM HERE

async def generate_image_tool(
    tool_context: ToolContext,
    description: str,
    aspect_ratio: str = "1:1", # Added default here based on docstring
    candidate_count: int = 1,  # Added default here based on docstring
    image_artifact_ids: list = None, # Fixed mutable default argument
) -> dict[str, str]:
    
    if image_artifact_ids is None:
        image_artifact_ids = []

    # --- FIX START: Initialize Client inside the function ---
    # This ensures the client attaches to the currently running event loop
    client = genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION"),
    )
    # --- FIX END ---

    logger.info(
        "Tool 'generate_image_tool' started. Aspect: %s, Candidates: %d, Input Images: %s",
        aspect_ratio,
        candidate_count,
        image_artifact_ids,
    )

    try:
        ALLOWED_ASPECT_RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]

        if not image_artifact_ids:
            logger.warning("Execution failed: No image_artifact_ids provided.")
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_ids": "",
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
                    "tool_input_artifact_ids": "",
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

        logger.info("GenAI API call completed successfully.")

        if not response.candidates or not response.candidates[0].content.parts:
            logger.error(
                "API response has no candidates or content parts. Raw response: %s",
                response.text,
            )
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_ids": ", ".join(image_artifact_ids),
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
                "tool_input_artifact_ids": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": "Image generation failed: API returned image data but it was not inline data.",
            }

        input_ids_str = ", ".join(image_artifact_ids)
        
        return {
            "status": "success",
            "tool_response_artifact_id": artifact_id,
            "tool_input_artifact_ids": input_ids_str,
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
            "tool_input_artifact_ids": input_ids_str,
            "used_prompt": description,
            "message": f"Error generating image: {str(error)}",
        }
