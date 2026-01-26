import aiohttp
import asyncio
import json
import disnake
import psutil
import time
import io
import mimetypes
import socket
import ipaddress
import config
import re

from urllib.parse import urlparse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator
from utils.stats_manager import stats
from utils.logger import log






class WSPacket(BaseModel):
    action: str
    data: Dict[str, Any]

class DatabaseRequest(BaseModel):
    table: str

class SendMessagePayload(BaseModel):
    channel_id: int
    text: str

class EmbedButton(BaseModel):
    label: str
    url: str
    section_text: Optional[str] = None

class EmbedField(BaseModel):
    name: str
    value: str
    inline: bool = False

class SendEmbedPayload(BaseModel):
    channel_id: int
    type: str = "v1"
    title: Optional[str] = None
    description: Optional[str] = None
    color: str = "#000000"
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    fields: List[EmbedField] = []
    buttons: List[EmbedButton] = []
    content: Optional[str] = None
    image_desc: Optional[str] = ""
    file_url: Optional[str] = None
    file_name: Optional[str] = "document.pdf"

    @validator('color')
    def validate_color(cls, v):
        if v.startswith("#"): return v.replace("#", "")
        return v

class AdminReplyPayload(BaseModel):
    ticket_id: int
    admin_name: str
    text: str

class TicketActionPayload(BaseModel):
    ticket_id: int




