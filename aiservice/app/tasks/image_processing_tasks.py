# Placeholder for tasks related to TS-AI-Reconstruct-4: Image Processing & Persistence Agent 

from crewai import Task, Agent # Assuming Agent for type hinting

class ImageProcessingTasks:
    """Defines tasks for the ImageProcessingPersistenceAgent.

    These tasks are responsible for managing image assets, including downloading
    images from URLs, uploading all acquired images to Google Cloud Storage (GCS),
    consolidating their metadata, and packaging this information for downstream use.
    """

    def image_downloading_task(self, agent: Agent, image_url_list: list[str]) -> Task:
        """Creates a Task for downloading images from a list of URLs.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            image_url_list: A list of URL strings pointing to images that need to be downloaded.

        Returns:
            Task: A CrewAI Task configured for image downloading.
        """
        return Task(
            description=f"Download images from the provided list of URLs (count: {len(image_url_list)}). "
                        "Handle potential errors during download (e.g., 404s, timeouts) and verify content types to ensure they are valid images.",
            expected_output="A list of dictionaries, each containing the 'original_url', the 'local_file_path' of the successfully downloaded image, "
                            "and a 'status' (e.g., 'success', 'error_not_found', 'error_download_failed') with an optional 'error_message'.",
            agent=agent
            # tools=[ImageDownloaderTool_instance]
        )

    def gcs_upload_task(self, agent: Agent, image_data_list: list[dict]) -> Task:
        """Creates a Task for uploading images to Google Cloud Storage (GCS).

        Args:
            agent: The CrewAI agent assigned to execute this task.
            image_data_list: A list of dictionaries, where each dictionary represents an image to upload.
                             Each dict should contain information like 'local_path' (for locally available images)
                             or 'image_bytes' and 'original_filename' or 'source_identifier' to help generate a unique GCS name.

        Returns:
            Task: A CrewAI Task configured for GCS image upload.
        """
        return Task(
            description=f"Upload images to Google Cloud Storage (GCS). Process a list of {len(image_data_list)} image data items. "
                        "For each image, generate a unique name for GCS storage. Set appropriate GCS metadata (e.g., content type).",
            expected_output="A list of dictionaries, each corresponding to an input image, containing the 'original_identifier' (e.g., local path or source URL), "
                            "the 'gcs_url' of the uploaded image, and an 'upload_status' (e.g., 'success', 'error_upload_failed') with an optional 'error_message'.",
            agent=agent
            # tools=[GCSUploadTool_instance]
        )

    def metadata_consolidation_task(self, agent: Agent, all_image_info_list: list[dict]) -> Task:
        """Creates a Task for consolidating all available metadata for each processed image.

        This involves gathering all information collected about an image (from parsing, LLM analysis,
        GCS upload, etc.) and standardizing it, including determining image dimensions and MIME type if needed.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            all_image_info_list: A list of dictionaries, where each dictionary contains various pieces of 
                                 information about an image (e.g., original_source_identifier, local_path, 
                                 gcs_url, alt_text, caption, llm_description, etc.).

        Returns:
            Task: A CrewAI Task configured for image metadata consolidation.
        """
        return Task(
            description=f"Consolidate all available metadata for each of the {len(all_image_info_list)} images. "
                        "For each image, gather its GCS URL, original source identifier, any extracted alt text or captions, "
                        "LLM-generated descriptions or context, and determine image dimensions (width, height) and precise MIME type (e.g., using Pillow) if not already known. "
                        "Create a standardized ProcessedImageData object/dictionary for each image.",
            expected_output="A list of ProcessedImageData objects/dictionaries, each comprehensively describing an image "
                            "(including 'gcs_url', 'original_source_identifier', 'alt_text', 'caption', 'llm_description', 'dimensions', 'mime_type', etc.). "
                            "Report status for each image if consolidation encounters issues.",
            agent=agent
            # tools=[ImageMetadataTool_instance] # (e.g., using Pillow)
        )

    def package_image_processing_output_task(self, agent: Agent, processed_images_data_list: list[dict]) -> Task:
        """Creates a Task to package the final list of processed image data.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            processed_images_data_list: A list of ProcessedImageData objects/dictionaries from the metadata_consolidation_task.

        Returns:
            Task: A CrewAI Task configured for packaging the image processing output.
        """
        return Task(
            description="Package the final list of ProcessedImageData objects/dictionaries that resulted from all image processing and persistence steps.",
            expected_output="A dictionary containing a single key, e.g., 'processed_images_list', which holds the list of ProcessedImageData objects/dictionaries.",
            agent=agent
        ) 