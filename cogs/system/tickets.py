import disnake
import io
import re
import datetime

from config import *
from disnake.ext import commands
from utils.transcript import generate_transcript


class TicketModal(disnake.ui.Modal):
    def __init__(self, ticket_type, cog):
        self.ticket_type = ticket_type
        self.cog = cog
        title_text = "Техническая поддержка" if ticket_type == "tech" else "Вопрос по серверу"
        components = [
            disnake.ui.TextInput(
                label="Суть проблемы", 
                placeholder="Кратко: Не работает бот / Жалоба на игрока", 
                custom_id="topic", 
                max_length=50
            ),
            disnake.ui.TextInput(
                label="Подробное описание", 
                placeholder="Опишите ситуацию максимально подробно...", 
                custom_id="desc", 
                style=disnake.TextInputStyle.paragraph,
                min_length=10
            )
        ]
        super().__init__(title=title_text, components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        topic = inter.text_values["topic"]
        desc = inter.text_values["desc"]
        await self.cog.create_ticket(inter, self.ticket_type, topic, desc)

class TicketView(disnake.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @disnake.ui.string_select(
        placeholder="Выберите категорию обращения...",
        custom_id="ticket_select",
        options=[
            disnake.SelectOption(label="Серверный вопрос", value="server", description="Жалобы, вопросы по правилам, предложения", emoji="🛡️"),
            disnake.SelectOption(label="Техническая проблема", value="tech", description="Ошибки бота, проблемы с доступом, баги", emoji="🔧"),
        ]
    )
    async def select_callback(self, select: disnake.ui.StringSelect, inter: disnake.MessageInteraction):
        select.view.children[0].placeholder = "Категория выбрана..."
        modal = TicketModal(select.values[0], self.cog)
        await inter.response.send_modal(modal)

class TicketControlView(disnake.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @disnake.ui.button(label="Закрыть обращение", style=disnake.ButtonStyle.gray, custom_id="close_ticket_btn", emoji="🔒")
    async def close_btn(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        ticket = await self.bot.db.get_ticket_by_channel(inter.channel.id)
        if ticket:
            cog = self.bot.get_cog("Tickets")
            await cog.close_ticket_logic(ticket['ticket_id'], inter)
        else:
            await inter.send("❌ Ошибка: Не удалось найти тикет в базе данных.", ephemeral=True)

class TicketDeleteView(disnake.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @disnake.ui.button(label="Открыть тикет", style=disnake.ButtonStyle.success, custom_id="reopen_ticket_btn", emoji="🔓")
    async def reopen_btn(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        ticket = await self.bot.db.get_ticket_by_channel(inter.channel.id)
        if ticket:
            cog = self.bot.get_cog("Tickets")
            await cog.reopen_ticket_logic(ticket['ticket_id'], inter)
        else:
            await inter.send("❌ Тикет не найден.", ephemeral=True)

    @disnake.ui.button(label="Удалить и Сохранить", style=disnake.ButtonStyle.red, custom_id="delete_ticket_btn", emoji="🗑️")
    async def delete_btn(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        ticket = await self.bot.db.get_ticket_by_channel(inter.channel.id)
        if ticket:
            cog = self.bot.get_cog("Tickets")
            await cog.delete_ticket_logic(ticket['ticket_id'])
        else:
            await inter.send("❌ Тикет не найден.", ephemeral=True)





class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.persistent_views_added = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.persistent_views_added:
            self.bot.add_view(TicketView(self))
            self.bot.add_view(TicketControlView(self.bot))
            self.bot.add_view(TicketDeleteView(self.bot))
            self.persistent_views_added = True

    

    async def update_status_message(self, channel, status_type):
        async for msg in channel.pins():
            
            if msg.author.id == self.bot.user.id and msg.embeds:
                embed = msg.embeds[0]
                
                if embed.title and "Тикет #" in embed.title:
                    
                    
                    field_index = -1
                    for i, field in enumerate(embed.fields):
                        if "Статус" in field.name:
                            field_index = i
                            break
                    
                    if field_index != -1:
                        if status_type == 'closed':
                            embed.set_field_at(field_index, name="🟢 Статус", value="Закрыт", inline=True)
                        else:
                            embed.set_field_at(field_index, name="🟢 Статус", value="Открыт", inline=True)
                        
                        await msg.edit(embed=embed)
                        return 

    @commands.slash_command(name="setup_tickets")
    async def setup_tickets(self, inter):
        embed = disnake.Embed(
            title="Центр Поддержки",
            description=(
                "**Нужна помощь или есть вопрос?**\n"
                "Создайте тикет, выбрав соответствующую категорию в меню ниже.\n\n"
                "🛡️ **Серверные вопросы** — Жалобы, правила, роли.\n"
                "🔧 **Технические проблемы** — Ошибки, баги\n\n"
                "ℹ️ *Наша команда ответит вам в ближайшее время.*"
            ),
            color=0x2b2d31
        )
        if inter.guild.icon: embed.set_thumbnail(url=inter.guild.icon.url)
        embed.set_footer(text="Тех.Поддержка - KwargsssBot")
        await inter.channel.send(embed=embed, view=TicketView(self))
        await inter.response.send_message("✅ Панель тикетов успешно установлена!", ephemeral=True)

    
    async def create_ticket(self, inter, t_type, topic, desc):
        color = 0x5865F2 if t_type == "server" else 0x9B59B6
        type_name = "Server Support" if t_type == "server" else "Tech Support"
        
        cat_id = TICKET_CATEGORY_SERVER_ID if t_type == "server" else TICKET_CATEGORY_TECH_ID
        category = self.bot.get_channel(cat_id)
        if not category: return await inter.edit_original_response("❌ Ошибка: Категория тикетов не настроена.")

        ticket_id = await self.bot.db.create_ticket(inter.author.id, 0, t_type, topic)
        
        overwrites = {
            inter.guild.default_role: disnake.PermissionOverwrite(read_messages=False),
            inter.author: disnake.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            inter.guild.me: disnake.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for role_id in TICKET_SUPPORT_ROLES:
            role = inter.guild.get_role(role_id)
            if role: overwrites[role] = disnake.PermissionOverwrite(read_messages=True, send_messages=True)

        channel_name = f"ticket-{ticket_id}"
        channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)
        await self.bot.db.conn.execute("UPDATE tickets SET channel_id = ? WHERE ticket_id = ?", (channel.id, ticket_id))
        await self.bot.db.conn.commit()

        embed = disnake.Embed(
            title=f"{type_name} | Тикет #{ticket_id}",
            description=f"Привет! \n Мы получили ваш запрос. Администратор скоро подключится.",
            color=color, timestamp=datetime.datetime.now()
        )
        embed.add_field(name="📋 Тема обращения", value=f"**{topic}**", inline=False)
        embed.add_field(name="📝 Описание", value=f"{desc}", inline=False)
        embed.add_field(name="👤 Создатель", value=inter.author.display_name, inline=True)
        embed.add_field(name="🏷️ Категория", value=t_type.capitalize(), inline=True)
        embed.add_field(name="🟢 Статус", value="Открыт", inline=True)
        embed.set_thumbnail(url=inter.author.display_avatar.url)

        msg = await channel.send(
            content=f"{inter.author.mention} <@&{TICKET_SUPPORT_ROLES[0]}>", 
            embed=embed, view=TicketControlView(self.bot)
        )
        await msg.pin()
        try: await inter.edit_original_response(f"✅ Тикет создан: {channel.mention}")
        except: pass

        await self.send_ws_event("ticket_created", {
            "id": ticket_id, "type": t_type, "topic": topic, "author": inter.author.name,
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    
    async def close_ticket_logic(self, ticket_id, inter=None):
        ticket = await self.bot.db.get_ticket_by_id(ticket_id)
        if not ticket or ticket['status'] == 'closed': return

        channel = self.bot.get_channel(ticket['channel_id'])
        if not channel: return

        await self.bot.db.close_ticket(ticket_id)

        
        user = channel.guild.get_member(ticket['user_id'])
        if user: await channel.set_permissions(user, read_messages=False)

        
        await self.update_status_message(channel, 'closed')

        embed = disnake.Embed(
            title="🔒 Обращение закрыто",
            description="Тикет был помечен как решенный.\nВы можете удалить его или **открыть заново**, если закрыли случайно.",
            color=disnake.Color.dark_grey()
        )
        embed.set_footer(text=f"Закрыл: {inter.author.display_name if inter else 'Система'}")
        
        await channel.send(embed=embed, view=TicketDeleteView(self.bot))
        
        try: await channel.edit(name=f"closed-{ticket_id}")
        except: pass

        if inter:
            try: await inter.send("Тикет закрыт", ephemeral=True)
            except: pass
        
        await self.send_ws_event("ticket_updated", {"id": ticket_id, "status": "closed"})

    
    async def reopen_ticket_logic(self, ticket_id, inter):
        ticket = await self.bot.db.get_ticket_by_id(ticket_id)
        channel = self.bot.get_channel(ticket['channel_id'])
        if not channel: return

        await self.bot.db.reopen_ticket(ticket_id)

        user = channel.guild.get_member(ticket['user_id'])
        if user:
            await channel.set_permissions(user, read_messages=True, send_messages=True, attach_files=True)

        
        await self.update_status_message(channel, 'open')

        embed = disnake.Embed(
            description=f"🔓 **Тикет снова открыт!**\nПрава пользователя {user.mention if user else 'Unknown'} восстановлены.",
            color=disnake.Color.green()
        )
        
        if inter:
            try: await inter.message.delete()
            except: pass
            
        await channel.send(embed=embed, view=TicketControlView(self.bot))
        
        try: await channel.edit(name=f"ticket-{ticket_id}")
        except: pass

        await self.send_ws_event("ticket_updated", {"id": ticket_id, "status": "open"})


    

    async def delete_ticket_logic(self, ticket_id):
        ticket = await self.bot.db.get_ticket_by_id(ticket_id)
        if not ticket: return 

        channel = self.bot.get_channel(ticket['channel_id'])
        transcript_url = None 

        if channel:
            await channel.send("⏳ **Сохранение данных и удаление...**")
            html_content = await generate_transcript(channel)
            
            user = channel.guild.get_member(ticket['user_id'])
            log_channel = self.bot.get_channel(TICKET_LOG_CHANNEL_ID)
            
            
            if log_channel:
                file = disnake.File(io.BytesIO(html_content.encode('utf-8')), filename=f"ticket-{ticket_id}.html")
                log_embed = disnake.Embed(title=f"📑 Архив тикета #{ticket_id} от {user}", description=f"**Тема**\n{ticket['topic']}" ,color=disnake.Color.blurple(), timestamp=datetime.datetime.now())
                msg = await log_channel.send(embed=log_embed, file=file)
                
                
                transcript_url = msg.attachments[0].url
                
                
                await self.bot.db.set_transcript(ticket_id, transcript_url)

            
            await channel.delete()
        
        
        await self.bot.db.conn.execute("UPDATE tickets SET status = 'deleted' WHERE ticket_id = ?", (ticket_id,))
        await self.bot.db.conn.commit()
        
        
        await self.send_ws_event("ticket_deleted", {"id": ticket_id, "status": "deleted"})

    @commands.Cog.listener()
    async def on_message(self, message):
        if not isinstance(message.channel, disnake.TextChannel): return

        ticket = await self.bot.db.get_ticket_by_channel(message.channel.id)
        if ticket and ticket['status'] == 'open':
            
            content = message.content
            author_name = message.author.display_name
            avatar_url = message.author.display_avatar.url
            embeds_list = []

            if content:
                guild = message.guild
                content = re.sub(r'<@!?(\d+)>', lambda m: f'<span class="mention">@{guild.get_member(int(m.group(1))).display_name if guild.get_member(int(m.group(1))) else "User"}</span>', content)
                content = re.sub(r'<@&(\d+)>', lambda m: f'<span class="mention role">@{guild.get_role(int(m.group(1))).name if guild.get_role(int(m.group(1))) else "Role"}</span>', content)
                content = re.sub(r'<#(\d+)>', lambda m: f'<span class="mention">#{guild.get_channel(int(m.group(1))).name if guild.get_channel(int(m.group(1))) else "channel"}</span>', content)

            if message.embeds:
                for emb in message.embeds:
                    if message.author.id == self.bot.user.id and emb.footer and emb.footer.text and "Ответ от администратора" in emb.footer.text:
                        content = emb.description.replace("**", "") if emb.description else ""
                        try:
                            author_name = emb.footer.text.replace("Ответ от администратора ", "")
                        except: pass
                        continue

                    embeds_list.append({
                        "title": emb.title,
                        "description": emb.description,
                        "color": f"#{message.embeds[0].color.value:06x}" if message.embeds[0].color else "#202225",
                        "fields": [{"name": f.name, "value": f.value, "inline": f.inline} for f in emb.fields],
                        "footer": emb.footer.text if emb.footer else None,
                        "thumbnail": emb.thumbnail.url if emb.thumbnail else None,
                        "image": emb.image.url if emb.image else None
                    })

            await self.send_ws_event("new_message", {
                "ticket_id": ticket['ticket_id'],
                "author": author_name, 
                "avatar": avatar_url,
                "content": content,
                "embeds": embeds_list,
                "time": message.created_at.isoformat()
            })

    async def send_ws_event(self, type, data):
        if hasattr(self.bot, 'ws_client') and self.bot.ws_client:
             await self.bot.ws_client.send_event(type, data)

def setup(bot):
    bot.add_cog(Tickets(bot))