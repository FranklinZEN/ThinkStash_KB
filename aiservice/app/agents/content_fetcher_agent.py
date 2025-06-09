from crewai import Agent
from app.tools.web_content_fetcher_tool import WebPageContentFetcherTool
from app.config.settings import settings # To potentially pass LLM config if needed for the agent itself
import os

# Set environment variables for the LLMs.
# The primary key is Gemini. We set it for both GEMINI_API_KEY and OPENAI_API_KEY
# to handle libraries that might be hardcoded for OpenAI's variable name.
os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
os.environ["OPENAI_API_KEY"] = settings.gemini_api_key # For OpenAI-compatible endpoints or library defaults

# If a specific OpenAI key is also provided (for a different agent, perhaps), set it.
if settings.openai_api_key:
    # This might overwrite the OPENAI_API_KEY set above, which is intentional
    # if you want to use a specific agent with OpenAI.
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key

# Instantiate the tool the agent will use
web_fetcher_tool = WebPageContentFetcherTool()

content_fetching_agent = Agent(
    role='Expert Web Content Extractor',
    goal='Accurately extract the main textual content from a given URL. Provide only the extracted text or an error message if extraction fails.',
    backstory=(
        "You are a specialist in web content extraction, developed to meticulously analyze web pages. "
        "You navigate through HTML structures to pinpoint and retrieve the core information, effectively filtering out irrelevant noise. "
        "Your primary function is to use the WebPageContentFetcherTool to get content. If the tool returns an error, you should report that error." 
        "If the tool returns content, you should return that content directly."
    ),
    tools=[web_fetcher_tool],
    verbose=True,
    allow_delegation=False,
    # By default, agents use the OPENAI_MODEL_NAME set in the environment or a Crew-level default.
    # You could explicitly pass an LLM here if needed:
    # from langchain_openai import ChatOpenAI
    # llm = ChatOpenAI(model_name=settings.openai_model_name, temperature=0.7)
    # llm=llm,
)

# Example of how to test this agent with a task (we'll do this more formally in a crew later)
if __name__ == '__main__':
    from crewai import Task, Crew, Process

    print("Testing ContentFetchingAgent with a Crew...")
    # test_url = "https://www.example.com"
    test_url = "https://medium.com/walmartglobaltech/creating-web-app-for-file-interactions-using-rag-a-developers-guide-aeaed58de536" # A more realistic article
    # test_url_bad = "https://www.example.com/nonexistentpage123xyz"

    # Task for the agent
    # The agent will use its LLM to understand this task and decide to use its tool.
    # The input to the task (`inputs` in crew.kickoff) should provide the necessary info (the URL).
    fetch_content_task = Task(
        description=f"The user has provided a URL in the inputs. Your task is to fetch the main textual content from this specific URL: {{url}}. Your final answer must be only the fetched content or an error string.",
        expected_output=(
            "The primary textual content from the specified URL. "
            "If an error occurs during fetching (e.g., 404, timeout, or no content found), "
            "the output should be a string describing the error."
        ),
        agent=content_fetching_agent,
        # Human input can be used if the agent needs clarification, but for this simple task, it shouldn't be needed.
        # human_input=True 
    )

    # Create a simple crew to run this one agent and task
    content_crew = Crew(
        agents=[content_fetching_agent],
        tasks=[fetch_content_task],
        process=Process.sequential,
        verbose=True # Changed from 2 to True
    )

    print(f"\nAttempting to fetch content from: {test_url}")
    try:
        # The inputs dictionary key should match what the task description implies the agent needs.
        # The agent's LLM will interpret the task description and use the tool with the provided URL.
        # The `url` key in the inputs dict here is a common convention for such tasks.
        results = content_crew.kickoff(inputs={'url': test_url})
        
        print("\n--------------------------------")
        print("Content Fetching Crew Result:")
        print(results)
        print("--------------------------------")
    except Exception as e:
        print(f"An error occurred during crew kickoff: {e}")

    # print(f"\nAttempting to fetch content from: {test_url_bad}")
    # try:
    #     results_bad = content_crew.kickoff(inputs={'url': test_url_bad})
    #     print("\n--------------------------------")
    #     print("Content Fetching Crew Result (for bad URL):")
    #     print(results_bad)
    #     print("--------------------------------")
    # except Exception as e:
    #     print(f"An error occurred during crew kickoff for bad URL: {e}") 