import functools
import time

from config import *
from utils.settings import *
from database.core import UsersDataBase
from utils.embeds import EmbedBuilder


db = UsersDataBase()
embed_builder = EmbedBuilder()

def custom_cooldown(command_name: str):
	def decorator(func):
		@functools.wraps(func)
		async def wrapper(self, inter, *args, **kwargs):
			is_admin = any(role.id in ADMIN_ROLE_IDS for role in inter.author.roles)
			is_bot = inter.author.id == BOT_ID

			if is_admin or is_bot:
				return await func(self, inter, *args, **kwargs)
			
			cooldown = await self.bot.db.get_remaining_cooldown(inter.author.id, command_name)

			if cooldown > 0:
				formatted_cd = format_cooldown(cooldown)

				embed = embed_builder.get_embed(
                    name="error_cooldown",
                    time=formatted_cd
                )

				await inter.send(embed=embed)
				return
			
			await func(self, inter, *args, **kwargs)

			await self.bot.db.set_cooldown(inter.author.id, command_name, cooldown_second[command_name])
		
		return wrapper
	return decorator

def prison_check():
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, inter, *args, **kwargs):

            release_time = await self.bot.db.check_prison_status(inter.author.id)

            if release_time > time.time():
                embed = embed_builder.get_embed(
                    name="error_prison",
                    release_time=int(release_time),
                    author_name=inter.author.display_name,
                    author_avatar=inter.author.display_avatar.url
                )
                await inter.send(embed=embed, ephemeral=True)
                return 

            await func(self, inter, *args, **kwargs)
        
        return wrapper
    return decorator

def maintenance_check():
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, inter, *args, **kwargs):
            is_admin = any(role.id in ADMIN_ROLE_IDS for role in inter.author.roles)

            if is_admin:
                return await func(self, inter, *args, **kwargs)

            is_maintenance = await self.bot.db.get_maintenance()

            if is_maintenance:
                embed = embed_builder.get_embed(
                    name="error_maintenance",
                    icon_url=self.bot.user.display_avatar.url
                )
                
                await inter.send(embed=embed, ephemeral=True)
                return

            await func(self, inter, *args, **kwargs)
        
        return wrapper
    return decorator

def blacklist_check():
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, inter, *args, **kwargs):
            is_admin = any(role.id in ADMIN_ROLE_IDS for role in inter.author.roles)

            if is_admin:
                return await func(self, inter, *args, **kwargs)

            ban_entry = await self.bot.db.check_blacklist(inter.author.id)

            if ban_entry:
                ban_date = f"<t:{ban_entry['date']}:D>"
                
                embed = embed_builder.get_embed(
                    name="error_blacklisted",
                    reason=ban_entry['reason'],
                    date=ban_date,
                    icon_url=self.bot.user.display_avatar.url
                )
                

                await inter.send(embed=embed, ephemeral=True)
                return

            await func(self, inter, *args, **kwargs)
        
        return wrapper
    return decorator