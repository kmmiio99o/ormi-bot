import logging
import os
from datetime import datetime

def setup_logger():
    """Setup the logger for the bot"""
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)

    log_file = f"{log_dir}/{datetime.now().strftime('%Y-%m-%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger('bot')

def get_logger(name=None):
    """Get a logger with the specified name"""
    return logging.getLogger(name)
