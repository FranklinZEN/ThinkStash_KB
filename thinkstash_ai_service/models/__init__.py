# E:\ThinkStash\thinkstash_ai_service\models\__init__.py

from .web_content import WebContent  # Assuming WebContent is in web_content.py
from .structured_data import StructuredData # Assuming StructuredData is in structured_data.py
from .link import Link  # Assuming Link is in link.py
from .image import Image  # Assuming Image is in image.py

# Add any other models you want to expose directly from 'thinkstash_ai_service.models'
# For example, if you have a 'metadata.py' with a 'Metadata' class:
# from .metadata import Metadata

__all__ = [
    "WebContent",
    "StructuredData",
    "Link",
    "Image",
    # "Metadata", # if you add it above
]