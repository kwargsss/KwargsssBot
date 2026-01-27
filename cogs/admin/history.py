import disnake
from disnake.ext import commands
from utils.embeds import EmbedBuilder


embed_builder = EmbedBuilder()

class HistorySelect(disnake.ui.StringSelect):
    def __init__(self, bot, target_user, author):
        self.bot = bot
        self.target_user = target_user
        self.author = author
        
        options = [
            disnake.SelectOption(label="Все наказания", value="all", description="Показать общую историю", emoji="📜", default=True),
            disnake.SelectOption(label="Варны", value="warn", description="Только предупреждения", emoji="⚠️"),
            disnake.SelectOption(label="Баны", value="ban", description="Только блокировки", emoji="🔨"),
            disnake.SelectOption(label="Мьюты", value="mute", description="Только заглушки", emoji="🔇"),
        ]
        
        super().__init__(
            placeholder="Выберите тип наказаний...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="history_select"
        )

    async def callback(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.author.id:
            # Для чужих кнопок используем send с ephemeral=True (это не крашит, так как это send, а не edit)
            # Если вы хотите, чтобы ошибки кнопок видели все, уберите ephemeral=True
            return await inter.response.send_message(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url),
                ephemeral=True 
            )

        selected_type = self.values[0]
        
        for option in self.options:
            option.default = (option.value == selected_type)

        embed = await generate_history_embed(self.bot, self.target_user, self.author, selected_type)

        await inter.response.edit_message(embed=embed, view=self.view)


class HistoryView(disnake.ui.View):
    def __init__(self, bot, target_user, author):
        super().__init__(timeout=180)
        self.add_item(HistorySelect(bot, target_user, author))

async def generate_history_embed(bot, target, author, p_type):
    history = await bot.db.get_punishment_history(target.id, p_type)

    if not history:
        history_text = "*История наказаний пуста...*"
    else:
        lines = []
        for i, entry in enumerate(history, 1):
            mod_id = entry['moderator_id']
            reason = entry['reason'] or "Нет причины"
            created_at = entry['created_at'] or 0
            ptype = entry['type'].upper()
            status = entry.get('status', 'unknown')

            if status == 'active':
                status_icon = "🟢 Активен"
            elif status == 'expired':
                status_icon = "⚪ Истек"
            elif status == 'revoked':
                status_icon = "🛡️ Снят"
            else:
                status_icon = ""

            emoji = "⚠️" if ptype == "WARN" else "🔨" if ptype == "BAN" else "🔇"
            time_str = f"<t:{int(created_at)}:d>" if created_at else "???"

            lines.append(
                f"**{i}.** {emoji} `{ptype}` | {time_str}\n"
                f"> 👤 Модератор: <@{mod_id}>\n"
                f"> 📊 Статус: {status_icon}\n"
                f"> 📝 *{reason}*"
            )
        
        history_text = "\n".join(lines)

    filter_map = {"all": "Все наказания", "warn": "Варны", "ban": "Баны", "mute": "Мьюты"}
    
    return embed_builder.get_embed(
        name="history_embed",
        user_mention=target.mention,
        user_id=target.id,
        filter_name=filter_map.get(p_type, "Unknown"),
        history_text=history_text,
        author_name=author.display_name,
        author_avatar=author.display_avatar.url
    )

class HistoryCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="история", description="Посмотреть историю наказаний")
    async def history(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя")
    ):
        await inter.response.defer()

        embed = await generate_history_embed(self.bot, member, inter.author, "all")

        view = HistoryView(self.bot, member, inter.author)
        
        await inter.edit_original_response(embed=embed, view=view)

def setup(bot):
    bot.add_cog(HistoryCommand(bot))