class DashboardClient:
    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self.ws = None

    def _resolve_mentions(self, text, guild):
        if not text: return ""

        
        def replace_user(match):
            uid = int(match.group(1))
            member = guild.get_member(uid)
            name = member.display_name if member else "Unknown User"
            return f'<span class="mention">@{name}</span>'

        text = re.sub(r'<@!?(\d+)>', replace_user, text)

        
        def replace_role(match):
            rid = int(match.group(1))
            role = guild.get_role(rid)
            name = role.name if role else "Role"
            return f'<span class="mention role">@{name}</span>'

        text = re.sub(r'<@&(\d+)>', replace_role, text)

        
        def replace_channel(match):
            cid = int(match.group(1))
            chan = guild.get_channel(cid)
            name = chan.name if chan else "channel"
            return f'<span class="mention">#{name}</span>'

        text = re.sub(r'<#(\d+)>', replace_channel, text)

        return text

    async def start(self):
        self.running = True
        await self.bot.wait_until_ready()
        
        
        
        
        while self.running and not self.bot.is_closed():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(config.WS_URL, headers={"Authorization": config.API_SECRET}) as ws:
                        self.ws = ws
                        
                        log.info("🟢 Успешное подключение к Dashboard WebSocket")

                        
                        async def send_log_to_site(level, text):
                            if not ws.closed:
                                await ws.send_str(json.dumps({"type": "log", "level": level, "message": text}))

                        sync_task = asyncio.create_task(self._sync_loop(ws))

                        try:
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    await self._handle_message(ws, msg.data, send_log_to_site)
                                elif msg.type == aiohttp.WSMsgType.ERROR:
                                    log.warning("⚠️ WebSocket соединение разорвано (ERROR type)")
                                    break
                        finally:
                            sync_task.cancel()
                            self.ws = None

            except Exception as e:
                
                log.error(f"🔌 Ошибка подключения к Dashboard: {e}\nРеконнект через 5 сек...")
                self.ws = None
                await asyncio.sleep(5)

    async def send_event(self, event_type: str, data: Dict[str, Any]):
        if self.ws and not self.ws.closed:
            try:
                await self.ws.send_str(json.dumps({"type": event_type, "data": data}))
            except Exception as e: 
                log.error(f"📤 Ошибка отправки ивента {event_type}: {e}")

    async def _sync_loop(self, ws):
        while True:
            try:
                guild = self.bot.get_guild(config.TARGET_GUILD_ID)
                if guild:
                    channels = [{"id": str(c.id), "name": f"#{c.name}"} for c in guild.text_channels]
                    
                    tickets_data = []
                    if hasattr(self.bot.db, 'get_active_tickets'):
                        raw_tickets = await self.bot.db.get_active_tickets()
                        for t in raw_tickets:
                            member = guild.get_member(t['user_id'])
                            author_name = member.display_name if member else f"User {t['user_id']}"
                            tickets_data.append({
                                "ticket_id": t['ticket_id'],
                                "type": t['type'],
                                "topic": t['topic'],
                                "status": t['status'],
                                "created_at": t['created_at'],
                                "author": author_name
                            })

                    await ws.send_str(json.dumps({
                        "type": "sync_data",
                        "data": { "channels": channels, "members": [], "tickets": tickets_data }
                    }))
                    
                    stats.check_new_day()
                    chart_data = await self.bot.db.get_weekly_stats()
                    
                    
                    proc = psutil.Process()
                    await ws.send_str(json.dumps({
                        "type": "stats_update",
                        "data": {
                            "total_members": guild.member_count,
                            "online_members": sum(1 for m in guild.members if m.status != disnake.Status.offline),
                            "messages_today": stats.data["messages_today"],
                            "commands_today": stats.data["commands_today"],
                            "chart_data": chart_data,
                            "system": {
                                "cpu": psutil.cpu_percent(interval=None),
                                "ram": psutil.virtual_memory().percent,
                                "ping": round(self.bot.latency * 1000) if self.bot.latency else 0
                            }
                        }
                    }))
            except Exception as e:
                
                log.error(f"🔄 Ошибка цикла синхронизации: {e}")
            await asyncio.sleep(5)

    async def _handle_message(self, ws, raw_data, log_func):
        try:
            packet = WSPacket.model_validate_json(raw_data)
            action = packet.action
            
            if action == "get_database":
                req = DatabaseRequest(**packet.data)
                await self._handle_db_request(ws, req.table)

            elif action == "send_message":
                payload = SendMessagePayload(**packet.data)
                channel = self.bot.get_channel(payload.channel_id)
                if channel: await channel.send(payload.text)

            elif action == "send_embed":
                payload = SendEmbedPayload(**packet.data)
                if payload.type == "v2": await self._send_v2_components(payload, log_func)
                else: await self._send_embed(payload, log_func)

            elif action == "admin_reply":
                await self._handle_admin_reply(packet.data)

            elif action == "close_request":
                await self._handle_close_request(packet.data)

            elif action == "delete_request":
                await self._handle_delete_request(packet.data)

            elif action == "get_ticket_history":
                await self._handle_history_request(packet.data)

            elif action == "get_archived_tickets":
                await self._handle_get_archived_tickets()

        except Exception as e:
            await log_func("error", f"Handler Error: {e}")
            
            log.error(f"📨 Ошибка обработки входящего WS сообщения: {e}")

    
    async def _handle_get_archived_tickets(self):
        if not hasattr(self.bot, 'db'): return
        
        tickets_data = []
        try:
            
            async with self.bot.db.conn.execute("""
                SELECT ticket_id, type, topic, created_at, user_id, transcript_url 
                FROM tickets 
                WHERE status = 'deleted' 
                ORDER BY ticket_id DESC
            """) as cursor:
                rows = await cursor.fetchall()
                
                for row in rows:
                    t_id, t_type, t_topic, t_created, u_id, t_url = row
                    
                    user = self.bot.get_user(u_id)
                    if not user:
                        try: user = await self.bot.fetch_user(u_id)
                        except: pass
                    
                    author_display = user.display_name if user else f"User {u_id}"
                    author_avatar = user.display_avatar.url if user else "https://cdn.discordapp.com/embed/avatars/0.png"
                    
                    
                    final_url = t_url if t_url else "#"

                    tickets_data.append({
                        "ticket_id": t_id,
                        "type": t_type,
                        "topic": t_topic,
                        "author": author_display,
                        "avatar": author_avatar,
                        "created_at": t_created,
                        "url": final_url 
                    })
            
            await self.send_event("archived_tickets_list", tickets_data)
            
        except Exception as e:
            
            log.error(f"🗄️ Ошибка получения списка архивов: {e}")

    
    async def _handle_history_request(self, data: dict):
        ticket_id = data.get("ticket_id")
        
        if hasattr(self.bot, 'db'):
            ticket = await self.bot.db.get_ticket_by_id(ticket_id)
        else: return

        if not ticket: return
        channel = self.bot.get_channel(ticket['channel_id'])
        if not channel: return

        ticket_owner_id = ticket['user_id']
        messages_data = []

        try:
            async for msg in channel.history(limit=50, oldest_first=True):
                
                is_admin = (msg.author.id != ticket_owner_id)
                
                content = msg.content if msg.content else ""
                content = self._resolve_mentions(content, channel.guild)
                
                embeds_list = []
                
                
                if msg.embeds:
                    for emb in msg.embeds:
                        
                        if msg.author.id == self.bot.user.id and emb.footer and emb.footer.text and "Ответ от администратора" in emb.footer.text:
                            clean_text = emb.description.replace("**", "") if emb.description else ""
                            content = clean_text 
                            is_admin = True      
                            continue             
                        
                        
                        embeds_list.append({
                            "title": emb.title,
                            "description": emb.description,
                            "color": f"#{emb.color.value:06x}" if emb.color else "#202225",
                            "fields": [{"name": f.name, "value": f.value, "inline": f.inline} for f in emb.fields],
                            "footer": emb.footer.text if emb.footer else None,
                            "thumbnail": emb.thumbnail.url if emb.thumbnail else None,
                            "image": emb.image.url if emb.image else None
                        })

                
                for att in msg.attachments:
                    content += f"\n[File: {att.url}]"

                if not content and not embeds_list: 
                    continue

                messages_data.append({
                    "author": msg.author.display_name,
                    "avatar": msg.author.display_avatar.url,
                    "content": content,
                    "embeds": embeds_list, 
                    "is_admin": is_admin, 
                    "time": msg.created_at.isoformat()
                })
        except Exception as e:
            
            log.error(f"📜 Ошибка получения истории тикета: {e}")

        await self.send_event("ticket_history_data", {
            "ticket_id": ticket_id,
            "messages": messages_data
        })
        
    async def _handle_admin_reply(self, data: dict):
        req = AdminReplyPayload(**data)
        ticket = await self.bot.db.get_ticket_by_id(req.ticket_id)
        if not ticket: return
        channel = self.bot.get_channel(ticket['channel_id'])
        if channel:
            embed = disnake.Embed(description=f"**{req.text}**", color=disnake.Color.green())
            embed.set_footer(text=f"Ответ от администратора {req.admin_name}")
            await channel.send(embed=embed)

    async def _handle_close_request(self, data: dict):
        req = TicketActionPayload(**data)
        cog = self.bot.get_cog("Tickets")
        if cog: await cog.close_ticket_logic(req.ticket_id)

    async def _handle_delete_request(self, data: dict):
        req = TicketActionPayload(**data)
        cog = self.bot.get_cog("Tickets")
        if cog: await cog.delete_ticket_logic(req.ticket_id)

    async def _handle_db_request(self, ws, table_name):
        response_data = []
        if table_name == "users":
            async with self.bot.db.conn.execute('SELECT * FROM users') as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    raw = dict(row)
                    uid = raw.pop('id')
                    u_obj = self.bot.get_user(uid)
                    response_data.append({"User": str(u_obj) if u_obj else str(uid), **raw, "ID": str(uid)})
        elif table_name == "cooldown":
            async with self.bot.db.conn.execute('SELECT * FROM cooldown') as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    raw = dict(row)
                    uid = raw.pop('user_id')
                    u_obj = self.bot.get_user(uid)
                    rem = max(0, int(raw['expires_at'] - time.time()))
                    response_data.append({"User": str(u_obj) if u_obj else str(uid), "Command": raw['command'], "Time Left": rem})
        
        await ws.send_str(json.dumps({"type": "db_response", "table": table_name, "data": response_data}))
    
    async def _download_file(self, url, default_name):  
        if not self._is_safe_url(url): return None, None
        try:
            parsed_url = urlparse(url)
            clean_path = parsed_url.path
            headers = {"User-Agent": "Bot/1.0"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        content_type = resp.headers.get('Content-Type', '')
                        ext = mimetypes.guess_extension(content_type)
                        if not ext: ext = "." + clean_path.split("/")[-1].split(".")[-1] if "." in clean_path else ".png"
                        base_name = default_name.split('.')[0]
                        final_name = f"{base_name}{ext}"
                        f = io.BytesIO(data); f.seek(0)
                        return disnake.File(f, filename=final_name), final_name
                    else: return None, None
        except: return None, None

    def _is_safe_url(self, url: str) -> bool:
        try:
            if not url: return False
            parsed = urlparse(url)
            hostname = parsed.hostname
            if not hostname: return False
            ip_str = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved: return False
            return True
        except: return False

    async def _send_embed(self, data: SendEmbedPayload, log_func):
        try:
            channel = self.bot.get_channel(data.channel_id)
            if not channel: return
            
            embed = disnake.Embed(
                title=data.title, description=data.description,
                color=int(data.color, 16), timestamp=disnake.utils.utcnow()
            )
            if data.image_url: embed.set_image(url=data.image_url)
            if data.thumbnail_url: embed.set_thumbnail(url=data.thumbnail_url)
            for f in data.fields: embed.add_field(name=f.name, value=f.value, inline=f.inline)

            view = disnake.ui.View() if data.buttons else None
            for btn in data.buttons: view.add_item(disnake.ui.Button(label=btn.label, url=btn.url, style=disnake.ButtonStyle.link))

            await channel.send(embed=embed, view=view)
            await log_func("success", f"Embed V1 sent to #{channel.name}")
        except Exception as e:
            await log_func("error", f"Embed Error: {e}")
            log.error(f"🧩 Ошибка отправки Embed (V1): {e}") 

    async def _send_v2_components(self, data: SendEmbedPayload, log_func):
        try:
            channel = self.bot.get_channel(data.channel_id)
            if not channel: return
            files = []
            final_img_name = "image.png"
            if data.image_url:
                file_obj, name = await self._download_file(data.image_url, "image")
                if file_obj: files.append(file_obj); final_img_name = name
            
            file_name_display = data.file_name or "document.pdf"
            if data.file_url:
                file_obj, name = await self._download_file(data.file_url, file_name_display)
                if file_obj: file_obj.filename = file_name_display; files.append(file_obj)

            components = []
            container_items = []
            if data.content: container_items.append(disnake.ui.TextDisplay(data.content))
            if data.image_url and any(f.filename == final_img_name for f in files):
                container_items.append(disnake.ui.MediaGallery(disnake.MediaGalleryItem(media=f"attachment://{final_img_name}", description=data.image_desc or "")))
            
            if (len(data.buttons) > 0 or data.file_url): container_items.append(disnake.ui.Separator(divider=True, spacing=disnake.SeparatorSpacing.large))
            
            for btn in data.buttons:
                sec_text = btn.section_text or f"{btn.label}:"
                container_items.append(disnake.ui.Section(disnake.ui.TextDisplay(sec_text), accessory=disnake.ui.Button(style=disnake.ButtonStyle.link, label=btn.label, url=btn.url)))

            if data.file_url and any(f.filename == file_name_display for f in files):
                container_items.append(disnake.ui.TextDisplay("Файл для скачивания:"))
                container_items.append(disnake.ui.File(file={"url": f"attachment://{file_name_display}"}, spoiler=False))

            if container_items: components.append(disnake.ui.Container(*container_items, accent_colour=disnake.Colour(0x1ABC9C), spoiler=False))

            await channel.send(components=components, files=files, flags=disnake.MessageFlags(is_components_v2=True))
            await log_func("success", f"Components V2 sent to #{channel.name}")
        except Exception as e:
            await log_func("error", f"V2 Error: {e}")
            log.error(f"🧩 Ошибка отправки Components (V2): {e}") 