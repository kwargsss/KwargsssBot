import disnake
import json
import statistics

from disnake.ext import commands
from utils.embeds import EmbedBuilder
from config import *


class Analytics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_view = EmbedBuilder("data/embeds.json")
        self.price_cache = {} 
        self.load_config()

    def load_config(self):
        try:
            with open("data/economy_config.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.price_cache = self._extract_costs(data)
        except FileNotFoundError:
            self.price_cache = {}

    def _extract_costs(self, data):
        costs = {}
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict) and 'cost' in value:
                    costs[key] = value['cost']
                else:
                    costs.update(self._extract_costs(value))
        return costs

    def calculate_business_value(self, biz_rows):
        total_value = 0
        biz_count = len(biz_rows)

        for row in biz_rows:
            biz_type = str(row[0]).strip() 

            price = self.price_cache.get(biz_type, 0)
            total_value += price
            
        return total_value, biz_count

    @commands.slash_command(name="экономика", description="Глобальная аналитика экономики сервера")
    async def sim_economy(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()

        users_data, biz_data, family_data = await self.bot.db.get_global_economy_data()

        if not users_data:
            return await inter.edit_original_response(content="❌ Ошибка: База пользователей пуста.")

        net_worths = [u[0] + u[1] for u in users_data]
        total_cash = sum(u[0] for u in users_data)
        total_bank = sum(u[1] for u in users_data)
        money_supply = total_cash + total_bank
        user_count = len(users_data)

        avg_wealth = money_supply / user_count if user_count > 0 else 0
        median_wealth = statistics.median(net_worths) if net_worths else 0

        net_worths.sort(reverse=True)
        top_1_count = max(1, int(user_count * 0.01))
        top_1_wealth = sum(net_worths[:top_1_count])
        wealth_concentration = (top_1_wealth / money_supply * 100) if money_supply > 0 else 0

        biz_value, biz_count = self.calculate_business_value(biz_data)
        family_treasury = sum(f[0] for f in family_data)

        cash_percent = (total_cash / money_supply * 100) if money_supply > 0 else 0
        bank_percent = (total_bank / money_supply * 100) if money_supply > 0 else 0
        
        m1_stats = (
            f"```yaml\n"
            f"Всего денег: {money_supply:,} $\n"
            f"Наличные:    {total_cash:,} $ ({int(cash_percent)}%)\n"
            f"В банках:    {total_bank:,} $ ({int(bank_percent)}%)\n"
            f"Игроков:     {user_count} чел.\n"
            f"```"
        )

        warnings = []
        
        if median_wealth < 200:
            warnings.append("📉 Нищета: Новичкам сложно. Поднимите ЗП 1-го уровня.")

        if wealth_concentration > 60:
            warnings.append("⚖️ Олигархия: Топ-1% держит >60% денег. Введите налог на богатых.")
        elif wealth_concentration < 5:
            warnings.append("☭ Уравниловка: Нет богатых игроков. Экономике не хватает стимулов.")

        invest_ratio = (biz_value / money_supply) if money_supply > 0 else 0
        if invest_ratio < 0.1 and user_count > 5:
            warnings.append("🏗️ Застой: Деньги копятся, а не тратятся. Сделайте скидки на бизнесы.")

        family_ratio = (family_treasury / money_supply) if money_supply > 0 else 0
        if family_ratio < 0.05 and user_count > 10:
             warnings.append("🏰 Слабые семьи: Казны пусты. Добавьте доход.")

        if not warnings:
            recommendation = "✅ Экономика стабильна. Критических перекосов нет."
        else:
            recommendation = "\n".join(warnings[:3])

        status_icon = "🟢"
        if wealth_concentration > 60: status_icon = "🔴"
        elif wealth_concentration > 40: status_icon = "🟡"

        inequality_stats = (
            f"> **Статус:** {status_icon}\n"
            f"> **Топ 1%:** `{wealth_concentration:.1f}%`\n"
            f"> **Медиана:** `{int(median_wealth):,} $`"
        )

        assets_stats = (
            f"Куплено бизнесов: **{biz_count}**\n"
            f"Стоимость рынка: **{biz_value:,} $**\n"
            f"В казнах семей: **{family_treasury:,} $**"
        )

        embed = self.embed_view.get_embed(
            "admin_economy_report",
            m1_stats=m1_stats,
            inequality_stats=inequality_stats,
            assets_stats=assets_stats,
            recommendation=recommendation,
            date=disnake.utils.format_dt(disnake.utils.utcnow(), "d"),
            icon_url=inter.author.display_avatar.url,
            author_avatar=inter.author.display_avatar.url
        )

        await inter.edit_original_response(embed=embed)

def setup(bot):
    bot.add_cog(Analytics(bot))