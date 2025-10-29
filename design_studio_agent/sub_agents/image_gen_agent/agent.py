import logging
import warnings
from dotenv import load_dotenv

from google.genai import types
from google.adk.agents import LlmAgent

from .config import (
    IMAGE_GEN_AGENT_MODEL, 
    IMAGE_GEN_AGENT_TEMPERATURE, 
    IMAGE_GEN_AGENT_MAX_TOKENS
)
from .prompts import IMAGE_GEN_AGENT_DESCRIPTION, IMAGE_GEN_AGENT_INSTRUCTION
from .tools import generate_image_tool

load_dotenv()
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")
logger = logging.getLogger(__name__)


image_gen_agent = LlmAgent(
    name="image_gen_agent",
    model=IMAGE_GEN_AGENT_MODEL,
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
    disallow_transfer_to_peers=False,
    disallow_transfer_to_parent=False,
)
