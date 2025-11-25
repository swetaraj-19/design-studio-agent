import sys
import logging
import warnings
from dotenv import load_dotenv

from google.genai import types
from google.genai import Client

from google.adk import Agent
from google.adk.tools import load_artifacts
from google.adk.tools.tool_context import ToolContext

from .config import (
    GCS_AGENT_MODEL, 
    GCS_AGENT_TEMPERATURE, 
    GCS_AGENT_MAX_TOKENS
)

from .prompts import GCS_AGENT_DESCRIPTION, GCS_AGENT_INSTRUCTION
from .tools import get_image_from_gcs, save_image_to_gcs, search_images_in_gcs

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")


gcs_agent = Agent(
    model=GCS_AGENT_MODEL,
    name='gcs_agent',
    description=GCS_AGENT_DESCRIPTION,
    instruction=GCS_AGENT_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        temperature=GCS_AGENT_TEMPERATURE,
        max_output_tokens=GCS_AGENT_MAX_TOKENS,
    ),
    include_contents="default",
    tools=[
        get_image_from_gcs,
        save_image_to_gcs,
        search_images_in_gcs
    ]
)
