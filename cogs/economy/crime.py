import disnake
import random

from disnake.ext import commands
from utils.embeds import EmbedBuilder
from utils.decorators import prison_check, maintenance_check, blacklist_check


embed_builder = EmbedBuilder()

class Crime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_if_jailed(self, inter):
        release_time = await self.bot.db.check_prison_status(inter.author.id)
        if release_time > 0:
            embed = embed_builder.get_embed(
                name="error_prison",
                release_time=int(release_time),
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            await inter.edit_original_response(embed=embed)
            return True
        return False

    @commands.slash_command(name="ограбить", description="Попытаться ограбить пользователя")
    @blacklist_check()
    @maintenance_check()
    @prison_check()
    async def crime(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="жертва", description="Кого грабим?")
    ):
        await inter.response.defer()
        if await self.check_if_jailed(inter):
            return

        if member.id == inter.author.id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_self_action", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        
        if member.bot:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_bot_action", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        user_data = await self.bot.db.get_user(inter.author)
        target_data = await self.bot.db.get_user(member)

        if not target_data or target_data['money'] < 50:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text=f"У {member.display_name} слишком мало налички.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        target_businesses = await self.bot.db.get_user_businesses(member.id)
        
        security_level = 0
        if target_businesses:
            security_level = max(b['security_lvl'] for b in target_businesses)

        base_difficulty = 60
        defense_bonus = security_level * 2
        
        difficulty_threshold = min(95, base_difficulty + defense_bonus)

        roll = random.randint(1, 100)

        if roll > difficulty_threshold:
            max_steal = int(target_data['money'] * 0.4)
            stolen_amount = random.randint(10, max_steal)

            await self.bot.db.update_money(member, -stolen_amount, 0)
            await self.bot.db.update_money(inter.author, stolen_amount, 0)

            embed = embed_builder.get_embed(
                name="success_crime",
                target_name=member.display_name,
                amount=stolen_amount,
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            if security_level > 0:
                embed.description += f"\n🥷 Вы обошли охрану уровня **{security_level}**!"
            
            await inter.edit_original_response(embed=embed)

        else:      
            fine = 500
            jail_seconds = random.randint(3600, 7200)

            await self.bot.db.update_money(inter.author, -fine, 0)

            await self.bot.db.jail_user(inter.author.id, jail_seconds)

            hours = jail_seconds // 3600
            minutes = (jail_seconds % 3600) // 60
            time_str = f"{hours}ч {minutes}мин"

            embed = embed_builder.get_embed(
                name="fail_crime",
                target_name=member.display_name,
                fine=fine,
                time_str=time_str,
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )

            reason = "Вам просто не повезло."
            if security_level > 0 and roll > 60: 
                reason = f"🛡️ Сработала частная охрана (Ур. {security_level})!"
            elif roll <= 60:
                reason = "Вы споткнулись и упали прямо в руки полиции."

            embed.description += f"\n\n🛑 **Причина:** {reason}"

            await inter.edit_original_response(embed=embed)

def setup(bot):
    bot.add_cog(Crime(bot))