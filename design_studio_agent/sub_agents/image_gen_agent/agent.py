from google.genai import types
from google.genai import Client

from google.adk import Agent
from google.adk.tools import load_artifacts
from google.adk.tools.tool_context import ToolContext


client = Client()

async def generate_image(prompt: str, tool_context: 'ToolContext'):
    image = None

    try:
        availabl_files = await tool_context.list_artifacts()
        if not availabl_files:
            print("You have no saved artifacts.")
        else:
            image = await tool_context.load_artifact(availabl_files[-1])

    except Exception as e:
        print(f"Error generating image: {e}")
        return

    contents = [prompt]

    if image is not None:
        contents.append(image)

    response = client.models.generate_content(
        model='gemini-2.5-flash-image',
        contents=contents,
    )

    print(response)

    for part in response.candidates[0].content.parts:
        if part.text is not None:
            print(part.text)

        elif part.inline_data is not None:
            image_bytes = part.inline_data.data

            await tool_context.save_artifact(
                'image.png',
                types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
            )

            return {
                'status': 'success',
                'detail': 'Image generated successfully and stored in artifacts.',
                'filename': 'image.png',
            }

    return {'status': 'failed'}

image_gen_agent = Agent(
    model='gemini-2.5-flash',
    name='image_gen_agent',
    description="""An agent that generates images based on the provided reference images.""",
    instruction="""You are an agent whose job is to generate an image based on the user's prompt and reference image.
    """,
    tools=[generate_image, load_artifacts],
)