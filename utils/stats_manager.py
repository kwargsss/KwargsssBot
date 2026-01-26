import json
import datetime

from config import *


STATS_FILE = BASE_DIR / "data" / "stats.json"

class StatsHandler:
    def __init__(self):
        self.data = self.load()
    
    def load(self):
        if not STATS_FILE.exists():
            return self._default_data()
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults = self._default_data()
                for key, val in defaults.items():
                    if key not in data:
                        data[key] = val
                return data
        except:
            return self._default_data()

    def _default_data(self):
        return {
            "date": "", 
            "messages_today": 0, 
            "commands_today": 0,
            "recent_commands": []
        }

    def save(self):
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def check_new_day(self):
        now = datetime.datetime.now() 
        today_str = now.strftime("%Y-%m-%d")
        
        if self.data["date"] != today_str:
            self.data["date"] = today_str
            self.data["messages_today"] = 0
            self.data["commands_today"] = 0
            self.save()
            return True
        return False

    def add_message(self):
        self.check_new_day()
        self.data["messages_today"] += 1
        self.save()

    def add_command(self, user, channel, command_name, success=True):
        self.check_new_day()
        self.data["commands_today"] += 1 
        
        entry = {
            "user": user,
            "channel": channel,
            "command": command_name,
            "time": datetime.datetime.now().strftime("%H:%M"),
            "status": success 
        }
        
        self.data["recent_commands"].insert(0, entry)
        
        if len(self.data["recent_commands"]) > 10:
            self.data["recent_commands"] = self.data["recent_commands"][:10]
            
        self.save()

stats = StatsHandler()