import disnake
import traceback
import io

from disnake.ext import commands
from config import *
from utils.logger import log


class GlobalErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_to_owner(self, inter, error, tb):
        owner = await self.bot.fetch_user(OWNER_ID)
        
        if not owner:
            return

        embed = disnake.Embed(
            title="🔥 Critical Error Report",
            color=disnake.Color.dark_red(),
            timestamp=disnake.utils.utcnow()
        )
        
        cmd_name = inter.data.name if hasattr(inter, 'data') and hasattr(inter.data, 'name') else "Unknown"

        embed.add_field(name="Команда", value=f"`/{cmd_name}`", inline=True)
        embed.add_field(name="Пользователь", value=f"{inter.author} (`{inter.author.id}`)", inline=True)
        
        if inter.guild:
            embed.add_field(name="Сервер", value=f"{inter.guild.name} (`{inter.guild.id}`)", inline=True)
        else:
            embed.add_field(name="Локация", value="Личные сообщения (DM)", inline=True)

        if len(tb) < 1000:
            embed.description = f"```python\n{tb}\n```"
            await owner.send(embed=embed)
        else:
            embed.description = "**Ошибка слишком длинная. Полный лог в файле ниже.**"
            await owner.send(embed=embed)
            
            file_buffer = io.BytesIO(tb.encode('utf-8'))
            file = disnake.File(file_buffer, filename="traceback.txt")
            
            await owner.send(file=file)


    @commands.Cog.listener()
    async def on_slash_command_error(self, inter: disnake.ApplicationCommandInteraction, error: Exception):
        
        if getattr(inter, "handled", False):
            return

        if isinstance(error, commands.MissingPermissions):
            embed = disnake.Embed(title="⛔ Нет прав", description="У вас недостаточно прав.", color=disnake.Color.red())
            if not inter.response.is_done():
                await inter.send(embed=embed, ephemeral=True)
            else:
                await inter.followup.send(embed=embed, ephemeral=True)
            return

        elif isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            msg = f"⚠️ Мне не хватает прав: {missing}"
            if not inter.response.is_done():
                await inter.send(msg, ephemeral=True)
            else:
                await inter.followup.send(msg, ephemeral=True)
            return
        
        elif isinstance(error, commands.CommandInvokeError):
            original_error = error.original
            
            
            tb = "".join(traceback.format_exception(type(original_error), original_error, original_error.__traceback__))

            
            cmd_name = inter.data.name if hasattr(inter, 'data') and hasattr(inter.data, 'name') else "Unknown"

            
            log.error(f"User: {inter.author}\nCommand: /{cmd_name}\n\n{tb}")

            
            self.bot.loop.create_task(self.send_to_owner(inter, original_error, tb))

            
            embed = disnake.Embed(
                title="🔥 Произошла внутренняя ошибка",
                description="Разработчик уже получил автоматический отчет об этом сбое.",
                color=disnake.Color.dark_red()
            )
            
            try:
                if not inter.response.is_done():
                    await inter.send(embed=embed, ephemeral=True)
                else:
                    await inter.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                pass

def setup(bot):
    bot.add_cog(GlobalErrorHandler(bot))