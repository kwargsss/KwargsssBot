import disnake
import json
import os
import asyncio
import datetime

from disnake.ext import commands


class EmbedDebug(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.path = os.path.join("data", "embeds.json")

    def load_embeds(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    dummy_data = {
        "text": "Пример текста ошибки или сообщения.",
        "time": "5 мин.",
        "author_avatar": "https://cdn.discordapp.com/embed/avatars/0.png",
        "moderator_avatar": "https://cdn.discordapp.com/embed/avatars/1.png",
        "user_avatar": "https://cdn.discordapp.com/embed/avatars/2.png",
        "icon_url": "https://cdn.discordapp.com/embed/avatars/3.png",
        "thumbnail_url": "https://cdn.discordapp.com/embed/avatars/4.png",
        
        "user_mention": "@User",
        "moderator_mention": "@Admin",
        "channel_mention": "#general",
        "sender_mention": "@Sender",
        "target_mention": "@Target",
        "author_mention": "@Author",
        "user1": "Romeo",
        "user2": "Juliet",
        "user1_mention": "@Romeo",
        "user2_mention": "@Juliet",

        "balance": "50,000",
        "amount": "1,500",
        "needed": "2,000",
        "new_bank": "150,000",
        "new_money": "2,500",
        "price": "10,000",
        "sell_price": "5,000",
        "fee": "150",
        "received": "1,350",
        "bet": "500",
        "prize": "1,000",
        "fine": "200",
        "total": "55,000",
        "percent": "5",
        "days": "30",
        "max_loan": "100,000",
        "taken": "20,000",
        "left": "15,000",
        "share": "25,000",
        "original_price": "20,000",
        "ratio": "50",

        "reason": "Нарушение правил сервера (тест).",
        "time_str": "2 часа",
        "job_name": "Программист",
        "job_tier": "3",
        "xp_gain": "150",
        "total_xp": "1250",
        "phrase": "Вы успешно закрыли задачу!",
        "source_type": "Наличные",
        "target_type": "Банк",
        "biz_name": "Starbucks",
        "house_name": "Элитный коттедж",
        "house_type": "Дом",
        "game_name": "Рулетка",
        "target_name": "Магазин 24/7",
        "role_name": "VIP",
        "role_color": "#FF0000",
        "display_name": "Tester",
        "user_display_name": "Tester",
        "bio": "Это пример биографии пользователя.",

        "history_text": "1. Ban | 2024-01-01 | Spam\n2. Mute | 2024-01-02 | Flood",
        "roles": "@Member, @VIP, @Admin",
        "upgrades": "🔹 Склад: Ур. 2\n🔹 Персонал: Ур. 5",
        "status": "🟢 Работает",
        "economy_status": "Экономика стабильна",
        "m1_stats": "1,000,000 $",
        "inequality_stats": "Джини: 0.35",
        "assets_stats": "Домов: 15",
        "owners": "@User1, @User2",
        "imp_name": "Сейф ур. 2",
        "filter_name": "Все наказания",

        "expires_at": int(datetime.datetime.now().timestamp() + 3600),
        "created_at": int(datetime.datetime.now().timestamp()),
        "joined_at": int(datetime.datetime.now().timestamp()),
        "release_time": int(datetime.datetime.now().timestamp() + 600),
        "end_time": int(datetime.datetime.now().timestamp() + 86400),
        "due_time": int(datetime.datetime.now().timestamp() + 604800),
        "date": datetime.date.today().strftime("%Y-%m-%d"),

        "limit": "5",
        "warn_count": "2",
        "warns_active": "1",
        "mutes_total": "5",
        "bans_total": "0",
        "count": "3",
        "lvl": "5",
        "max_lvl": "10",
        "level": "5",
        "xp": "500",
        "rate": "4.8",
        "rating": "A+",
        "roles_count": "5",
        "user_id": "123456789",
        "supplies": "500",
        "max_storage": "1000",
        "storage_progress": "🟦🟦🟦⬜⬜⬜⬜⬜⬜⬜",
        "levels_info": "Уровень 1 -> 2",
        "tenants_count": "2",
        "max_tenants": "5",
        "slots": "10",
        "bitrate": "64",
        "deposit_info": "Активен (50k)",
        "loan_info": "Нет долгов",
        "recommendation": "Повысить налоги",

        "player_score": "21",
        "dealer_score": "18",
        "player_hand": "🃏 Туз Черви\n🃏 Король Пики",
        "dealer_hand": "🃏 10 Буби\n🃏 8 Трефы",
        
        "user": "BadGuy#1234",
        "author": "Admin#0001",
    }

    def process_text(self, text):
        if isinstance(text, str):
            text = text.strip()
            try:
                return text.format(**self.dummy_data)
            except KeyError as e:
                return text.replace("{" + str(e).strip("'") + "}", "UNKNOWN")
            except Exception:
                return text
        return text

    def clean_url(self, url_raw):
        if not url_raw:
            return None
        
        url = self.process_text(url_raw)
        
        if not isinstance(url, str):
            return None
            
        url = url.strip()
        if not url.startswith("http"):
            return None
            
        return url

    @commands.slash_command(name="debug_embeds", description="Предпросмотр (Fix URL)")
    async def debug_embeds(self, inter: disnake.AppCmdInter, key_name: str = None):
        data = self.load_embeds()
        
        if key_name:
            subset = {key_name: data.get(key_name)}
            if not subset[key_name]: return await inter.response.send_message("❌ Ключ не найден", ephemeral=True)
            await inter.response.send_message(f"🔍 Просмотр: `{key_name}`")
        else:
            subset = data
            await inter.response.send_message("🚀 Генерация...", ephemeral=True)

        for key, value in subset.items():
            if key == "_comments" or not isinstance(value, dict): continue

            try:
                emb = disnake.Embed(
                    title=self.process_text(value.get("title")),
                    description=self.process_text(value.get("description")),
                    color=int(value.get("color", "000000"), 16) if "color" in value else 0x2b2d31
                )
                
                if value.get("timestamp"):
                    emb.timestamp = datetime.datetime.now()

                if "footer" in value:
                    emb.set_footer(
                        text=self.process_text(value["footer"].get("text")),
                        icon_url=self.clean_url(value["footer"].get("icon_url"))
                    )
                
                if "thumbnail" in value:
                    raw = value["thumbnail"]
                    url_str = raw if isinstance(raw, str) else raw.get("url")
                    valid_url = self.clean_url(url_str)
                    if valid_url:
                        emb.set_thumbnail(url=valid_url)

                if "image" in value:
                    raw = value["image"]
                    url_str = raw if isinstance(raw, str) else raw.get("url")
                    valid_url = self.clean_url(url_str)
                    if valid_url:
                        emb.set_image(url=valid_url)

                if "fields" in value:
                    for field in value["fields"]:
                        emb.add_field(
                            name=self.process_text(field.get("name", "No Title")),
                            value=self.process_text(field.get("value", "No Value")),
                            inline=field.get("inline", True)
                        )

                msg_content = f"🔑 **{key}**"
                if key_name:
                    await inter.followup.send(content=msg_content, embed=emb)
                else:
                    await inter.channel.send(content=msg_content, embed=emb)
                    await asyncio.sleep(1.0)

            except Exception as e:
                print(f"Error in {key}: {e}")
                try:
                    await inter.channel.send(f"⚠️ Ошибка рендера `{key}`: {e}")
                except:
                    pass

def setup(bot):
    bot.add_cog(EmbedDebug(bot))