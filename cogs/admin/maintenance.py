import disnake

from disnake.ext import commands
from utils.embeds import EmbedBuilder


class Maintenance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_view = EmbedBuilder("data/embeds.json")

    @commands.slash_command(name="обслуживание", description="Управление режимом техработ")
    async def maintenance(self, inter: disnake.ApplicationCommandInteraction, state: str = commands.Param(name="режим", description="Режим экономики",choices=["Включить", "Выключить"])):
        
        await inter.response.defer()
        enable = (state == "Включить")

        await self.bot.db.set_maintenance(enable)

        embed_name = "maintenance_enabled" if enable else "maintenance_disabled"

        embed = self.embed_view.get_embed(
            embed_name,
            author_avatar=inter.author.display_avatar.url
        )
            
        await inter.edit_original_response(embed=embed)

def setup(bot):
    bot.add_cog(Maintenance(bot))