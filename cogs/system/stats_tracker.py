from disnake.ext import commands
from utils.stats_manager import stats


class StatsTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def push_stats_update(self):
        if hasattr(self.bot, "ws_client") and self.bot.ws_client:
            payload = {
                "recent_commands": stats.data["recent_commands"],
                "commands_today": stats.data["commands_today"],
                "messages_today": stats.data["messages_today"]
            }
            await self.bot.ws_client.send_event("stats_update", payload)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        stats.add_message()

    @commands.Cog.listener()
    async def on_command(self, ctx):
        stats.add_command(
            user=ctx.author.name,
            channel=ctx.channel.name,
            command_name=f"{ctx.prefix}{ctx.command.name}",
            success=True
        )
        await self.push_stats_update()

    @commands.Cog.listener()
    async def on_slash_command(self, inter):
        channel_name = inter.channel.name if inter.channel else "ЛС"
        stats.add_command(
            user=inter.author.name,
            channel=channel_name,
            command_name=f"/{inter.application_command.name}",
            success=True
        )
        await self.push_stats_update()

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, (commands.CommandNotFound, commands.MissingPermissions)):
            cmd_name = ctx.message.content.split()[0] if ctx.message.content else "Unknown"
            stats.add_command(
                user=ctx.author.name,
                channel=ctx.channel.name if ctx.channel else "ЛС",
                command_name=cmd_name,
                success=False
            )
            await self.push_stats_update()

def setup(bot):
    bot.add_cog(StatsTracker(bot))