import disnake

from config import *
from disnake.ext import commands
from utils.embeds import EmbedBuilder


embed_builder = EmbedBuilder()

class WarnSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="варн", description="Выдать или снять предупреждение пользователю")
    async def warn(self, inter):
        pass

    @warn.sub_command(name="выдать", description="Выдать предупреждение пользователю")
    async def givewarn(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя"), 
        reason: str = commands.Param(name="причина",description="Укажите причину", default="Нарушение правил")
    ):
        await inter.response.defer()
        if member.id == self.bot.user.id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_bot_action", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        if member.id == inter.author.id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_self_action", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        
        if member.top_role >= inter.author.top_role and inter.author.id != inter.guild.owner_id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_hierarchy", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        await self.bot.db.add_punishment(member.id, "warn", 0, reason=reason, moderator_id=inter.author.id)

        count = await self.bot.db.get_warns_count(member.id)

        embed = embed_builder.get_embed(
            name="success_warn",
            user_mention=member.mention,
            warn_count=count,
            reason=reason,
            moderator_name=inter.author.display_name,
            moderator_avatar=inter.author.display_avatar.url,
            moderator_mention=inter.author.mention,
        )
        await inter.edit_original_response(embed=embed)

        log_channel = inter.guild.get_channel(LOG_PUNISH)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_warn",
                user_mention=member.mention,
                user_id=member.id,
                moderator_mention=inter.author.mention,
                warn_count=count,
                reason=reason,
                moderator_name=inter.author.display_name,
                moderator_avatar=inter.author.display_avatar.url,
            )
            await log_channel.send(embed=embed_log)

    @warn.sub_command(name="снять", description="Снять предупреждение")
    async def unwarn(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя"), 
    ):
        await inter.response.defer()
        removed = await self.bot.db.remove_last_warn(member.id)
        
        if not removed:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text=f"У пользователя {member.mention} нет активных предупреждений.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        count = await self.bot.db.get_warns_count(member.id)

        embed = embed_builder.get_embed(
            name="success_unwarn",
            user_mention=member.mention,
            warn_count=count,
            moderator_name=inter.author.display_name,
            moderator_avatar=inter.author.display_avatar.url,
            moderator_mention=inter.author.mention,
        )
        await inter.edit_original_response(embed=embed)

        log_channel = inter.guild.get_channel(LOG_PUNISH)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_unwarn",
                user_mention=member.mention,
                user_id=member.id,
                moderator_mention=inter.author.mention,
                warn_count=count,
                moderator_avatar=inter.author.display_avatar.url,
                moderator_name=inter.author.display_name,
            )
            await log_channel.send(embed=embed_log)

def setup(bot):
    bot.add_cog(WarnSystem(bot))