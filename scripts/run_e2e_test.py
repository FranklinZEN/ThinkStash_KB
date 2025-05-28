import os
import sys
import asyncio
import json
import uuid

# Determine the project root (E:\ThinkStash\aiservice)
# __file__ is aiservice\scripts\run_e2e_test.py
# os.path.dirname(__file__) is aiservice\scripts
# os.path.join(os.path.dirname(__file__), '..') is aiservice (this is our project root for the aiservice package)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# We need to add the parent of PROJECT_ROOT (E:\ThinkStash) to sys.path 
# so that Python can find the 'aiservice' package itself.
GRANDPARENT_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, '..')) # Should be E:\ThinkStash

if GRANDPARENT_ROOT not in sys.path:
    print(f"<<<<< ADDING {GRANDPARENT_ROOT} (as top-level package directory) TO SYS.PATH >>>>>")
    sys.path.insert(0, GRANDPARENT_ROOT)
else:
    print(f"<<<<< {GRANDPARENT_ROOT} (as top-level package directory) ALREADY IN SYS.PATH >>>>>")

print("<<<<< PYTHON SYS.PATH (POST-MODIFICATION) >>>>>")
for p_path in sys.path:
    print(p_path)
print("<<<<< END PYTHON SYS.PATH (POST-MODIFICATION) >>>>>")

# Attempt to import again for path checking
try:
    # Now, Python should look for E:\ThinkStash\aiservice\app\services\acquisition\web_service.py
    # The import statement itself uses 'aiservice' as the top-level package found in GRANDPARENT_ROOT
    import aiservice.app.services.acquisition.web_service
    print(f"<<<<< WebAcquisitionService MODULE LOADED FROM (diagnostic): {aiservice.app.services.acquisition.web_service.__file__} >>>>>")

    from aiservice.app.config.settings import settings
    print(f"<<<<< Settings object LOADED (diagnostic), type: {type(settings)} >>>>>")

    from aiservice.app.services.acquisition.web_service import WebAcquisitionService
    print(f"<<<<< WebAcquisitionService CLASS IMPORTED (diagnostic), type: {type(WebAcquisitionService)} >>>>>")
    
except ImportError as e:
    print(f"<<<<< FAILED TO IMPORT WebAcquisitionService/Settings POST sys.path MOD (diagnostic): {e} >>>>>")
    print(f"Ensure 'aiservice' package (under {GRANDPARENT_ROOT}) and its submodules are structured correctly with __init__.py files.")
except AttributeError as e:
    print(f"<<<<< IMPORT OK, BUT ATTRIBUTE ERROR (diagnostic - likely __file__ not on namespace): {e} >>>>>")


# ========= Your original script's imports should start around here =========
import time

from aiservice.app.config.settings import settings
from aiservice.app.models.orchestration_models import OrchestrationInput
from aiservice.app.services.orchestrator import ParallelOrchestrator
from aiservice.app.services.routing_service import RoutingService
from aiservice.app.services.acquisition.web_service import WebAcquisitionService # This should be the correct path now
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService
from aiservice.app.services.acquisition.file_service import FileAcquisitionService
from aiservice.app.services.processing.image_processing_service import ImageProcessingService
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService
from aiservice.app.tools.llm_tools import ImageAnalysisLLMTool, ContentStructuringLLMHelper
from aiservice.app.crews.minimal_crew import MinimalLLMCrew
from langchain_openai import ChatOpenAI

# ========= Test Case Setup =========
# Ensure uuid is imported right before its first use for this specific debug
import uuid 

pdf_file_path = r"E:\ThinkStash\documentation\AI Agents Testing File\Embedding-Based Retrieval for Airbnb Search.pdf"
docx_file_path = r"E:\ThinkStash\documentation\AI Agents Testing File\Fulfillment Planning Deep Research Paper.docx"
md_file_path = r"E:\ThinkStash\documentation\AI Agents Testing File\Product Requirement Document - Knowledge Card System v3.8.md"

job_id_for_pdf_test = f"job_{uuid.uuid4().hex[:8]}" 
job_id_for_docx_test = f"job_{uuid.uuid4().hex[:8]}"
job_id_for_md_test = f"job_{uuid.uuid4().hex[:8]}"

# ... (rest of your script, potentially creating OrchestrationInput objects etc.) ... 