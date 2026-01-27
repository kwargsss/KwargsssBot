from disnake.ext import commands
from utils.embeds import EmbedBuilder
from config import *


embed_builder = EmbedBuilder()

class Lock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="закрыть", description="Закрыть канал для сообщений")
    async def lock(self, inter):
        await inter.response.defer()
        if inter.channel.id in ADMIN_CHANNELS_LIST:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_admin_channel", author_avatar=inter.author.display_avatar.url)
            )

        channel = inter.channel

        overwrite = channel.overwrites_for(inter.guild.default_role)

        if overwrite.send_messages is False:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Этот канал уже заблокирован.", author_avatar=inter.author.display_avatar.url)
            )
        
        overwrite.send_messages = False
        await channel.set_permissions(inter.guild.default_role, overwrite=overwrite, reason=f"Закрыл {inter.author}")

        embed = embed_builder.get_embed(
            name="success_lock",
            moderator_mention=inter.author.mention,
            channel_mention=channel.mention,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

        log_channel = inter.guild.get_channel(LOG_PUNISH)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_lock",
                channel_mention=channel.mention,
                moderator_mention=inter.author.mention,
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            await log_channel.send(embed=embed_log)

    @commands.slash_command(name="открыть", description="Разрешить писать в текущем канале")
    async def unlock(self, inter):
        await inter.response.defer()
        if inter.channel.id in ADMIN_CHANNELS_LIST:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_admin_channel", author_avatar=inter.author.display_avatar.url)
            )

        channel = inter.channel
        
        overwrite = channel.overwrites_for(inter.guild.default_role)

        if overwrite.send_messages is None or overwrite.send_messages is True:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Этот канал не заблокирован.", author_avatar=inter.author.display_avatar.url)
            )

        overwrite.send_messages = None
        await channel.set_permissions(inter.guild.default_role, overwrite=overwrite, reason=f"Открыл {inter.author}")

        embed = embed_builder.get_embed(
            name="success_unlock",
            moderator_mention=inter.author.mention,
            channel_mention=channel.mention,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

        log_channel = inter.guild.get_channel(LOG_PUNISH)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_unlock",
                channel_mention=channel.mention,
                moderator_mention=inter.author.mention,
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            await log_channel.send(embed=embed_log)

def setup(bot):
    bot.add_cog(Lock(bot))