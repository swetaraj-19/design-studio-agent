from google.genai import Client
from google.cloud import storage
import datetime

from .. import config

conf = config.Config()

client = Client(
    vertexai=True,
    project=conf.PROJECT_ID,
    location=conf.LOCATION,
)

GCS_BUCKET_NAME = conf.GCS_BUCKET_NAME
storage_client = storage.Client(project=conf.PROJECT_ID)


class MediaGeneration:
    def generate_image(img_prompt: str):
        """
        Generates an image based on the prompt.
        Args:
            img_prompt (str): The prompt for image generation.
        Returns:
            dict: A dictionary containing the status, detail, and image URL if successful.
        """

        response = client.models.generate_images(
            model=conf.IMAGE_MODEL,
            prompt=img_prompt,
            config={"number_of_images": 1},
        )
        if not response.generated_images:
            return {"status": "failed"}

        generated_image = response.generated_images[0].image
        if not generated_image:
            return {"status": "failed"}
        image_bytes = generated_image.image_bytes
        print(len(image_bytes))
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        gcs_object_name = f"images/{timestamp}.png"

        try:
            bucket = storage_client.bucket(GCS_BUCKET_NAME)

            blob = bucket.blob(gcs_object_name)
            blob.upload_from_string(image_bytes, content_type="image/png")
            print(
                blob.public_url.replace(
                    "https://storage.googleapis.com/",
                    "https://storage.mtls.cloud.google.com/",
                    1,
                )
            )
            return {
                "status": "success",
                "detail": "Image generated and uploaded to GCS",
                "image_url": blob.public_url.replace(
                    "https://storage.googleapis.com/",
                    "https://storage.mtls.cloud.google.com/",
                    1,
                ),
            }
        except IOError as e:
            return {"status": "failed", "detail": f"Failed to upload image to GCS: {e}"}