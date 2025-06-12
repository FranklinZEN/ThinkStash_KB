import asyncio
import platform
import uvicorn

if __name__ == "__main__":
    # On Windows, the default asyncio event loop (SelectorEventLoop) does not support
    # the subprocesses that Playwright requires to run browsers.
    # We must explicitly set the policy to use ProactorEventLoop before the
    # event loop is created. This must be done at the very start of the
    # application's entry point.
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # We programmatically start uvicorn, which will load the FastAPI app
    # from aiservice.main. This ensures our policy is in effect before uvicorn
    # sets up its own event loop.
    # RELOAD is set to False, as the reloader on Windows spawns a new process
    # that does not inherit the asyncio policy.
    uvicorn.run(
        "aiservice.main:app", 
        host="0.0.0.0", 
        port=8080, 
        reload=False
    ) 