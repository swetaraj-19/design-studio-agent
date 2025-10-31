from google.genai import types
from google.genai import Client

from google.adk import Agent
from google.adk.tools import load_artifacts
from google.adk.tools.tool_context import ToolContext

from .callbacks import before_image_gen_model_callback
from .config import (
    IMAGE_GEN_AGENT_MODEL, 
    IMAGE_GEN_AGENT_TEMPERATURE, 
    IMAGE_GEN_AGENT_MAX_TOKENS
)
from .prompts import IMAGE_GEN_AGENT_DESCRIPTION, IMAGE_GEN_AGENT_INSTRUCTION
from .tools import generate_image_tool


image_gen_agent = Agent(
    model=IMAGE_GEN_AGENT_MODEL,
    name='image_gen_agent',
    description=IMAGE_GEN_AGENT_DESCRIPTION,
    instruction=IMAGE_GEN_AGENT_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        temperature=IMAGE_GEN_AGENT_TEMPERATURE,
        max_output_tokens=IMAGE_GEN_AGENT_MAX_TOKENS,
    ),
    include_contents="default",
    tools=[
        generate_image_tool
    ],
    before_model_callback=before_image_gen_model_callback
)
