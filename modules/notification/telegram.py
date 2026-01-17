import logging
import asyncio
from telegram import Bot
from telegram.error import TelegramError

class TelegramLogsHandler(logging.Handler):
    def __init__(self, token: str, chat_id: str):
        super().__init__()
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        self.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
        self.setFormatter(formatter)
        self.loop = asyncio.new_event_loop()

    def emit(self, record):
        try:
            log_entry = self.format(record)
            # Run the coroutine in the event loop
            self.loop.run_until_complete(
                self._async_emit(log_entry)
            )
        except Exception as e:
            print(f"Error in Telegram logger: {e}")


    def _format_log_entry(self, message: str) -> str:
        """Format log message with Markdown for better Telegram display"""
        try:
            # Split into parts (assuming format: "timestamp - name - level - message")
            parts = message.split(' | ', 3)
            if len(parts) == 4:
                timestamp, name, level, msg = parts
                # Add emojis based on log level
                level_emoji = {
                    'DEBUG': '🔍',
                    'INFO': 'ℹ️',
                    'WARNING': '⚠️',
                    'ERROR': '❌',
                    'CRITICAL': '🔥'
                }.get(level.upper(), '📝')
                
                return f"""
{level_emoji} *{level}* | `{name}`
⏰ `{timestamp}`
📝 {msg}
"""
        except Exception:
            pass
        return message  # Fallback to original message if formatting fails

    async def _async_emit(self, message: str):
        """Async helper method to send the message"""
        try:
            formatted_message = self._format_log_entry(message)
            await self.bot.send_message(chat_id=self.chat_id, text=formatted_message)
        except TelegramError as e:
            print(f"Failed to send log to Telegram: {e}")
        except Exception as e:
            print(f"Unexpected error in Telegram logger: {e}")

    def close(self):
        self.loop.close()
        super().close()

def setup_telegram_logger(token: str, chat_id: str, log_level=logging.INFO):
    """Setup and return a logger with Telegram handler"""
    logger = logging.getLogger('telegram_logger')
    
    # Prevent adding handlers multiple times
    if not logger.handlers:
        telegram_handler = TelegramLogsHandler(token, chat_id)
        telegram_handler.setLevel(log_level)
        logger.addHandler(telegram_handler)
        logger.setLevel(log_level)
    
    return logger