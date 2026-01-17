import logging
import sys
from pathlib import Path
import os
from modules.notification.telegram import setup_telegram_logger

def setup_logger(name=__name__, log_level=logging.INFO, log_file="backup.log"):
    """Setup and return a configured logger instance."""
    logger = logging.getLogger(name)
    
    # Prevent adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if log_file is provided
    if log_file:
        log_path = Path(log_file).parent
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    telegram_token = os.environ["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

    if telegram_token and telegram_chat_id:
        try:
            telegram_logger = setup_telegram_logger(
                token=telegram_token,
                chat_id=telegram_chat_id,
                log_level=log_level
            )
            logger.addHandler(telegram_logger.handlers[0])
        except Exception as e:
            logger.error(f"Failed to setup Telegram logging: {e}")


    return logger

# Create a default logger instance
logger = setup_logger(os.environ["S3_PREFIX_PATH"])