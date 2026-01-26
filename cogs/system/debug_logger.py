import disnake

from disnake.ext import commands
from utils.logger import log


class DebugLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name='crash')
    @commands.is_owner()
    async def crash(self, inter):
        result = 1 / 0
        await inter.send("Этого сообщения никто не увидит")

    @commands.slash_command(name='mega_crash')
    @commands.is_owner()
    async def megacrash(self, inter: disnake.ApplicationCommandInteraction):
        
        def recursive_bomb(depth):
            if depth <= 0:
                return 1 / 0 
            else:
                _ = f"Stack depth level: {depth}" * 2 
                return recursive_bomb(depth - 1)

        recursive_bomb(40)

    @commands.slash_command(name="log_test")
    async def test_log(self, inter, уровень: str = commands.Param(choices=["Info", "Warning", "Error", "Critical"])):
        
        message_text = f"Это тестовое сообщение уровня {уровень}. Проверка связи!"

        if уровень == "Info":
            log.info(message_text)
            await inter.send("✅ Отправлен INFO лог", ephemeral=True)
            
        elif уровень == "Warning":
            log.warning(message_text)
            await inter.send("🟠 Отправлен WARNING лог", ephemeral=True)
            
        elif уровень == "Error":
            try:
                
                1 / 0
            except Exception:
                log.error("Тестовая ошибка (имитация ZeroDivisionError)")
            await inter.send("🔴 Отправлен ERROR лог", ephemeral=True)
            
        elif уровень == "Critical":
            log.critical("🔥 СИСТЕМА ПАДАЕТ (Тест) 🔥")
            await inter.send("☠️ Отправлен CRITICAL лог", ephemeral=True)

def setup(bot):
    bot.add_cog(DebugLogger(bot))