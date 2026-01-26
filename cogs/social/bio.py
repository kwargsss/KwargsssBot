from disnake.ext import commands
from utils.embeds import EmbedBuilder


embed_builder = EmbedBuilder()

class Bio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="био", description="Установить биографию профиля")
    async def bio(
        self, 
        inter, 
        text: str = commands.Param(name="текст", description="Ваша биография (макс. 200 символов)")
    ):
        if len(text) > 200:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Длина биографии не может превышать 200 символов.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        await self.bot.db.update_bio(inter.author.id, text)
        
        embed = embed_builder.get_embed(
            "success_bio",
            bio=text,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.send(embed=embed)

def setup(bot):
    bot.add_cog(Bio(bot))