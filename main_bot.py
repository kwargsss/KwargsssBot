import disnake
import os
import asyncio

from utils.logger import log
from config import *
from disnake.ext import commands, tasks
from services.dashboard import DashboardClient
from services.backup import backup_scheduler
from database.core import UsersDataBase


bot = commands.Bot(
    command_prefix="!", 
    intents=disnake.Intents.all(),
    help_command=None,
    test_guilds=[TARGET_GUILD_ID]
)

db = UsersDataBase()

async def process_expired_punishments(expired_list):
    guild = bot.get_guild(TARGET_GUILD_ID)
    if not guild: return

    role_ban = guild.get_role(ROLE_BAN)
    role_mute = guild.get_role(ROLE_MUTE)

    for record in expired_list:
        punish_type = record['type']
        user_id = record['user_id']
        row_id = record['id']

        member = guild.get_member(user_id)
        if punish_type == "ban":
            if role_ban and member:
                await member.remove_roles(role_ban, reason="[Auto] Время бана истекло")
            

        elif punish_type == "mute":
            if role_mute and member:
                await member.remove_roles(role_mute, reason="[Auto] Время мьюта истекло")
                
        await db.expire_punishment(row_id)

@bot.event
async def on_ready():
    if getattr(bot, "db_initialized", False):
        return

    await bot.change_presence(status = disnake.Status.online, activity = disnake.Game( '/хелп' ))

    await db.connect()
    bot.db = db
    bot.db_initialized = True
    log.info("✅ База данных подключена")

    if not cooldown_cleanup_loop.is_running():
        cooldown_cleanup_loop.start()

    if not check_punishments_loop.is_running():
        check_punishments_loop.start()

    # if not daily_backup_task.is_running():
    #     daily_backup_task.start()
    #     logger.info("[BACKUP] Система бэкапов активирована.")

    expired = await db.get_expired_punishments()
    if expired:
        await process_expired_punishments(expired)

    for guild in bot.guilds:
        for member in guild.members:
            user = await db.get_user(member)

            if not user:
                await db.add_user(member)

    ws_client = DashboardClient(bot)
    bot.ws_client = ws_client
    bot.loop.create_task(ws_client.start())

    log.info(f"✅ Бот успешно запущен!")

@bot.event
async def on_member_join(member):
    if hasattr(bot, "db") and bot.db:
        user = await bot.db.get_user(member)
        if not user:
            await bot.db.add_user(member)

    if member.guild.id == TARGET_GUILD_ID:
        active_ban = await bot.db.get_active_ban(member.id)
        active_mute = await bot.db.get_active_mute(member.id)
        
        if active_ban:
            role_ban = member.guild.get_role(ROLE_BAN)
            if role_ban:
                await member.add_roles(role_ban, reason="Попытка обхода наказания")

        if active_mute:
            role_mute = member.guild.get_role(ROLE_MUTE)
            if role_mute:
                await member.add_roles(role_mute, reason="Попытка обхода наказания")



@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if hasattr(bot, "db") and bot.db:
        await bot.db.increment_daily_stat("message")

    await bot.process_commands(message)

@bot.event
async def on_slash_command_completion(inter):
    if hasattr(bot, "db") and bot.db:
        await bot.db.increment_daily_stat("command")

@bot.event
async def on_command_completion(ctx):
    if hasattr(bot, "db") and bot.db:
        await bot.db.increment_daily_stat("command")

@bot.event
async def on_user_command_completion(inter):
    if hasattr(bot, "db") and bot.db:
        await bot.db.increment_daily_stat("command")

@bot.event
async def on_message_command_completion(inter):
    if hasattr(bot, "db") and bot.db:
        await bot.db.increment_daily_stat("command")

@bot.event
async def on_disconnect():
    log.warning("🔌 Бот потерял соединение с Gateway (Disconnect)!")

@tasks.loop(seconds = 10)
async def cooldown_cleanup_loop():
    await db.remove_expired_cooldowns()

@tasks.loop(seconds=30)
async def check_punishments_loop():
    if not getattr(bot, "db_initialized", False):
        return

    expired_list = await db.get_expired_punishments()
    if expired_list:
        await process_expired_punishments(expired_list)

# @tasks.loop(hours=24)
# async def daily_backup_task():
#     log.info("⏳ Планировщик бекапов бота запущен")
#     logger.info("[BACKUP] Начинаю создание ежедневного бэкапа...")
#     asyncio.create_task(backup.backup_scheduler())

# @daily_backup_task.before_loop
# async def before_backup():
#     asyncio.create_task(backup.backup_scheduler())

for filename in os.listdir("./cogs/system"):
    if filename.endswith(".py") and not filename.startswith("_"):
        bot.load_extension(f"cogs.system.{filename[:-3]}")

for filename in os.listdir("./cogs/admin"):
    if filename.endswith(".py") and not filename.startswith("_"):
        bot.load_extension(f"cogs.admin.{filename[:-3]}")

for filename in os.listdir("./cogs/economy"):
    if filename.endswith(".py") and not filename.startswith("_"):
        bot.load_extension(f"cogs.economy.{filename[:-3]}")

if __name__ == "__main__":
    bot.run(BOT_TOKEN)