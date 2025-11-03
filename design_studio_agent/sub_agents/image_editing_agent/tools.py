import os
import logging
from dotenv import load_dotenv

from google import genai
from google.genai import types
from google.adk.tools import ToolContext

# Import configs from this agent's LOCAL config.py
from ...config import PROJECT_ID, LOCATION
from .config import IMAGE_EDIT_TOOL_MODEL 

load_dotenv()
logger = logging.getLogger(__name__)

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID or os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=LOCATION or os.getenv("GOOGLE_CLOUD_LOCATION"),
)

async def edit_image_tool(
    tool_context: ToolContext,
    description: str,
    image_artifact_ids: list,
) -> dict[str, str]:
    """
    Tool to generate a new image based on a text description and
    a reference image (image-to-image), using the 'generate_content' method.
    """
    try:
        if not image_artifact_ids:
            return {"status": "error", "message": "No reference image artifact ID provided."}

        # 1. Load the reference image artifact
        input_image_id = image_artifact_ids[0]
        image_artifact = await tool_context.load_artifact(filename=input_image_id)
        
        if image_artifact is None:
            return {"status": "error", "message": f"Artifact {input_image_id} not found."}

        logger.info(f"Performing image-to-image edit with prompt: {description}")
        
        # 2. Create the prompt for the model
        edit_prompt_text = f"""
        USER REQUEST: {description}
        
        ---
        "**CRITICAL INSTRUCTION: YOU MUST PRESERVE THE REFERENCE PRODUCT.**\n"
            "1.  **PRODUCT PRESERVATION:** The reference product (bottle, jar, etc.) must be used *exactly* as-is. Do not change its lighting, angle, or position.\n"
            "2.  **TEXT IS SACRED:** All text, logos, and branding on the reference product must be preserved perfectly. Do not regenerate, misspell, or change any text.\n"
            "3.  **APPEARANCE INTEGRITY:** The product's shape, color, design, and label must remain identical to the reference image.\n"
            "4.  **COMPLETE BACKGROUND REPLACEMENT:** Your primary task is to completely replace the *entire background and scene* behind the product with the one described in the user prompt. **Absolutely no elements from the original background should remain.** This includes any existing decorations, patterns, surfaces, or objects. The new scene should be fully coherent and replace all previous background elements.\n"
            "5.  **FOCUS ON NEW SCENE:** Ensure the new background is the dominant visual element behind the product, completely overriding anything from the original image's background."
            "6.  **PHOTOREALISTIC LIGHTING & CONTRAST MATCHING:** Analyze the lighting (direction, intensity, color), shadows, and overall contrast/brightness of the *original product*. The *newly generated background* must meticulously match these lighting conditions and contrast levels. Ensure the new scene's lighting is consistent with the product's existing lighting to achieve a seamless, photorealistic, and professional look. 
                 Avoid harsh shadows or highlights that don't align with the product. The product should remain prominent and perfectly integrated, not look like it's been artificially placed.\n"
            "7.  **HARMONIOUS COLOR PALETTE:** While creating the new background, ensure its color palette complements the product without clashing. The product should stand out naturally against the new background, maintaining its prominence and visual appeal."
        )
        """
        
        # 3. Send the reference image + text prompt to the model
        # This is the same method as your image_gen_agent, but we add
        # the image_artifact to the contents list.
        contents = [image_artifact, edit_prompt_text]
        
        response = await client.aio.models.generate_content(
            model=IMAGE_EDIT_TOOL_MODEL, # Uses gemini-2.5-flash-image
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["Image"], # We want an image back
                candidate_count=1
            ),
        )

        # 4. Save the new image as an artifact
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    artifact_id = f"edited_img_{tool_context.function_call_id}.png"
                    await tool_context.save_artifact(filename=artifact_id, artifact=part)
                    
                    logger.info(f"Successfully generated new image and saved as {artifact_id}")
                    return {
                        "status": "success",
                        "tool_response_artifact_id": artifact_id,
                        "tool_input_artifact_ids": input_image_id,
                        "used_prompt": description,
                        "message": "Image edited successfully.",
                    }
        
        return {"status": "error", "message": "Image editing call succeeded but no image part was returned."}

    except Exception as e:
        logger.error(f"Error in edit_image_tool: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error editing image: {str(e)}",
        }