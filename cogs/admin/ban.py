import disnake
import time

from config import *
from disnake.ext import commands
from utils.time_converter import parse_time
from utils.embeds import EmbedBuilder


embed_builder = EmbedBuilder()

class Ban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="бан", description="Выдать или снять бан на время")
    async def ban(self, inter):
        pass

    @ban.sub_command(name="выдать", description="Выдать бан на время")
    async def giveban(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя"), 
        time_str: str = commands.Param(name="время", description="Например: 1ч 30мин"),
        reason: str = commands.Param(name="причина", description="Укажите причину", default="Нарушение правил")
    ):
        await inter.response.defer()
        seconds = parse_time(time_str)

        if seconds == 0:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_invalid_time", author_avatar=inter.author.display_avatar.url)
            )

        if seconds < 5:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_invalid_time", author_avatar=inter.author.display_avatar.url)
            )

        role_ban = inter.guild.get_role(ROLE_BAN)
        if not role_ban:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Роль бана не настроена в конфиге.", author_avatar=inter.author.display_avatar.url)
            )

        if member.id == self.bot.user.id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_bot_action", author_avatar=inter.author.display_avatar.url)
            )

        if member.id == inter.author.id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_self_action", author_avatar=inter.author.display_avatar.url)
            )

        if member.top_role >= inter.author.top_role and inter.author.id != inter.guild.owner_id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_hierarchy", author_avatar=inter.author.display_avatar.url)
            )

        if role_ban in member.roles:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Пользователь уже забанен.", author_avatar=inter.author.display_avatar.url)
            )

        await member.add_roles(role_ban, reason=f"Забанил {inter.author}: {reason}")

        expires_at = time.time() + seconds

        await self.bot.db.add_punishment(
            user_id=member.id,
            p_type="ban", 
            expires_at=expires_at, 
            reason=reason, 
            moderator_id=inter.author.id
        )

        embed = embed_builder.get_embed(
            name="success_ban",
            user_mention=member.mention,
            time_str=time_str,
            expires_at=int(expires_at),
            reason=reason,
            moderator_name=inter.author.display_name,
            moderator_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

        log_channel = inter.guild.get_channel(LOG_PUNISH)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_ban",
                user_mention=member.mention,
                moderator_mention=inter.author.mention,
                time_str=time_str,
                reason=reason,
                moderator_name=inter.author.display_name,
                moderator_avatar=inter.author.display_avatar.url
            )
            await log_channel.send(embed=embed_log)

    @ban.sub_command(name="снять", description="Снять бан с пользователя")
    async def unban(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя")
    ):
        await inter.response.defer()
        role_ban = inter.guild.get_role(ROLE_BAN)
        
        active_ban = await self.bot.db.get_active_ban(member.id)
        has_role = role_ban and role_ban in member.roles

        if not active_ban and not has_role:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Этот пользователь не забанен.", author_avatar=inter.author.display_avatar.url)
            )

        if has_role:
            await member.remove_roles(role_ban, reason=f"Разбанил {inter.author}")

        if active_ban:
            await self.bot.db.revoke_punishment(active_ban['id'])

        embed = embed_builder.get_embed(
            name="success_unban",
            user_mention=member.mention,
            moderator_mention=inter.author.mention,
            moderator_name=inter.author.display_name,
            moderator_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

        log_channel = inter.guild.get_channel(LOG_PUNISH)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_unban",
                user_mention=member.mention,
                moderator_mention=inter.author.mention,
                moderator_name=inter.author.display_name,
                moderator_avatar=inter.author.display_avatar.url
            )
            await log_channel.send(embed=embed_log)

def setup(bot):
    bot.add_cog(Ban(bot))