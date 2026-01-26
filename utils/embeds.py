import json
import disnake

from config import *


def format_money(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "{:,}".format(int(value)).replace(",", ".")
    return value

class EmbedBuilder:
    def __init__(self, filename="data/embeds.json"):
        self.filepath = BASE_DIR / filename
        self.data = self._load_data()
        
    def _load_data(self):
        if not self.filepath.exists():
             return {}
        with open(self.filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_embed(self, name: str, **kwargs) -> disnake.Embed:
        raw_data = self.data.get(name)
        
        if not raw_data:
            return disnake.Embed(description=f"Embed '{name}' not found in config.", color=disnake.Color.red())

        ignore_keys = {
            "user_id", "sender_id", "target_id", "owner_id", "id", 
            "channel_id", "message_id", "guild_id",
            "created_at", "joined_at", "date", "release_time", "timestamp",
            "bought_at", "end_time", "due_time", "start_time", "due_date",
            "expires_at" 
        }
        
        formatted_kwargs = {}
        for k, v in kwargs.items():
            if k in ignore_keys or k.endswith("_id") or not isinstance(v, (int, float)):
                formatted_kwargs[k] = v
            else:
                formatted_kwargs[k] = format_money(v)

        embed = disnake.Embed(
            title=raw_data.get("title", "").format(**formatted_kwargs),
            description=raw_data.get("description", "").format(**formatted_kwargs),
            url=raw_data.get("url", "").format(**formatted_kwargs) if raw_data.get("url") else None
        )

        if "color" in raw_data:
            color_str = raw_data["color"]
            if isinstance(color_str, str):
                embed.color = int(color_str.replace("#", ""), 16)
            else:
                embed.color = color_str

        if "thumbnail" in raw_data:
            thumb_data = raw_data["thumbnail"]
            if isinstance(thumb_data, dict):
                thumb_url = thumb_data.get("url", "")
            else:
                thumb_url = thumb_data
            
            if thumb_url:
                embed.set_thumbnail(url=thumb_url.format(**formatted_kwargs))

        if "image" in raw_data:
            img_data = raw_data["image"]
            if isinstance(img_data, dict):
                img_url = img_data.get("url", "")
            else:
                img_url = img_data
            
            if img_url:
                embed.set_image(url=img_url.format(**formatted_kwargs))

        if "footer" in raw_data:
            footer_text = raw_data["footer"].get("text", "").format(**formatted_kwargs)
            footer_icon = raw_data["footer"].get("icon_url", "").format(**formatted_kwargs)
            embed.set_footer(text=footer_text, icon_url=footer_icon)

        if "author" in raw_data:
            author_name = raw_data["author"].get("name", "").format(**formatted_kwargs)
            author_url = raw_data["author"].get("url", "").format(**formatted_kwargs) if raw_data["author"].get("url") else None
            author_icon = raw_data["author"].get("icon_url", "").format(**formatted_kwargs)
            embed.set_author(name=author_name, url=author_url, icon_url=author_icon)

        if "fields" in raw_data:
            for field in raw_data["fields"]:
                name = field.get("name", "").format(**formatted_kwargs)
                value = field.get("value", "").format(**formatted_kwargs)
                inline = field.get("inline", False)
                embed.add_field(name=name, value=value, inline=inline)

        if raw_data.get("timestamp") is True:
            embed.timestamp = disnake.utils.utcnow()

        return embed