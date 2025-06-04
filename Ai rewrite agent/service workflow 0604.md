# AI Content Rewrite Workflow Report (As of June 4, 2025)

This document outlines the current workflow for the AI Content Rewrite feature, detailing the components, their interactions, inputs, outputs, and the role of LLMs and Python functions.

## I. Overall Workflow (High-Level)

1.  **User Action (Frontend):** The user, on a card's page (e.g., "New Card" or "Edit Card"), clicks an "AI Rewrite Content" button.
2.  **Frontend Request (Next.js App):**
    *   The frontend gathers the current `content_blocks` (which are `AIServiceContentBlock[]` or `PartialBlock[]` depending on the context, eventually mapped to `AIServiceContentBlock[]` by `mapPartialBlocksToAIServiceContentBlocks` in `src/lib/contentUtils.ts`).
    *   It makes a POST request to the Next.js API endpoint: `/api/ai/rewrite-content`.
    *   Payload: `{ content_blocks_to_rewrite: AIServiceContentBlock[] }`
3.  **Next.js API Route (`src/app/api/ai/rewrite-content/route.ts`):**
    *   Receives the `content_blocks_to_rewrite`.
    *   Makes a POST request to the Python `aiservice` endpoint: `${AISERVICE_URL}/api/v1/ai/rewrite-content`.
    *   Payload: Matches the structure received from the frontend.
    *   Waits for the `aiservice` response.
    *   On success, receives `{ ai_rewritten_content_blocks: AIServiceContentBlock[] }`.
    *   Returns this response to the frontend.
4.  **Python `aiservice` (`aiservice/app/api/api_v1/endpoints/ai_operations.py` - `/rewrite-content`):**
    *   Receives `content_blocks_to_rewrite: List[AIServiceContentBlock]` and `document_metadata: Optional[DocumentMetadata]` (though `document_metadata` is often not explicitly passed or used in the rewrite-specific part of the current crew manager).
    *   Instantiates `ContentRewriteCrewManager`.
    *   Calls `manager.run(rewrite_input_data)`.
    *   If successful, returns `{ "ai_rewritten_content_blocks": List[AIServiceContentBlock], "status_code": "success_rewrite_content", "error_message": null }`.
5.  **Frontend Response Handling:**
    *   Receives the `ai_rewritten_content_blocks`.
    *   Updates its state to display these blocks, typically in a side-by-side comparison modal.

## II. Key Modules & Their Interactions

### A. Frontend (Next.js/React - TypeScript)

*   **`src/app/cards/new/page.tsx` (and similar edit pages):**
    *   **Function:** Handles user interaction, manages state for original and rewritten content.
    *   **Key Functions:**
        *   `handleRewriteContent()`: Orchestrates the API call.
        *   `mapPartialBlocksToAIServiceContentBlocks()` (from `src/lib/contentUtils.ts`): Converts BlockNote's `PartialBlock[]` to `AIServiceContentBlock[]` before sending to the API. This is crucial for ensuring images have `image_id_ref`, `gcs_url`, etc.
    *   **Input to `handleRewriteContent()`:** Current content blocks from the editor.
    *   **Output (to user):** Displays original and rewritten content.
*   **`src/lib/contentUtils.ts`:**
    *   **`mapPartialBlocksToAIServiceContentBlocks()`:**
        *   **Input:** `partialBlocks: AppPartialBlock[]`, `userId: string`, `documentId: string`.
        *   **Output:** `AIServiceContentBlock[]`.
        *   **Logic:** Maps BlockNote editor's block structure (including images with `props.url` and `props.caption`) to the `AIServiceContentBlock` format, ensuring fields like `image_id_ref` (set to `block.id`), `gcs_url` (set to `block.props.url`), and `caption` are correctly populated for image blocks. For text blocks, it extracts and maps content.
    *   **`mapContentBlocksToPartialBlocks()`:**
        *   **Input:** `aiBlocks: AIServiceContentBlock[]`.
        *   **Output:** `PartialBlock[]` (for BlockNote editor).
        *   **Logic:** Converts `AIServiceContentBlock[]` (e.g., from API response) back into BlockNote's `PartialBlock` format for rendering in the editor. For images, it sets `props: { url: block.gcs_url, caption: block.caption || "" }`.

