import disnake
from disnake.ext import commands


class Reload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name='reload')
    async def reload(self, inter: disnake.ApplicationCommandInteraction, extension: str):
        try:
            self.bot.reload_extension(f"cogs.{extension}")
            
            await inter.send(f"✅ Модуль `cogs.{extension}` перезагружен!", ephemeral=True)
        except Exception as e:
            await inter.send(f"❌ Ошибка: {e}", ephemeral=True)    

def setup(bot):
    bot.add_cog(Reload(bot))