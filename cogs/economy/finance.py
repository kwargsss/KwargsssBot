import disnake
import json
import os
import time
import asyncio

from config import ECO_CFG
from disnake.ext import commands, tasks
from utils.embeds import EmbedBuilder, format_money
from utils.decorators import prison_check, maintenance_check, blacklist_check


embed_builder = EmbedBuilder()

class FinanceSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = ECO_CFG["finance"]
        self.finance_loop.start()

    def _load_config(self):
        path = os.path.join("data", "finance_config.json")
        if not os.path.exists(path):
            return {
                "deposits": {"3": 5, "7": 15, "30": 50, "early_penalty_percent": 10},
                "credit": {"percent": 20, "max_days": 14, "penalty_percent_per_day": 5, "rating_multiplier": 100, "min_rating_to_take": 100}
            }
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def cog_unload(self):
        self.finance_loop.cancel()

    async def render_credit_menu(self, user: disnake.Member):
        rating = await self.bot.db.get_credit_rating(user.id)
        active_loan = await self.bot.db.get_active_loan(user.id)
        
        cfg = self.config['credit']
        max_loan = rating * cfg['rating_multiplier']

        common_kwargs = {
            "rating": rating,
            "max_loan": max_loan,
            "user_avatar": user.display_avatar.url,
            "author_name": user.display_name,
            "author_avatar": user.display_avatar.url
        }

        if active_loan:
            left_to_pay = active_loan['amount_total'] - active_loan['amount_paid']
            due_time = int(active_loan['due_date'])
            
            status = "✅ Активен"
            if time.time() > active_loan['due_date']:
                status = "⚠️ Просрочен"

            embed = embed_builder.get_embed(
                "finance_credit_active",
                taken=active_loan['amount_taken'],
                left=left_to_pay,
                due_time=due_time,
                status=status,
                **common_kwargs
            )
            
            view = CreditRepayView(self.bot, self, user.id, active_loan['id'], left_to_pay)
        else:
            embed = embed_builder.get_embed(
                "finance_credit_offer",
                percent=cfg['percent'],
                days=cfg['max_days'],
                **common_kwargs
            )
            
            view = CreditTakeView(self.bot, self, user.id, max_loan, cfg)

        return embed, view

    @commands.slash_command(name="финансы", description="Банковская система")
    @blacklist_check()
    @maintenance_check()
    @prison_check()
    async def finance(self, inter):
        await inter.response.defer()
        pass

    @finance.sub_command(name="вклад", description="Управление вкладами")
    async def deposit(
        self, 
        inter,
        amount: int = commands.Param(name="сумма", description="Сумма вклада", default=0),
        days: str = commands.Param(name="срок", description="На сколько дней", choices=["3", "7", "30"], default="3")
    ):
        await inter.response.defer()
        user_db = await self.bot.db.get_user(inter.author)
        if not user_db: await self.bot.db.add_user(inter.author)

        active_deposit = await self.bot.db.get_active_deposit(inter.author.id)

        if active_deposit:
            profit = active_deposit['profit_amount']
            total = active_deposit['amount'] + profit
            end_time = int(active_deposit['end_time'])
            
            penalty_pct = self.config['deposits'].get('early_penalty_percent', 10)
            penalty_amount = int(active_deposit['amount'] * (penalty_pct / 100))
            return_amount = active_deposit['amount'] - penalty_amount

            embed = embed_builder.get_embed(
                "finance_deposit_active",
                amount=active_deposit['amount'],
                total=total,
                end_time=end_time,
                penalty_pct=penalty_pct,
                return_amount=return_amount,
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )

            view = DepositManageView(self.bot, inter.author.id, active_deposit['id'], return_amount)
            return await inter.edit_original_response(embed=embed, view=view)

        if amount == 0:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="ℹ️ Чтобы открыть вклад, укажите сумму и срок: `/финансы вклад сумма:1000 срок:7`", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        if amount < 100:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="❌ Минимальная сумма вклада — 100 монет.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        if user_db['money'] < amount:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_no_money_details", balance=user_db['money'], needed=amount, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        percent = self.config.get("deposits", {}).get(days, 5)
        
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if marriage and "family_capital" in (marriage.get('improvements') or ""):
            fam_cfg = ECO_CFG.get('family', {}).get('improvements', {}).get('family_capital', {})
            bonus_mult = fam_cfg.get('deposit_multiplier', 1.0)
            
            percent = int(percent * bonus_mult)

        profit = int(amount * (percent / 100))

        await self.bot.db.update_money(inter.author, -amount, 0)
        await self.bot.db.create_deposit(inter.author.id, amount, profit, int(days))

        embed = embed_builder.get_embed(
            "finance_deposit_new",
            amount=amount,
            days=days,
            total=amount + profit,
            percent=percent,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

    @finance.sub_command(name="кредит", description="Меню кредитования")
    async def credit_menu_cmd(self, inter):
        await inter.response.defer()
        embed, view = await self.render_credit_menu(inter.author)
        await inter.edit_original_response(embed=embed, view=view)
    
    @tasks.loop(minutes=30)
    async def finance_loop(self):
        await self.bot.wait_until_ready()
        while not getattr(self.bot, "db", None):
            await asyncio.sleep(1)

        ready_deposits = await self.bot.db.get_ready_deposits()
        for dep in ready_deposits:
            total = dep['amount'] + dep['profit_amount']
            await self.bot.db.update_money(disnake.Object(id=dep['user_id']), 0, total)
            await self.bot.db.close_deposit(dep['id'])

        loans = await self.bot.db.get_overdue_loans()
        cfg = self.config['credit']
        now = time.time()

        for loan in loans:
            if loan['amount_paid'] >= loan['amount_total']:
                await self.bot.db.close_loan(loan['id'])
                continue

            if now > loan['due_date']:
                if now - loan['last_penalty_date'] >= 86400:
                    penalty = int(loan['amount_taken'] * (cfg['penalty_percent_per_day'] / 100))
                    await self.bot.db.apply_loan_penalty(loan['id'], penalty)
                    await self.bot.db.update_credit_rating(loan['user_id'], -10)

    @finance_loop.before_loop
    async def before_finance_loop(self):
        await self.bot.wait_until_ready()

class DepositManageView(disnake.ui.View):
    def __init__(self, bot, user_id, deposit_id, return_amount):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.deposit_id = deposit_id
        self.return_amount = return_amount

    @disnake.ui.button(label="Закрыть досрочно", style=disnake.ButtonStyle.danger, emoji="💸")
    async def close_early(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.user_id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        await self.bot.db.update_money(inter.author, 0, self.return_amount)
        await self.bot.db.revoke_deposit(self.deposit_id)

        embed = embed_builder.get_embed(
            "finance_deposit_early_close",
            amount=self.return_amount,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        
        await inter.response.edit_message(embed=embed, view=None)
        self.stop()

class CreditTakeModal(disnake.ui.Modal):
    def __init__(self, bot, cog, max_amount, config):
        self.bot = bot
        self.cog = cog
        self.max_amount = max_amount
        self.cfg = config
        super().__init__(
            title="Оформление кредита",
            components=[disnake.ui.TextInput(
                label=f"Сумма (Лимит: {max_amount})",
                custom_id="amount",
                style=disnake.TextInputStyle.short,
                placeholder="Например: 5000"
            )]
        )

    async def callback(self, inter: disnake.ModalInteraction):
        try:
            amount = int(inter.text_values["amount"])
        except ValueError:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Введите корректное число.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        if amount <= 0:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_zero_amount", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        if amount > self.max_amount:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text=f"Ваш лимит превышен! Максимум: {self.max_amount}", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        rating = await self.bot.db.get_credit_rating(inter.author.id)
        if rating < self.cfg['min_rating_to_take']:
             return await inter.edit_original_response(
                 embed=embed_builder.get_embed("error_generic", text="Ваш кредитный рейтинг слишком низок.", author_avatar=inter.author.display_avatar.url),
                 ephemeral=True
             )

        total_to_pay = int(amount * (1 + self.cfg['percent'] / 100))
        
        await self.bot.db.update_money(inter.author, 0, amount)
        await self.bot.db.create_loan(inter.author.id, amount, total_to_pay, self.cfg['max_days'])

        embed, view = await self.cog.render_credit_menu(inter.author)
        await inter.response.edit_message(embed=embed, view=view)
        await inter.followup.send(
            embed=disnake.Embed(description=f"✅ Вы взяли кредит: **{format_money(amount)}**", color=disnake.Color.green()),
            ephemeral=True
        )


class CreditRepayModal(disnake.ui.Modal):
    def __init__(self, bot, cog, loan_id, left_to_pay):
        self.bot = bot
        self.cog = cog
        self.loan_id = loan_id
        self.left = left_to_pay
        super().__init__(
            title="Погашение кредита",
            components=[disnake.ui.TextInput(
                label=f"Сумма (Долг: {left_to_pay})",
                custom_id="amount",
                style=disnake.TextInputStyle.short
            )]
        )

    async def callback(self, inter: disnake.ModalInteraction):
        try:
            amount = int(inter.text_values["amount"])
        except:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Ошибка ввода.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        if amount <= 0:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_zero_amount", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        if amount > self.left: amount = self.left

        bank_money = await self.bot.db.get_balance(inter.author, "bank")
        if bank_money < amount:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_no_money_details", balance=bank_money, needed=amount, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        await self.bot.db.update_money(inter.author, 0, -amount)
        await self.bot.db.repay_loan_part(self.loan_id, amount)

        msg = f"✅ Внесено: **{amount}**."
        if amount == self.left:
            await self.bot.db.close_loan(self.loan_id)
            await self.bot.db.update_credit_rating(inter.author.id, 5)
            msg += " 🎊 Кредит закрыт! Рейтинг повышен."

        embed, view = await self.cog.render_credit_menu(inter.author)
        await inter.response.edit_message(embed=embed, view=view)
        await inter.followup.send(
            embed=disnake.Embed(description=msg, color=disnake.Color.green()),
            ephemeral=True
        )


class CreditTakeView(disnake.ui.View):
    def __init__(self, bot, cog, user_id, max_loan, config):
        super().__init__(timeout=60)
        self.bot = bot
        self.cog = cog
        self.user_id = user_id
        self.max_loan = max_loan
        self.cfg = config

    @disnake.ui.button(label="Взять кредит", style=disnake.ButtonStyle.success, emoji="🖊️")
    async def take_loan(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.user_id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        await inter.response.send_modal(CreditTakeModal(self.bot, self.cog, self.max_loan, self.cfg))

class CreditRepayView(disnake.ui.View):
    def __init__(self, bot, cog, user_id, loan_id, left_to_pay):
        super().__init__(timeout=60)
        self.bot = bot
        self.cog = cog
        self.user_id = user_id
        self.loan_id = loan_id
        self.left = left_to_pay

    @disnake.ui.button(label="Погасить", style=disnake.ButtonStyle.primary, emoji="💳")
    async def repay(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.user_id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        await inter.response.send_modal(CreditRepayModal(self.bot, self.cog, self.loan_id, self.left))

def setup(bot):
    bot.add_cog(FinanceSystem(bot))