import base64
import logging
import warnings
from dotenv import load_dotenv

from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext

from .callbacks import before_root_agent_model_callback
from .config import (
    ROOT_AGENT_MODEL, 
    ROOT_AGENT_TEMPERATURE, 
    ROOT_AGENT_MAX_TOKENS
)
from .prompts import ROOT_AGENT_DESCRIPTION, ROOT_AGENT_INSTRUCTION
from .sub_agents.image_gen_agent.agent import image_gen_agent
from .tools.utils import decode_b64_str

load_dotenv()
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")


root_agent = LlmAgent(
    name="root_agent",
    model=ROOT_AGENT_MODEL,
    description=ROOT_AGENT_DESCRIPTION,
    instruction=ROOT_AGENT_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        temperature=ROOT_AGENT_TEMPERATURE,
        max_output_tokens=ROOT_AGENT_MAX_TOKENS,
    ),
    include_contents="default",
    sub_agents=[
        image_gen_agent
    ],
    tools=[],
    before_model_callback=before_root_agent_model_callback,
)