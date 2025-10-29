import base64
import logging
import warnings
from dotenv import load_dotenv

from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext

from .config import (
    ROOT_AGENT_MODEL, 
    ROOT_AGENT_TEMPERATURE, 
    ROOT_AGENT_MAX_TOKENS
)
from .prompts import ROOT_AGENT_DESCRIPTION, ROOT_AGENT_INSTRUCTION
from .sub_agents.image_gen_agent.agent import image_gen_agent
from .tools.utils import decode_b64_str


load_dotenv()
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")
logger = logging.getLogger(__name__)


def before_agent_callback(callback_context: CallbackContext):
    state = callback_context.state
    user_content = callback_context.user_content

    if not user_content or not user_content.parts:
        return
    
    image_parts_list = []
    first_image_b64 = None

    keys_to_clear = [
        "uploaded_image_b64",
        "uploaded_mask_b64",
        "uploaded_image_parts"
    ]

    for key in keys_to_clear:
        if state.get(key) is not None:
            state[key] = None

    for i, part in enumerate(user_content.parts):
        if hasattr(part, 'inline_date') and getattr(part.inline_data, 'mime_type', '').startswith('image/'):
            mime_type = part.inline_data.mime_type
            part_data_container = part.inline_data
            current_data_bytes = None

            raw_bytes = getattr(part_data_container, 'data', None)

            if raw_bytes and isinstance(raw_bytes, (bytes, bytearray)):
                current_data_bytes = raw_bytes

            else:
                b64_data = getattr(part_data_container, 'b64_json', None)
                if b64_data and isinstance(b64_data, str):
                    try:
                        current_data_bytes = decode_b64_str(b64_data)
                    except:
                        # failed to decode b64
                        continue
                else:
                    # unsuitable image part
                    continue
            
            if current_data_bytes:
                try:
                    current_b64_str = base64.b64encode(current_data_bytes).decode('utf-8')
                    image_part_info = {
                        "b64": current_b64_str,
                        "mime_type": mime_type
                    }

                    image_parts_list.append(image_part_info)

                    if first_image_b64 is None:
                        first_image_b64 = current_b64_str
                
                except:
                    continue

    if image_parts_list:
        state["uploaded_image_parts"] = image_parts_list
    
    if first_image_b64:
        state["uploaded_image_b64"] = first_image_b64
    
    else:
        if "uploaded_image_b64" in state:
            del state["uploaded_image_b64"]

    return None


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
    before_agent_callback=before_agent_callback
)