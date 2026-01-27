import disnake

from disnake.ext import commands
from utils.embeds import EmbedBuilder
from config import *


embed_builder = EmbedBuilder()

class Blacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_view = EmbedBuilder("data/embeds.json")


    @commands.slash_command(name="чс", description="Управление черным списком")
    async def blacklist(self, inter):
        pass

    @blacklist.sub_command(name="выдать", description="Заблокировать доступ к боту")
    async def blacklist_add(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        user: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя"), 
        reason: str = commands.Param(name="причина", description="Укажите причину", default="Нарушение правил")
    ):
        await inter.response.defer()
        if user.id == inter.author.id or user.bot:
            embed = self.embed_view.get_embed(
                "error_blacklist_invalid_target",
                author_avatar=inter.author.display_avatar.url
            )
            return await inter.edit_original_response(embed=embed )

        await self.bot.db.add_blacklist(user.id, reason, inter.author.id)

        embed = self.embed_view.get_embed(
            "blacklist_added",
            user=user.mention,
            user_id=user.id,
            reason=reason,
            author=inter.author.mention,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

        log_channel = inter.guild.get_channel(LOG_PUNISH)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_blacklist_add",
                user=user.mention,
                author=inter.author.name,
                author_avatar=inter.author.display_avatar.url,
                reason=reason
            )
            await log_channel.send(embed=embed_log)

    @blacklist.sub_command(name="снять", description="Разблокировать доступ")
    async def blacklist_remove(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        user: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя"), 
    ):
        await inter.response.defer()
        check = await self.bot.db.check_blacklist(user.id)
        
        if not check:
            embed = self.embed_view.get_embed(
                "error_blacklist_not_found",
                user=user.name,
                author_avatar=inter.author.display_avatar.url
            )
            return await inter.edit_original_response(embed=embed )

        await self.bot.db.remove_blacklist(user.id)

        embed = self.embed_view.get_embed(
            "blacklist_removed",
            user=user.mention,
            author=inter.author.mention,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

        log_channel = inter.guild.get_channel(LOG_PUNISH)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_blacklist_remove",
                user=user.mention,
                author=inter.author.name,
                author_avatar=inter.author.display_avatar.url,
            )
            await log_channel.send(embed=embed_log)

def setup(bot):
    bot.add_cog(Blacklist(bot))