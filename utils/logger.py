import logging
import requests
import threading
import html
import config


class TelegramBotHandler(logging.Handler):
    def __init__(self, token, chat_id):
        super().__init__()
        self.token = token
        self.chat_id = chat_id
        
    def emit(self, record):
        try:
            log_entry = self.format(record)
            threading.Thread(target=self.send_msg, args=(log_entry, record.levelno, record.module, record.funcName)).start()
        
        except Exception:
            self.handleError(record)

    def send_msg(self, text, level, module_name, func_name):
        prefix = "🤖 <b>DISCORD BOT</b>"

        if level >= logging.CRITICAL:
            header = f"{prefix} | ☠️ <b>CRITICAL ERROR</b>"
        elif level >= logging.ERROR:
            header = f"{prefix} | 🔴 <b>RUNTIME ERROR</b>"
        elif level >= logging.WARNING:
            header = f"{prefix} | 🟠 <b>WARNING</b>"
        else:
            header = f"{prefix} | 🟢 <b>INFO</b>"

        clean_text = html.escape(text)

        msg_content = (
            f"{header}\n"
            f"📂 <b>Module:</b> <code>{module_name}.py</code>\n"
            f"⚙️ <b>Func:</b> <code>{func_name}</code>\n\n"
            f"<pre>{clean_text}</pre>"
        )

        if len(msg_content) > 4000:
            msg_content = msg_content[:4000] + "\n... (обрезано)</pre>"

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        
        try:
            requests.post(url, data={
                "chat_id": self.chat_id,
                "text": msg_content,
                "parse_mode": "HTML" 
            }, timeout=10)

        except Exception as e:
            print(f"❌ LOGGING ERROR: {e}")

def setup_logger():
    logger = logging.getLogger("discord_bot_logger")
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if config.TG_LOG_TOKEN and config.TG_LOG_CHAT_ID:
        tg_handler = TelegramBotHandler(config.TG_LOG_TOKEN, config.TG_LOG_CHAT_ID)
        tg_handler.setLevel(logging.WARNING) 
        tg_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(tg_handler)

    return logger

log = setup_logger()