"""Centralized logging configuration for AIKodAnaliz"""
import logging
import os
from datetime import datetime
from pathlib import Path

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Log file path with date
LOG_FILE = LOGS_DIR / f'aikodanaliz_{datetime.now().strftime("%Y%m%d")}.log'

# Create logger
logger = logging.getLogger('AIKodAnaliz')
logger.setLevel(logging.DEBUG)

# Prevent duplicate handlers
if not logger.handlers:
    # File handler - Detailed logs
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler - Important logs only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def log_request(endpoint: str, method: str, **kwargs):
    """Log API request with details"""
    logger.info(f"API Request: {method} {endpoint} | Params: {kwargs}")

def log_response(endpoint: str, status_code: int, **kwargs):
    """Log API response with details"""
    logger.info(f"API Response: {endpoint} | Status: {status_code} | Data: {kwargs}")

def log_error(context: str, error: Exception, **kwargs):
    """Log error with context"""
    logger.error(f"Error in {context}: {str(error)} | Details: {kwargs}", exc_info=True)

def log_analysis(project_id: int, message: str, **kwargs):
    """Log analysis progress"""
    logger.info(f"Analysis [Project {project_id}]: {message} | {kwargs}")

def log_upload(project_id: int, message: str, **kwargs):
    """Log upload progress"""
    logger.info(f"Upload [Project {project_id}]: {message} | {kwargs}")

def log_ai_call(function_id: int, status: str, **kwargs):
    """Log AI API calls"""
    logger.info(f"AI Call [Function {function_id}]: {status} | {kwargs}")
