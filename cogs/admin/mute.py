import disnake
import time

from config import *
from disnake.ext import commands
from utils.time_converter import parse_time
from utils.embeds import EmbedBuilder


embed_builder = EmbedBuilder()

class Mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="мут", description="Замутить или размутить пользователя на время")
    async def mute(self, inter):
        await inter.response.defer()
        pass

    @mute.sub_command(name="выдать", description="Замутить пользователя на время")
    async def give_mute(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя"), 
        time_str: str = commands.Param(name="время", description="Например: 1ч 30мин"),
        reason: str = commands.Param(name="причина", description="Укажите причину", default="Нарушение правил")
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

        seconds = parse_time(time_str)
        if seconds == 0:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_invalid_time", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        if seconds < 5:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_invalid_time", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        role_mute = inter.guild.get_role(ROLE_MUTE)
        if not role_mute:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Роль Mute не настроена в конфиге.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        if role_mute in member.roles:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Пользователь уже в мьюте.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        await member.add_roles(role_mute, reason=f"Замьютил {inter.author}: {reason}")

        expires_at = time.time() + seconds
        await self.bot.db.add_punishment(
            user_id=member.id, 
            p_type="mute", 
            expires_at=expires_at, 
            reason=reason, 
            moderator_id=inter.author.id
        )

        embed = embed_builder.get_embed(
            name="success_mute",
            user_mention=member.mention,
            time_str=time_str,
            expires_at=int(expires_at),
            reason=reason,
            moderator_name=inter.author.display_name,
            moderator_avatar=inter.author.display_avatar.url,
            moderator_mention=inter.author.mention,
        )
        await inter.edit_original_response(embed=embed)

        log_channel = inter.guild.get_channel(LOG_PUNISH)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_mute",
                user_mention=member.mention,
                user_id=member.id,
                moderator_mention=inter.author.mention,
                time_str=time_str,
                reason=reason,
                moderator_name=inter.author.display_name,
                moderator_avatar=inter.author.display_avatar.url,
            )
            await log_channel.send(embed=embed_log)

    @mute.sub_command(name="снять", description="Снять мьют с пользователя")
    async def unmute(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя")
    ):
        await inter.response.defer()
        role_mute = inter.guild.get_role(ROLE_MUTE)
        
        active_mute = await self.bot.db.get_active_mute(member.id)
        has_role = role_mute and role_mute in member.roles

        if not active_mute and not has_role:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Этот Пользователь не в мьюте.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        if has_role:
            await member.remove_roles(role_mute, reason=f"Размьютил {inter.author}")

        if active_mute:
            await self.bot.db.revoke_punishment(active_mute['id'])

        embed = embed_builder.get_embed(
            name="success_unmute",
            user_mention=member.mention,
            moderator_name=inter.author.display_name,
            moderator_avatar=inter.author.display_avatar.url,
            moderator_mention=inter.author.mention,
        )
        await inter.edit_original_response(embed=embed)

        log_channel = inter.guild.get_channel(LOG_PUNISH)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_unmute",
                user_mention=member.mention,
                user_id=member.id,
                moderator_mention=inter.author.mention,
                moderator_name=inter.author.display_name,
                moderator_avatar=inter.author.display_avatar.url
            )
            await log_channel.send(embed=embed_log)

def setup(bot):
    bot.add_cog(Mute(bot))