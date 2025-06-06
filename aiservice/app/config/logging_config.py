import logging
import sys
from pythonjsonlogger import jsonlogger

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Configures and returns a logger instance with JSON formatting.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        # Using a common format string. Fields passed in 'extra' will be added automatically.
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

# Example of a basic configuration that could be expanded
# For example, to add file logging:
# file_handler = logging.FileHandler("app.log")
# file_handler.setFormatter(formatter)
# logger.addHandler(file_handler)

# Example of how to use it with extra fields:
# logger = get_logger(__name__)
# logger.info("User signed in", extra={'user_id': '12345', 'task_id': 'abc-123'}) 