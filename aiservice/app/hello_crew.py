import os
import litellm # Import litellm
litellm.set_verbose = True # Turn on litellm verbose mode
# litellm._turn_on_debug() # More detailed, can be very verbose - try verbose first

from crewai import Agent, Task, Crew, Process
from app.config.settings import settings # Import your settings

# --- Environment Setup ---
# Set environment variables for the LLMs based on the loaded settings.
# The primary key is Gemini. We set it for both GEMINI_API_KEY and OPENAI_API_KEY
# to handle libraries that might be hardcoded for OpenAI's variable name.
os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
os.environ["OPENAI_API_KEY"] = settings.gemini_api_key # For OpenAI-compatible endpoints

# If a specific OpenAI key is also provided, it will overwrite the compatible key.
if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key

def debug_env_vars():
    """Prints the state of relevant environment variables for debugging."""
    if "GEMINI_API_KEY" in os.environ:
        print(f"Environment: Gemini API Key IS SET.")
    else:
        print("Environment: Gemini API Key IS NOT SET.")
    
    if "OPENAI_API_KEY" in os.environ:
        print(f"Environment: OpenAI API Key IS SET.")
    else:
        print("Environment: OpenAI API Key IS NOT SET.")

# Explicitly set the OpenAI API key and model from settings for CrewAI
if settings.openai_api_key:
    print(f"Settings: Found OpenAI API Key (first 5, last 4): {settings.openai_api_key[:5]}...{settings.openai_api_key[-4:]}") # DEBUG
else:
    print("Settings: OpenAI API Key NOT FOUND in settings object.") # DEBUG

if "OPENAI_API_KEY" in os.environ:
    print(f"Environment: OpenAI API Key IS SET (first 5, last 4): {os.environ['OPENAI_API_KEY'][:5]}...{os.environ['OPENAI_API_KEY'][-4:]}") # DEBUG
else:
    print("Environment: OpenAI API Key IS NOT SET in os.environ before crew init.") # DEBUG

if settings.openai_model_name:
    os.environ["OPENAI_MODEL_NAME"] = settings.openai_model_name
# If you plan to use Gemini with CrewAI, you might need to set specific env vars for it too,
# e.g., GOOGLE_API_KEY, depending on how CrewAI/Langchain integrates with it.
# For now, this example focuses on OpenAI.

# Define a simple agent
hello_agent = Agent(
    role='Greeter',
    goal='Greet the user warmly and ask how their day is.',
    backstory=(
        "You are a friendly AI assistant created to make users feel welcome. "
        "You are enthusiastic and polite."
    ),
    verbose=True,
    allow_delegation=False,
    # If you want to explicitly pass the llm instance:
    # from langchain_openai import ChatOpenAI
    # llm = ChatOpenAI(model_name=settings.openai_model_name, temperature=0.7)
    # agent_llm=llm, # then pass it here
)

# Define a simple task
hello_task = Task(
    description='Greet the user. Ask about their day.',
    expected_output='A warm greeting and a question about the user\'s day.',
    agent=hello_agent
)

# Define a simple crew
hello_crew = Crew(
    agents=[hello_agent],
    tasks=[hello_task],
    process=Process.sequential,
    verbose=True
)

# --- Main Execution ---
def main():
    """
    Main function to run the Crew AI setup.
    """
    print("--- Starting Crew AI Hello World ---")
    debug_env_vars()

    # This is a placeholder for where you would assemble and run your crew.
    # For now, we are just verifying that the environment is set up correctly.
    
    # Example Crew Setup (commented out):
    #
    # research_task = Task(...)
    # writing_task = Task(...)
    # researcher_agent = Agent(...)
    # writer_agent = Agent(...)
    #
    # project_crew = Crew(
    #     tasks=[research_task, writing_task],
    #     agents=[researcher_agent, writer_agent],
    #     process=Process.sequential
    # )
    #
    # result = project_crew.kickoff()
    # print("\n--- Crew Execution Finished ---")
    # print("Result:", result)
    
    print("\n--- Crew AI Setup Verification Complete ---")


if __name__ == "__main__":
    if not settings.gemini_api_key:
        print("Error: GEMINI_API_KEY not found in .env file or settings.")
    else:
        main()

# To run this file directly (from the 'aiservice' directory):
# Make sure your virtual environment is activated.
# python app/hello_crew.py 