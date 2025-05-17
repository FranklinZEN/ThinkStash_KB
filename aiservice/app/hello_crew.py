import os
import litellm # Import litellm
litellm.set_verbose = True # Turn on litellm verbose mode
# litellm._turn_on_debug() # More detailed, can be very verbose - try verbose first

from crewai import Agent, Task, Crew, Process
from app.config.settings import settings # Import your settings

# Explicitly set the OpenAI API key and model from settings for CrewAI
if settings.openai_api_key:
    print(f"Settings: Found OpenAI API Key (first 5, last 4): {settings.openai_api_key[:5]}...{settings.openai_api_key[-4:]}") # DEBUG
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
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

if __name__ == "__main__":
    print("Running Hello CrewAI Example...")
    print("--------------------------------")
    # Moved this print lower, after potential os.environ modification
    # print(f"Attempting to use OpenAI Model: {os.environ.get('OPENAI_MODEL_NAME', 'Not Set')}") 
    
    if not settings.openai_api_key:
        print("Error: OPENAI_API_KEY not found in .env file or settings.")
        print("Please ensure your API key is set correctly in aiservice/.env")
    else:
        # This print is now a bit redundant due to earlier debug prints but confirms settings object again
        # print(f"OpenAI API Key found (first 5 chars): {settings.openai_api_key[:5]}...")
        print(f"Attempting to use OpenAI Model from settings: {settings.openai_model_name}") # DEBUG
        try:
            result = hello_crew.kickoff()
            print("\n--------------------------------")
            print("Hello Crew Result:")
            print(result)
            print("--------------------------------")
        except Exception as e:
            print(f"An error occurred during crew kickoff: {e}")
            print("Please check the following:")
            print("- Your OpenAI API key in aiservice/.env is valid and has credit.")
            print(f"- The model name '{settings.openai_model_name}' is correctly specified and available.")
            print("- Network connectivity to OpenAI API.")

# To run this file directly (from the 'aiservice' directory):
# Make sure your virtual environment is activated.
# python app/hello_crew.py 