### B. Next.js API Layer (TypeScript)

*   **`src/app/api/ai/rewrite-content/route.ts`:**
    *   **Function:** Acts as a proxy and error handler between the frontend and the Python `aiservice`.
    *   **Input:** `{ content_blocks_to_rewrite: AIServiceContentBlock[] }`.
    *   **Output (to frontend):** `{ ai_rewritten_content_blocks: AIServiceContentBlock[] }` or an error response.
    *   **Key Logic:**
        *   Receives JSON payload.
        *   Uses `fetch` to call the Python `aiservice` endpoint.
        *   Handles response status and JSON parsing.
        *   Includes timeout mechanisms (currently around 300 seconds, leading to `HeadersTimeoutError` if `aiservice` is too slow).

### C. Python `aiservice` (FastAPI & CrewAI)

1.  **API Endpoint (`aiservice/app/api/api_v1/endpoints/ai_operations.py`)**
    *   **Route:** `/rewrite-content`
    *   **Function:** Handles incoming HTTP requests for content rewrite.
    *   **Input:** `RewriteContentRequest` Pydantic model (containing `content_blocks_to_rewrite: List[ContentBlock]`).
    *   **Output:** `RewriteContentResponse` Pydantic model (containing `ai_rewritten_content_blocks: List[ContentBlock]`).
    *   **Key Logic:**
        *   Validates the input using Pydantic.
        *   Creates an instance of `ContentRewriteCrewManager`.
        *   Calls the `manager.run()` method with the input data.
        *   Handles exceptions and formats the response.

