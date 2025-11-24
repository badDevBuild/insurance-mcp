import sys
import logging
from typing import Optional

def setup_logging(name: str = "insurance_mcp", level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
    """
    Setup standard logging configuration.
    
    Args:
        name: Logger name
        level: Logging level (default: INFO)
        log_file: Optional path to write logs to file
        
    Returns:
        Configured Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent adding duplicate handlers if function is called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (Optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

# Create default logger
logger = setup_logging()

