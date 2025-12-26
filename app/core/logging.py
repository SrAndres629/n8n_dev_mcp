"""
Logging Configuration
Provides structured logging for all services.
"""
import logging
import sys
from typing import Optional


def setup_logging(name: str = "n8n_architect", level: Optional[int] = None) -> logging.Logger:
    """
    Configure and return a logger instance.
    
    Args:
        name: Logger name (typically module name)
        level: Logging level (defaults to INFO)
    
    Returns:
        Configured logger instance
    """
    if level is None:
        level = logging.INFO
    
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
    
    return logger


# Pre-configured loggers for each service
architect_logger = setup_logging("n8n.architect")
debugger_logger = setup_logging("n8n.debugger")
manager_logger = setup_logging("n8n.manager")
packages_logger = setup_logging("n8n.packages")
gateway_logger = setup_logging("n8n.gateway")