2.  **Crew Manager (`aiservice/app/crews/content_rewrite_crew.py`)**
    *   **Class:** `ContentRewriteCrewManager`
    *   **Function:** Orchestrates the entire rewrite process using CrewAI. It prepares inputs for the crew, kicks off the crew, and processes its results.
    *   **`run()` Method:**
        *   **Input:** `rewrite_input: RewriteContentRequest`.
        *   **Output:** `RewriteContentResponse`.
        *   **Key Logic:**
            1.  **Preprocessing (ContentPrepperAgent's intended role, currently in `run()`):**
                *   Iterates through `rewrite_input.content_blocks_to_rewrite`.
                *   Concatenates content from `text` type blocks into `concatenated_text`.
                *   Extracts metadata from `image` type blocks (if `block.image_id_ref` is present) into `essential_image_metadata`. This list contains dictionaries with `image_id_ref`, `gcs_url`, `alt_text`, `caption`, `llm_description`.
                *   Logs this preprocessed data.
            2.  **Crew Setup:** Initializes the CrewAI `Crew` with defined agents and tasks.
            3.  **Crew Kickoff:** Calls `self.crew.kickoff(inputs=crew_kickoff_inputs)`.
                *   `crew_kickoff_inputs` includes:
                    *   `concatenated_text`
                    *   `essential_image_metadata_for_summarizer_prompt` (JSON string of `essential_image_metadata`)
                    *   `reconstructor_image_metadata_list_json` (JSON string of `essential_image_metadata`)
                    *   `reconstructor_document_id`
                    *   `reconstructor_operation`: "reconstruct_content_from_summary"
            4.  **Result Processing:**
                *   Retrieves the output from the last task of the crew (expected to be from `OutputReconstructionAgent`).
                *   **Attempts to get a Python list directly from `last_task_output_obj.raw` (if `last_task_output_obj.type == 'tool'`).** (This was a recent addition to try and get the direct tool output).
                *   If not a direct list, it converts `last_task_output_obj.output` (or `last_task_output_obj.exported_output`, or `str(last_task_output_obj)`) to a string.
                *   Calls `_try_json_parse()` to parse this string (after stripping markdown fences) into `candidate_data` (expected to be a list of dictionaries).
                *   Calls `safe_parse_to_content_blocks()` to validate `candidate_data` against the `ContentBlock` Pydantic model.
                *   Returns the validated list of `ContentBlock` objects.
    *   **`_try_json_parse()` Method:** Attempts to parse a string into JSON, with added logic to strip markdown code fences (```json ... ``` or \`...\`).
    *   **`safe_parse_to_content_blocks()` Method:** Iterates through a list of dictionaries, tries to validate each as a `ContentBlock`, and logs errors for invalid items.

3.  **Agents Factory & Agent Definitions (`aiservice/app/agents/content_rewrite_agents.py`)**
    *   **Class:** `ContentRewriteAgentsFactory`
    *   **Function:** Creates and configures the agents used in the rewrite crew.
    *   **Agents Created:**
        *   **`ContentPrepperAgent` (Conceptual):** Its logic is currently implemented *within* the `ContentRewriteCrewManager.run()` method before crew kickoff. The V2.6 plan envisions this as a distinct, non-LLM agent.
            *   **Current Python Logic (in `ContentRewriteCrewManager`):** Iterates `content_blocks_to_rewrite`, builds `concatenated_text` and `essential_image_metadata`. No LLM.
        *   **`SummarizationAgent`:**
            *   **LLM Used:** `Gemini-2.5-flash` (via `ChatOpenAI` wrapper configured for Gemini).
            *   **Goal:** Generate a concise summary of the text, referring to images by identifiers.
            *   **Tools:** `OptimizedLLMInteractionTool` (likely a wrapper for direct LLM calls, but not explicitly detailed as a separate tool in recent debugging).
            *   **Prompt:** (Embedded in `task_summarize_content` in `content_rewrite_crew.py`) - A detailed prompt instructing the LLM on summarization, image placeholder usage (`[IMAGE_REF: <image_id_ref>]`), tone, and output format (single continuous string).
        *   **`OutputReconstructionAgent`:**
            *   **LLM Used:** `Gemini-2.5-flash`.
            *   **Goal:** Take the summarized text (with image placeholders) and the `essential_image_metadata`, and reconstruct the final `List[ContentBlock]`.
            *   **Tools:** `FastContentBlockProcessorTool`.
            *   **Prompt:** (Embedded in `task_reconstruct_output` in `content_rewrite_crew.py`) - Instructs the agent to use the `FastContentBlockProcessorTool` with the summarized text and image metadata to generate the structured content blocks. Recent changes emphasize it should take the tool's list output, convert it to JSON, and return that string.
            *   **`max_iter=1`**: To force tool use and direct output.

4.  **Tasks (`aiservice/app/crews/content_rewrite_crew.py`)**
    *   **`task_summarize_content` (for `SummarizationAgent`):**
        *   **Context:** None (takes direct inputs from `crew_kickoff_inputs`).
        *   **Inputs:** `concatenated_text`, `essential_image_metadata_for_summarizer_prompt`.
        *   **Instructions:** Detailed prompt for summarization, image placeholder usage.
        *   **`expected_output`:** "A single string containing the summarized text... This string will be used to populate the 'summary_text' field of the 'SummarizerTaskOutput' Pydantic model by the system."
        *   **`output_pydantic=SummarizerTaskOutput`**: The agent's string output is wrapped in this Pydantic model.
    *   **`task_reconstruct_output` (for `OutputReconstructionAgent`):**
        *   **Context:** `task_summarize_content`.
        *   **Inputs:**
            *   `operation`: "{{reconstructor_operation}}" (value: "reconstruct_content_from_summary")
            *   `summarized_text`: "{{context.summary_text}}" (accesses the string from `SummarizerTaskOutput`)
            *   `image_metadata_list_json`: "{{reconstructor_image_metadata_list_json}}"
            *   `document_id`: "{{reconstructor_document_id}}"
        *   **Instructions:** Critical instruction to use `FastContentBlockProcessorTool` ONCE, take its Python List of Dictionaries, CONVERT IT TO A JSON STRING, and return that JSON STRING.
        *   **`expected_output`:** "A JSON string representation of a list of ContentBlock dictionaries..."
        *   **`output_json=True`** (and `output_file=None`): Attempts to ensure the agent's final output is treated as JSON, though recent prompts focus on the agent itself producing the JSON *string*.

5.  **Tools (`aiservice/app/tools/insight_generation_tools.py`)**
    *   **`FastContentBlockProcessorTool`:**
        *   **Inherits from:** `BaseTool`.
        *   **Pydantic Input Schema:** `ContentProcessorToolInput` (fields: `operation: str`, `summarized_text: Optional[str]`, `image_metadata_list_json: Optional[str]`, `document_id: Optional[str]`).
        *   **`_run()` Method:**
            *   **Input:** `operation`, `summarized_text`, `image_metadata_list_json`, `document_id`.
            *   **Output:** `List[Dict]` (Python list of dictionaries, each representing a ContentBlock).
            *   **Core Python Logic for `operation == "reconstruct_content_from_summary"`:**
                1.  Parses `image_metadata_list_json` into a Python list of image metadata dictionaries.
                2.  Uses regex (`re.split(r"(\\[IMAGE_REF: [a-f0-9-]+\\])", summarized_text)`) to split the summary text by image placeholders.
                3.  Iterates through these segments:
                    *   If a segment is an image placeholder, it extracts the `image_id_ref`.
                    *   It finds the corresponding image metadata from the parsed list.
                    *   Constructs an image `ContentBlock` dictionary (setting `type='image'`, `gcs_url`, `caption`, `alt_text`, `image_id_ref`, `block_id`, `user_id`, `document_id`, `order_index`, and all other fields to `None` or appropriate values).
                    *   Appends this dictionary to `reconstructed_blocks`.
                    *   Marks the image metadata as "used."
                    *   If a segment is text, it constructs a text `ContentBlock` dictionary (setting `type='text'`, `content=segment.strip()`, `block_id`, `user_id`, `document_id`, `order_index`, and other fields to `None`).
                    *   Appends this to `reconstructed_blocks`.
                4.  Appends any "unused" images from `essential_image_metadata` to the end of `reconstructed_blocks`.
                5.  **Contains a temporary `sample_debug_return` which, if uncommented, returns a fixed list of 2 block dictionaries. The actual `return reconstructed_blocks_dicts` is currently often commented out for debugging.**
            *   **This tool does NOT use an LLM.** It's pure Python string manipulation, list processing, and dictionary creation.

## III. Current Challenges & Why it Might Be Slow/Fragile

1.  **LLM Calls (SummarizationAgent):** While `Gemini-2.5-flash` is fast, any LLM call introduces latency and variability. Network issues or model load can affect this. The prompt complexity for the `SummarizationAgent` is also a factor.
2.  **CrewAI Overhead:**
    *   **Agent "Thinking" Cycles:** Agents, especially if prompts are not perfectly clear or if `max_iter` is not set appropriately, can go through multiple internal "thought-action-observation" cycles. The `OutputReconstructionAgent` has `max_iter=1`, which is good.
    *   **Data Passing/Serialization:** CrewAI passes data between tasks. The `SummarizerTaskOutput` Pydantic model is used, and its `summary_text` is extracted. The final output from `OutputReconstructionAgent` has been a major point of debugging regarding its format (direct list, JSON string, TaskOutput object attributes).
3.  **Output Parsing in `ContentRewriteCrewManager`:**
    *   The manager has complex logic to extract the final list of dictionaries from the last task's output. It tries `last_task_output_obj.raw`, then `last_task_output_obj.output`, then `exported_output`, then `str(last_task_output_obj)`. This complexity arises from inconsistencies in how CrewAI task outputs are structured, especially when tools are involved or when agents are explicitly asked to produce JSON.
    *   The `_try_json_parse` and subsequent Pydantic validation (`safe_parse_to_content_blocks`) add processing time and are potential failure points if the string isn't perfect JSON or if the structure doesn't match `ContentBlock`. The "Unterminated string" JSON errors were a recent manifestation of this.
4.  **`FastContentBlockProcessorTool` Complexity:** While pure Python, the string splitting, regex, and iteration logic in `reconstruct_content_from_summary` can be intricate. If the LLM's summary format (image placeholders) deviates even slightly from what the regex expects, it could lead to incorrect block construction or errors.
5.  **Timeout Propagation:** The 5-minute `HeadersTimeoutError` suggests the entire Python `aiservice` process for a rewrite is taking too long. This could be any of the above points accumulating, or a specific part (like an LLM call or a complex loop in the tool) taking excessively long. The current `sample_debug_return` in the tool helps isolate if the tool's *actual data processing* is the cause vs. the CrewAI mechanics.
6.  **Fragility of LLM Output for Reconstruction:** The `OutputReconstructionAgent` (or more accurately, its `FastContentBlockProcessorTool`) relies on the `SummarizationAgent` producing text with perfectly formatted image placeholders (`[IMAGE_REF: <id>]`). If the LLM deviates, the reconstruction logic will break or produce incorrect results. This is a common challenge in multi-step LLM workflows where structured output is required from an LLM.

## IV. Can `task_reconstruct_output` be Purely Python?

**Yes, and it *already is* in terms of its core logic.**

*   The **`FastContentBlockProcessorTool`** used by the `OutputReconstructionAgent` is **100% Python code**. It takes the summarized string (from the `SummarizationAgent`'s LLM call) and the image metadata list, and performs all reconstruction logic using Python's string manipulation, regex, and list/dictionary operations.
*   The `OutputReconstructionAgent` itself *is* an LLM-based agent, but its **sole mandated job** (especially with recent prompt updates) is to:
    1.  Receive the `summarized_text` and `image_metadata_list_json`.
    2.  Call the `FastContentBlockProcessorTool` with these inputs.
    3.  Take the `List[Dict]` returned by the tool.
    4.  Convert this `List[Dict]` into a JSON string.
    5.  Return that JSON string.

The LLM part of the `OutputReconstructionAgent` is *not* supposed to be doing any creative work, re-interpretation, or further processing of the content itself. It's acting as a constrained "tool user and data formatter."

**The reason it's an LLM agent currently is primarily due to the CrewAI framework, where tasks are typically assigned to agents that can use tools.**

**To make the reconstruction step "more purely Python" within the current CrewAI structure, you could:**

1.  **Ensure the `OutputReconstructionAgent` prompt is extremely rigid:** As we've been trying, making it absolutely clear its only job is to call the tool and format the output as a JSON string. `max_iter=1` helps.
2.  **Consider a Custom CrewAI Tool that directly returns a JSON string:** If the `FastContentBlockProcessorTool` itself was modified to do `json.dumps(reconstructed_blocks_dicts)` as its final step and return that string, the agent's job would be even simpler: just return the tool's string output.
3.  **Alternative: Post-Crew Processing:** If the `OutputReconstructionAgent`'s task reliably returned the raw `List[Dict]` from the tool (e.g., if `last_task_output_obj.raw` consistently held this), then the `ContentRewriteCrewManager` could do the `json.dumps()` itself if a JSON string is needed, or directly use the list for Pydantic validation. The main challenge has been reliably *getting* that raw `List[Dict]` out of the `TaskOutput` object.

The desire to avoid an LLM for the reconstruction logic itself is sound, and the `FastContentBlockProcessorTool` already achieves this. The surrounding issues are more about CrewAI mechanics and ensuring the LLM agent strictly adheres to its role as a simple tool executor and data passer for this specific task. 