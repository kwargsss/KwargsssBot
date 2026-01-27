import random

from config import ECO_CFG
from utils.decorators import custom_cooldown, prison_check, maintenance_check, blacklist_check
from disnake.ext import commands
from utils.embeds import EmbedBuilder, format_money


embed_builder = EmbedBuilder()

class Work(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.work_cfg = ECO_CFG.get("work", {})
        self.jobs_data = self.work_cfg.get("jobs", {"1": {"name": "Дворник", "phrases": ["Работа"]}})

    @commands.slash_command(name="работа", description="Поработать и получить деньги и опыт")
    @blacklist_check()
    @maintenance_check()
    @prison_check()
    @custom_cooldown("work")
    async def work(self, inter):
        await inter.response.defer()

        user_db = await self.bot.db.get_user(inter.author)
        if not user_db:
            await self.bot.db.add_user(inter.author)
            user_db = await self.bot.db.get_user(inter.author)

        current_xp = user_db['work_xp'] if user_db['work_xp'] else 0
        current_lvl = current_xp // 100
        
        job_tier = (current_lvl // 10) + 1
        if job_tier > 20: job_tier = 20

        job_info = self.jobs_data.get(str(job_tier))
        if not job_info:
            job_info = self.jobs_data["1"]
            job_tier = 1

        job_name = job_info['name']
        phrases = job_info['phrases']
        phrase = random.choice(phrases)

        base = self.work_cfg.get("salary_base_per_tier", 50)
        lvl_bonus = self.work_cfg.get("salary_level_bonus", 5)
        rnd_min = self.work_cfg.get("salary_random_min", -10)
        rnd_max = self.work_cfg.get("salary_random_max", 20)
        
        base_salary = base * job_tier 
        level_bonus_calc = (current_lvl % 10) * lvl_bonus
        random_flux = random.randint(rnd_min, rnd_max)
        
        amount = base_salary + level_bonus_calc + random_flux
        if amount < self.work_cfg.get("min_payout", 10): 
            amount = self.work_cfg.get("min_payout", 10)

        xp_gain = random.randint(self.work_cfg.get("xp_min", 10), self.work_cfg.get("xp_max", 25))

        await self.bot.db.update_money(inter.author, amount, 0)
        await self.bot.db.update_work_xp(inter.author, xp_gain)
        
        new_xp = current_xp + xp_gain
        new_lvl = new_xp // 100
        
        embed = embed_builder.get_embed(
            "success_work",
            job_name=job_name,
            job_tier=job_tier,
            phrase=phrase,
            amount=format_money(amount),
            xp_gain=xp_gain,
            total_xp=new_xp,
            user_avatar=inter.author.display_avatar.url,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        
        if new_lvl > current_lvl:
            embed.add_field(
                name="🎉 ПОВЫШЕНИЕ УРОВНЯ!", 
                value=f"Вы достигли **{new_lvl} уровня**!\nВаша зарплата увеличена.", 
                inline=False
            )
            new_tier = (new_lvl // 10) + 1
            if new_tier > job_tier and new_tier <= 20:
                new_job_name = self.jobs_data["jobs"][str(new_tier)]['name']
                embed.add_field(
                    name="📈 КАРЬЕРНЫЙ РОСТ!", 
                    value=f"Вы получили новую должность: **{new_job_name}**!", 
                    inline=False
                )

        await inter.edit_original_response(embed=embed)

def setup(bot):
    bot.add_cog(Work(bot))