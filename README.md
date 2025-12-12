# Henkel Design Studio Agent 🎨

The Design Studio Agent is a specialized multimodal AI system designed to streamline the creation of marketing assets for Henkel's brands. It abstracts the complexity of prompt engineering and model selection, allowing marketing managers to generate high-volume, brand-compliant visual content via natural language.

The system orchestrates Gemini 2.5 Flash for reasoning and generation, and Imagen 3.0/4.0 for editing, enabling users to source products from Google Cloud Storage, generate photorealistic marketing scenes, and perform precise background editing.

## 🏗 System Architecture

The solution implements a Multi-Agent System (MAS) architecture using the Agent Development Kit (ADK). A central Root Agent evaluates user intent and routes execution to three specialized sub-agents.

1.  **Root Agent (`design_studio_agent`)**:
    *   **Model:** `gemini-2.5-flash`
    *   **Role:** The Orchestrator. Serves as the single entry point for user interaction.
    *   **Routing Logic:** Evaluates intent to route between Creation (Gen Agent), Modification (Edit Agent), or Asset Management (GCS Agent).
    *   **Capabilities:** Context understanding, delegation, and error handling.

2.  **GCS Agent (`gcs_agent`)**:
    *   **Role:** Asset Lifecycle Manager. Handles retrieval and persistence.
    *   **Tools:** 
        *   `search_images_in_gcs`: Uses fuzzy string matching to find product images in the source bucket.
        *   `get_image_from_gcs`: Loads specific binary data into the artifact store.
        *   `save_image_to_gcs`: Uploads final assets to the output bucket and generates signed URLs.

3.  **Image Generation Agent (`image_gen_agent`)**:
    *   **Role:** The Creative Photographer.
    *   **Logic:** Automatically expands user prompts into "meta-prompts" that include brand guidelines, lighting, and camera settings.
    *   **Tools:**
        *   `generate_image_tool (Gemini 2.5 Flash Image)`: Generates new scenes while preserving product integrity via reference artifacts
        *   `generate_image_without_labels_tool`: Generates imagery while stripping text/labels for cleaner artistic outputs.

4.  **Image Edit Agent (`image_edit_agent`)**:
    *   **Role:** The Retoucher.
    *   **Logic:** Offers dual-path optimization based on user needs.
    *   **Tools:** 
        *   `change_background_fast_tool`: Uses Imagen 4.0 Fast. rapid iteration. Supports custom Aspect Ratios (16:9, 1:1, etc.) and Sample Counts
        *   `change_background_capability_tool`: Uses Imagen 3.0 Capability. Supports precise product masking to preserve the exact pixels of the reference product.

## 🚀 Setup & Installation

### Prerequisites
*   Python 3.12+
*   LLMs: Gemini 2.5 Flash, Gemini 2.5 Pro
*   Image Models: Imagen 3.0 Capability, Imagen 4.0 Fast
*   Google Cloud Project with Vertex AI API enabled.
*   Google Cloud Storage Buckets (one for source images, one for output).

### Environment Variables
Create a `.env` file in the root directory:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
# Bucket containing source product images
GCS_BUCKET_SKU_DATA=your-source-bucket-name
# Bucket to save generated images
GCS_BUCKET_OUTPUT=your-output-bucket-name
```

### Installation

```bash
# Clone repository
git clone <repo-url>
cd design_studio_agent

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
uv sync --active 
```

## 💬 Agent Capabilities & Prompt Examples

The agent is designed to handle a full asset creation workflow. Below are examples of how to interact with it.

### 1. Sourcing Assets (GCS Agent)
*Before generating or editing, the agent usually needs a reference product.*

> **User:** "I need to find the image for the Kenra Volume Spray."

**Agent Action:**
* Delegates to `gcs_agent`.
* Executes `search_images_in_gcs("Kenra Volume Spray")`.
* Returns a list of matching filenames.

> **Agent Response:**
> "I found a few matches in the database:
> 1. `Volume Spray 25 1.5oz.png`
> 2. `Volume Spray 25 10oz.png`
> Which one would you like to use?"

![Sourcing Assets (GCS Agent)](images/gcs_fetch.png)

### 2. Image Generation (Gen Agent)
*Creating a new scene from scratch using the sourced product.*

> **User:** "Use the first image (`Volume Spray 25 1.5oz.png`). Generate a high-definition marketing shot of this bottle sitting on a marble counter in a luxury bathroom. Soft lighting, bokeh background."

**Agent Action:**
* `root_agent` delegates to `gcs_agent` to load the file (if not already loaded).
* Delegates to `image_gen_agent`.
* Executes `generate_image_tool`.
* **Constraint:** Strictly preserves text and logo.
* **Creative:** Generates marble counter and bathroom context.

> **Agent Response:**
> *(Displays generated image)* 
![generate](images/generate.png)
> "Here is the generated image of the Volume Spray in a luxury bathroom setting. Would you like to save this or try a different angle?"

### 3. Background Editing (Edit Agent)
*Quickly swapping the background of an existing asset.*

> **User:** "Can you just change the background to a solid studio grey? I need it for a catalog. [Upload the reference image]"

**Agent Action:**
* Delegates to `image_edit_agent`.
* Executes `change_background_fast_tool` (Optimized for speed).

> **Agent Response:**
> *(Displays edited image)*
![edit](images/edit.png)
> "I've updated the background to solid studio grey. How does this look?"

### 4. Saving & Publishing
*Finalizing the asset.*

> **User:** "That's perfect. Save it to the cloud."

**Agent Action:**
* Delegates to `gcs_agent`.
* Executes `save_image_to_gcs`.

> **Agent Response:**
> "I have saved the image as `generated_img_123.png`.
> You can download it here: **[Signed URL Link]** (Valid for 120 minutes)."

## 🛠 Deployment

### ADK Web (Local Host)

**Running Locally**
```bash
# Clone repository
git clone <repo-url>
cd design_studio_agent

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
uv sync --active 
gcloud auth application-default login

adk web
```

### Google Cloud Run Deployment

https://google.github.io/adk-docs/deploy/cloud-run/ 

## 🔍 Logging & Observability
The agent utilizes standard Python logging with distinct levels:

-   DEBUG: Full LLM prompts/responses and internal state transitions.

-   INFO: Tool execution and agent routing decisions.

-   ERROR: API failures (Gemini/Imagen/GCS).

-   Logs are automatically streamed to Google Cloud Logging when deployed to Agent Engine.