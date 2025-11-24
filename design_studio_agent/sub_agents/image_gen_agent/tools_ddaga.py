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

# NOTE: Do NOT initialize genai.Client globally here. 
# It causes "Event Loop Closed" errors in deployment.

async def generate_image_tool(
    tool_context: ToolContext,
    description: str,
    aspect_ratio: str = "1:1",
    candidate_count: int = 1,
    image_artifact_ids: list = None, # Corrected mutable default
) -> dict[str, str]:
    """
    Tool to generate a new image based on a text description and reference image(s).
    """
    if image_artifact_ids is None:
        image_artifact_ids = []

    # --- INITIALIZATION FIX ---
    # Initialize client inside the function to attach to the current active event loop
    try:
        client = genai.Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION"),
        )
        logger.debug("GenAI Client created successfully within tool scope.")
    except Exception as e:
        logger.critical("Failed to initialize GenAI Client: %s", e, exc_info=True)
        return {"status": "error", "message": "Internal tool configuration error."}
    # --------------------------

    logger.info(
        "Generate Image Tool Triggered | Aspect: %s | Candidates: %d | Input Images: %s",
        aspect_ratio, candidate_count, image_artifact_ids
    )

    try:
        ALLOWED_ASPECT_RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]

        if not image_artifact_ids:
            logger.warning("Validation Failed: No image_artifact_ids provided.")
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_ids": "",
                "used_prompt": description,
                "message": "No reference image provided. Please provide a reference image.",
            }

        image_artifacts = []
        logger.info("Loading %d image artifacts from ToolContext...", len(image_artifact_ids))

        for img_id in image_artifact_ids:
            logger.debug("Fetching artifact: %s", img_id)
            artifact = await tool_context.load_artifact(filename=img_id)

            if artifact is None:
                logger.error("Artifact Missing: %s not found in context.", img_id)
                return {
                    "status": "error",
                    "tool_response_artifact_id": "",
                    "tool_input_artifact_ids": "",
                    "used_prompt": description,
                    "message": f"Artifact {img_id} not found",
                }

            # Log artifact size/type for debugging
            blob_size = len(artifact.inline_data.data) if artifact.inline_data else 0
            logger.debug("Artifact loaded: %s | MIME: %s | Size: %d bytes", 
                         img_id, artifact.inline_data.mime_type, blob_size)
            image_artifacts.append(artifact)

        image_generation_prompt = (
            f"USER PROMPT: {description}.\n\n---\n"
            "**CRITICAL INSTRUCTION: YOU MUST PRESERVE THE REFERENCE PRODUCT.**\n"
            "1.  **DO NOT ALTER THE PRODUCT:** The reference product (bottle, jar, etc.) must be used *exactly* as-is.\n"
            "2.  **PRESERVE ALL TEXT:** All text, logos, and branding on the reference product must be preserved perfectly.\n"
            "3.  **PRESERVE APPEARANCE:** The product's shape, color, design, and label must remain identical.\n"
            "4.  **ONLY CHANGE THE BACKGROUND/SCENE:** Place the *unaltered* product into the new scene."
        )

        logger.debug("Prompt Constructed:\n%s", image_generation_prompt)
        contents = image_artifacts + [image_generation_prompt]

        # Validations
        if aspect_ratio not in ALLOWED_ASPECT_RATIOS:
            logger.warning("Invalid aspect ratio '%s'. Defaulting to '1:1'.", aspect_ratio)
            aspect_ratio = "1:1"
        
        if not (1 <= candidate_count <= 4):
            logger.warning("Invalid candidate_count %d. Defaulting to 1.", candidate_count)
            candidate_count = 1
        
        logger.info(
            "Sending request to Model: %s | Aspect: %s",
            IMAGE_GENERATION_TOOL_MODEL, aspect_ratio
        )

        # Call API
        response = await client.aio.models.generate_content(
            model=IMAGE_GENERATION_TOOL_MODEL,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                response_modalities=["Image"],
                candidate_count=candidate_count,
                image_config=genai.types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )

        logger.info("Model response received.")

        if not response.candidates or not response.candidates[0].content.parts:
            logger.error("Empty response from model. Raw text: %s", response.text)
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_ids": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": "Image generation failed: API returned no image data.",
            }

        artifact_id = ""
        saved_count = 0

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                artifact_id = f"generated_img_{tool_context.function_call_id}.png"
                
                logger.info("Saving output artifact: %s (MIME: %s)", artifact_id, part.inline_data.mime_type)
                
                await tool_context.save_artifact(filename=artifact_id, artifact=part)
                saved_count += 1

        if saved_count == 0:
            logger.error("Response contained content but no inline image data.")
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_ids": ", ".join(image_artifact_ids),
                "used_prompt": image_generation_prompt,
                "message": "Image generation failed: No inline image data found.",
            }

        logger.info("Tool execution successful. Output Artifact: %s", artifact_id)
        
        return {
            "status": "success",
            "tool_response_artifact_id": artifact_id,
            "tool_input_artifact_ids": ", ".join(image_artifact_ids),
            "used_prompt": image_generation_prompt,
            "message": f"Image generated successfully using {len(image_artifacts)} input image(s)",
        }

    except Exception as error:
        input_ids_str = ", ".join(image_artifact_ids) if image_artifact_ids else "None"
        logger.error(
            "CRITICAL ERROR in generate_image_tool. Inputs: %s. Error: %s",
            input_ids_str, error, exc_info=True
        )
        return {
            "status": "error",
            "tool_response_artifact_id": "",
            "tool_input_artifact_ids": input_ids_str,
            "used_prompt": description,
            "message": f"Error generating image: {str(error)}",
        }
