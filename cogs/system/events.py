import disnake

from disnake.ext import commands


class SystemEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.Member):
        user = await self.bot.db.get_user(member)

        if not user:
            await self.bot.db.add_user(member)

    @commands.slash_command(name = 'add_db')
    async def add_db(self, inter, member: disnake.Member):
        try: 
            user = await self.db.get_user(member)

            if not user:
                await self.db.add_user(member)
                await inter.response.send_message(f"**[DATABASE]** Пользователь {member.name} добавлен в базу данных!", ephemeral = True)
            
            else:
                await inter.response.send_message(f"**[DATABASE]** Пользователь {member.name} есть в базе данных!", ephemeral = True)
        
        except Exception as e:
            await inter.response.send_message(f"**[ERROR]** Ошибка при добавлении пользователя в базу данных: {e}", ephemeral = True)

def setup(bot):
    bot.add_cog(SystemEvents(bot))