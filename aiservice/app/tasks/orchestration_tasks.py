# Placeholder for tasks related to TS-AI-Reconstruct-0: Main Orchestration & Input Triage Agent 

from crewai import Task, Agent

class OrchestrationTasks:
    """Defines the various tasks managed and executed by the OrchestrationAgent.

    These tasks cover the initial stages of content processing, including input validation,
    content type detection, routing to appropriate acquisition agents, and handling
    the aggregation of results and errors.
    """

    def input_validation_task(self, agent: Agent, source_type: str, source_identifier: str) -> Task:
        """Creates a CrewAI Task for validating the input source.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            source_type: The type of the source (e.g., 'url', 'file').
            source_identifier: The identifier of the source (e.g., the URL string or file path).

        Returns:
            Task: A CrewAI Task configured for input validation.
        """
        return Task(
            description=f"Validate the input source. Source type: {source_type}, Identifier: {source_identifier}. "
                        "Normalize URLs (e.g., add https://, resolve common tracking parameters). "
                        "For files, perform basic validation of presence/accessibility.",
            expected_output="A dictionary containing validation status (True/False), normalized_identifier, "
                            "and an error message if validation failed.",
            agent=agent
        )

    def initial_content_triage_task(self, agent: Agent, source_type: str, source_identifier: str) -> Task:
        """Creates a CrewAI Task for initial content triage including type detection.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            source_type: The type of the source (e.g., 'url', 'file').
            source_identifier: The identifier of the source (e.g., the URL string or file path).

        Returns:
            Task: A CrewAI Task configured for initial content triage.
        """
        return Task(
            description=f"Perform initial triage for input: {source_identifier} (type: {source_type}). "
                        f"If URL, normalize it (ensure scheme). Then, use ContentTypeDetectionTool to detect content type. "
                        f"Final answer MUST be a dictionary: {{'normalized_identifier': '...', 'detected_content_type': '...', 'original_source_type': '...'}}.",
            expected_output="Dictionary with keys: normalized_identifier, detected_content_type, original_source_type.",
            agent=agent
        )

    def content_type_detection_task(self, agent: Agent, validated_identifier: str, source_type: str) -> Task:
        """Creates a CrewAI Task for detecting the content type of the validated input.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            validated_identifier: The validated and possibly normalized source identifier.
            source_type: The original type of the source (e.g., 'url', 'file') to help guide detection.

        Returns:
            Task: A CrewAI Task configured for content type detection.
        """
        return Task(
            description=f"Detect the content type of the validated input: {validated_identifier} (source type: {source_type}). "
                        "Use appropriate tools (e.g., python-magic for files, HEAD requests for URLs).",
            expected_output="A string representing the detected content type (e.g., 'pdf', 'docx', 'html', 'text', 'markdown', 'unknown').",
            agent=agent
        )

    def routing_task(self, agent: Agent, detected_content_type: str, original_source_identifier: str) -> Task:
        """Creates a CrewAI Task for routing to the appropriate content acquisition agent.

        Args:
            agent: The CrewAI agent assigned to execute this task (or to delegate from).
            detected_content_type: The content type detected by the content_type_detection_task.
            original_source_identifier: The original source identifier for processing.

        Returns:
            Task: A CrewAI Task configured for routing the content to the next stage.
        """
        return Task(
            description=f"Based on the detected content type ('{detected_content_type}'), determine and delegate to the appropriate content acquisition agent "
                        f"for source: {original_source_identifier}. This may involve invoking a sub-crew or a specific acquisition agent.",
            expected_output="Confirmation of successful delegation to the appropriate acquisition agent/crew, or an error if no suitable agent is found.",
            agent=agent
            # This task might involve invoking another crew or agent, which will be detailed later.
        )

    def error_aggregation_task(self, agent: Agent, errors_from_agents: list) -> Task:
        """Creates a CrewAI Task for aggregating errors from various agents in the pipeline.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            errors_from_agents: A list of error messages or structured error objects from other agents.

        Returns:
            Task: A CrewAI Task configured for error aggregation and reporting.
        """
        return Task(
            description=f"Aggregate and report errors from various agents. Implement structured logging "
                        f"and ensure clear error propagation. Errors received: {errors_from_agents}. Handle critical failures appropriately.",
            expected_output="A structured error report, a status update indicating partial success, or a notification of critical failure.",
            agent=agent
        )

    def output_aggregation_task(self, agent: Agent, processed_data_parts: list) -> Task:
        """Creates a CrewAI Task for aggregating outputs from all preceding agents into a final package.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            processed_data_parts: A list of data dictionaries or objects from various processing agents.

        Returns:
            Task: A CrewAI Task configured for output aggregation.
        """
        return Task(
            description=f"Aggregate outputs from all preceding agents (e.g., content extraction, image processing, AI insights) "
                        f"into a final 'processed_content_package'. Data parts received: {len(processed_data_parts)} items.",
            expected_output="A comprehensive 'processed_content_package' dictionary or object containing all extracted and generated content and metadata.",
            agent=agent
        )

    def fallback_strategy_task(self, agent: Agent, critical_failure_info: dict) -> Task:
        """Creates a CrewAI Task for implementing a fallback strategy in case of critical failure.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            critical_failure_info: A dictionary or object containing details about the critical failure.

        Returns:
            Task: A CrewAI Task configured for executing the fallback strategy.
        """
        return Task(
            description=f"Implement fallback strategy due to a critical failure. Package any partial data that might be available. "
                        f"Failure info: {critical_failure_info}. The goal is to provide a clear status and any retrievable information to the user or system.",
            expected_output="A data package containing partial data (if any), a clear error status, and a message explaining the failure.",
            agent=agent
        )

    def paywall_check_task(self, agent: Agent, url: str) -> Task:
        """Creates a task to check a given URL for paywalls using the PaywallDetectionTool."""
        return Task(
            description=f"Check the URL {url} for any paywalls using the PaywallDetectionTool. "
                        "Your final answer MUST be the direct dictionary output from the PaywallDetectionTool.",
            expected_output="A dictionary from PaywallDetectionTool with keys like 'status', 'details', 'url'.",
            agent=agent
        )

# Specific logic for how these tasks are chained, how their inputs/outputs are managed,
# and the actual execution flow will be defined within a Crew (e.g., in a main.py or a dedicated crew definition file).

# We will add more specific task parameters and logic as we develop the agents
# and understand the data flow better. 