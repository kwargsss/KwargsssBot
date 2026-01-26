import disnake
import asyncio
import random

from config import SELL_RATIO, ECONOMY_NEWS_CHANNEL_ID, MAX_UPGRADE_LEVEL, ECO_CFG
from disnake.ext import commands, tasks
from utils.embeds import EmbedBuilder, format_money
from utils.decorators import prison_check
from utils.commission import commission_manager


embed_builder = EmbedBuilder() 

class BizConfigWrapper:
    def __init__(self):
        self.data = ECO_CFG["business"]
        self.types = self.data.get("types", {})
        self.upgrades = self.data.get("upgrades", {})
        self.economy_events = self.data.get("market_events", [])
        self.supply_price = self.data.get("supply_price", 10)
        self.tick_time = self.data.get("tick_time_seconds", 600)
        self.upgrade_exponent = self.data.get("upgrade_cost_exponent", 1.5)
        self.current_factor = 1.0
        self.current_status = "Стабильность"

CFG = BizConfigWrapper()

async def render_dashboard(bot, user: disnake.Member, index: int = 0):
    all_businesses = await bot.db.get_user_businesses(user.id)
    
    if not all_businesses:
        return None, None

    if index >= len(all_businesses): index = 0
    if index < 0: index = len(all_businesses) - 1

    biz = all_businesses[index]
    info = CFG.types.get(biz['type'])
    if not info: return None, None

    log_bonus = biz.get('logistics_lvl', 0) * CFG.upgrades.get('logistics', {}).get('add_storage', 0)
    max_storage = info['storage'] + log_bonus
    
    mark_lvl = biz.get('marketing_lvl', 0)
    mark_pct = int((mark_lvl * (CFG.upgrades.get('marketing', {}).get('multiplier', 1.15) - 1)) * 100)

    pct = min(100, int((biz['supplies'] / max_storage) * 100)) if max_storage > 0 else 0
    filled = int(pct / 10)
    bar = "🟦" * filled + "⬜" * (10 - filled)

    levels_info = (
        f"📢 Маркетинг: **{mark_lvl}** (+{mark_pct}%)\n"
        f"🚚 Логистика: **{biz.get('logistics_lvl',0)}** (+{log_bonus})\n"
        f"🛡️ Охрана: **{biz.get('security_lvl',0)}**\n"
        f"🛠️ Автоматизация: **{biz.get('automation_lvl',0)}**\n"
        f"🏝️ Оффшоры: **{biz.get('offshore_lvl',0)}**"
    )
    
    if info['consume'] > 0:
        cycles = biz['supplies'] // info['consume']
        mins = cycles * (CFG.tick_time // 60)
        status = f"🟢 Работает ({mins} мин)" if biz['supplies'] >= info['consume'] else "🔴 Остановлен (Нет сырья)"
    else:
        status = "🟢 Вечный двигатель"

    count_str = f" ({index + 1}/{len(all_businesses)})" if len(all_businesses) > 1 else ""

    if CFG.current_factor < 0.9:
        econ_icon = "📉"
        econ_color = "Скидки"
    elif CFG.current_factor > 1.1:
        econ_icon = "📈"
        econ_color = "Дефицит"
    else:
        econ_icon = "📊"
        econ_color = "Стабильность"

    economy_text = (
        f"{econ_icon} Рынок: **{CFG.current_status}**\n"
        f"💵 Цена закупки: **{format_money(int(CFG.supply_price * CFG.current_factor))}** (x{CFG.current_factor})"
    )

    embed = embed_builder.get_embed(
        name="biz_dashboard",
        biz_name=f"{info['name']}{count_str}",
        economy_status=economy_text,
        author_name=user.display_name,
        author_avatar=user.display_avatar.url,
        balance=biz['balance'],
        supplies=biz['supplies'],
        max_storage=max_storage,
        storage_progress=bar,
        levels_info=levels_info,
        status=status,
    )

    view = BizDashboardView(bot, user.id, biz, index, len(all_businesses))
    return embed, view

class BizSellSelect(disnake.ui.StringSelect):
    def __init__(self, bot, businesses):
        self.bot = bot
        self.businesses_map = {str(b['id']): b for b in businesses}
        
        options = []
        for b in businesses:
            info = CFG.types.get(b['type'])
            if not info: continue
            
            sell_price = int(info['cost'] * SELL_RATIO)
            price_fmt = format_money(sell_price)
            
            options.append(disnake.SelectOption(
                label=f"{info['name']}",
                description=f"Продать за {price_fmt} монет",
                value=str(b['id']),
                emoji="🔻"
            ))

        super().__init__(
            placeholder="Выберите бизнес для продажи...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, inter: disnake.MessageInteraction):
        biz_id = self.values[0]
        biz_data = self.businesses_map.get(biz_id)
        
        if not biz_data:
            return await inter.send(
                embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
            
        info = CFG.types.get(biz_data['type'])
        sell_price = int(info['cost'] * SELL_RATIO)

        embed = embed_builder.get_embed(
            "biz_sell_confirm",
            biz_name=info['name'],
            amount=sell_price,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        view = BizSellConfirmView(self.bot, inter.author.id, biz_data, sell_price, info['name'])
        await inter.response.edit_message(embed=embed, view=view)

class BizSellSelectView(disnake.ui.View):
    def __init__(self, bot, businesses):
        super().__init__(timeout=60)
        self.add_item(BizSellSelect(bot, businesses))

class SuppliesModal(disnake.ui.Modal):
    def __init__(self, bot, biz_data, index):
        self.bot = bot
        self.biz_data = biz_data
        self.index = index

        base_price = CFG.supply_price
        self.current_price = int(base_price * CFG.current_factor)
        
        components = [
            disnake.ui.TextInput(
                label="Количество сырья",
                placeholder=f"Цена сейчас: {format_money(self.current_price)}/ед.",
                custom_id="amount",
                style=disnake.TextInputStyle.short,
                max_length=5
            )
        ]
        super().__init__(title="Закупка сырья", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        try:
            amount = int(inter.text_values["amount"])
        except ValueError:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Введите корректное число.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        if amount <= 0:
            return await inter.send(
                embed=embed_builder.get_embed("error_zero_amount", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        cost = amount * self.current_price
        user_money = await self.bot.db.get_balance(inter.author, "money")

        if user_money < cost:
            return await inter.send(
                embed=embed_builder.get_embed("error_no_money_details", balance=user_money, needed=cost, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        biz_type_info = CFG.types[self.biz_data['type']]
        log_bonus = self.biz_data.get('logistics_lvl', 0) * CFG.upgrades.get('logistics', {}).get('add_storage', 0)
        max_storage = biz_type_info['storage'] + log_bonus
        
        if self.biz_data['supplies'] + amount > max_storage:
             free = max_storage - self.biz_data['supplies']
             return await inter.send(
                 embed=embed_builder.get_embed("error_generic", text=f"Склад переполнен! Свободно мест: {free}", author_avatar=inter.author.display_avatar.url),
                 ephemeral=True
             )

        await self.bot.db.update_money(inter.author, -cost, 0)
        await self.bot.db.update_biz_stats(self.biz_data['id'], amount, 0)
        
        embed, view = await render_dashboard(self.bot, inter.author, self.index)
        await inter.response.edit_message(embed=embed, view=view)


class UpgradeView(disnake.ui.View):
    def __init__(self, bot, owner_id, biz_data, index):
        super().__init__(timeout=60)
        self.bot = bot
        self.owner_id = owner_id
        self.biz_data = biz_data
        self.index = index
        
        for key, info in CFG.upgrades.items():
            lvl = biz_data.get(f"{key}_lvl", 0)
            
            if lvl >= MAX_UPGRADE_LEVEL:
                button = disnake.ui.Button(
                    label=f"{info['name']} (МАКС)",
                    custom_id=key,
                    style=disnake.ButtonStyle.secondary,
                    emoji="✅",
                    disabled=True
                )
            else:
                cost = int(info['cost'] * (CFG.upgrade_exponent ** lvl))
                cost_fmt = format_money(cost)
                button = disnake.ui.Button(
                    label=f"{info['name']} (Lvl {lvl+1}) - {cost_fmt}",
                    custom_id=key,
                    style=disnake.ButtonStyle.secondary,
                    emoji="🛠️"
                )
                button.callback = self.make_callback(key, cost, info['name'])
            
            self.add_item(button)

    def make_callback(self, key, cost, name):
        async def callback(inter: disnake.MessageInteraction):
            if inter.author.id != self.owner_id: return
            
            money = await self.bot.db.get_balance(inter.author, "money")
            if money < cost:
                return await inter.send(
                    embed=embed_builder.get_embed("error_no_money_details", balance=money, needed=cost, author_avatar=inter.author.display_avatar.url),
                    ephemeral=True
                )
            
            await self.bot.db.update_money(inter.author, -cost, 0)
            await self.bot.db.upgrade_biz(self.biz_data['id'], f"{key}_lvl")

            new_biz_data = await self.bot.db.get_business_by_id(self.biz_data['id'])
            new_view = UpgradeView(self.bot, self.owner_id, new_biz_data, self.index)
            await inter.response.edit_message(view=new_view)
            
        return callback

    @disnake.ui.button(label="🔙 Назад", style=disnake.ButtonStyle.danger, row=4)
    async def back_to_dash(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        embed, view = await render_dashboard(self.bot, inter.author, self.index)
        await inter.response.edit_message(embed=embed, view=view)

class BizSellConfirmView(disnake.ui.View):
    def __init__(self, bot, owner_id, biz_data, sell_price, biz_name):
        super().__init__(timeout=60)
        self.bot = bot
        self.owner_id = owner_id
        self.biz_data = biz_data
        self.sell_price = sell_price
        self.biz_name = biz_name

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.send(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
            return False
        return True

    @disnake.ui.button(label="✅ Подтвердить продажу", style=disnake.ButtonStyle.danger)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        exists = await self.bot.db.get_business_by_id(self.biz_data['id'])
        if not exists:
            return await inter.send(
                embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        await self.bot.db.delete_business(self.biz_data['id'])

        await self.bot.db.update_money(inter.author, self.sell_price, 0)

        embed = embed_builder.get_embed(
            "success_sell_biz",
            biz_name=self.biz_name,
            amount=self.sell_price,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )

        await inter.response.edit_message(embed=embed, view=None)
        self.stop()

    @disnake.ui.button(label="❌ Отмена", style=disnake.ButtonStyle.secondary)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        embed = disnake.Embed(title="❌ Отмена", description="Продажа отменена.", color=disnake.Color.red())
        await inter.response.edit_message(embed=embed, view=None)
        self.stop()

class BizDashboardView(disnake.ui.View):
    def __init__(self, bot, owner_id, biz_data, index, total_count):
        super().__init__(timeout=60)
        self.bot = bot
        self.owner_id = owner_id
        self.biz_data = biz_data
        self.index = index
        self.total_count = total_count

        if total_count > 1:
            self.prev_btn = disnake.ui.Button(label="⬅️", style=disnake.ButtonStyle.secondary, row=1)
            self.prev_btn.callback = self.prev_page
            self.add_item(self.prev_btn)

            self.next_btn = disnake.ui.Button(label="➡️", style=disnake.ButtonStyle.secondary, row=1)
            self.next_btn.callback = self.next_page
            self.add_item(self.next_btn)

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.send(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
            return False
        return True

    async def prev_page(self, inter: disnake.MessageInteraction):
        embed, view = await render_dashboard(self.bot, inter.author, self.index - 1)
        await inter.response.edit_message(embed=embed, view=view)

    async def next_page(self, inter: disnake.MessageInteraction):
        embed, view = await render_dashboard(self.bot, inter.author, self.index + 1)
        await inter.response.edit_message(embed=embed, view=view)

    @disnake.ui.button(label="📦 Закупить сырье", style=disnake.ButtonStyle.primary, row=0)
    async def buy_supplies(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_modal(SuppliesModal(self.bot, self.biz_data, self.index))

    @disnake.ui.button(label="💰 Снять прибыль", style=disnake.ButtonStyle.success, row=0)
    async def collect_money(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        current = await self.bot.db.get_business_by_id(self.biz_data['id'])
        balance = current['balance']
        
        if balance <= 0:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="В кассе пусто.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        offshore_lvl = self.biz_data.get('offshore_lvl', 0)

        evasion_per_lvl = CFG.upgrades.get('offshore', {}).get('tax_evasion', 0.0)

        discount = offshore_lvl * evasion_per_lvl

        if discount > 1.0: discount = 1.0

        tax, net_profit = commission_manager.calculate(balance, "business_withdraw", discount_factor=discount)

        await self.bot.db.update_biz_stats(self.biz_data['id'], 0, -balance)

        await self.bot.db.update_money(inter.author, net_profit, 0)

        embed, view = await render_dashboard(self.bot, inter.author, self.index)

        await inter.response.edit_message(embed=embed, view=view)
 
        msg = f"✅ Вы сняли выручку: **{format_money(net_profit)}**"
        
        if tax > 0:
            base_tax_percent = int(commission_manager.rates.get("business_withdraw", 0) * 100)
            msg += f"\n📉 Налог ({base_tax_percent}%): **{format_money(tax)}**"
            
            if discount > 0:
                saved_percent = int(discount * 100)
                msg += f"\n🏝️ Оффшоры (Ур. {offshore_lvl}) снизили налог на **{saved_percent}%**!"
                
        elif discount >= 1.0 and balance > 0:
            msg += "\n🏝️ **Налог не уплачен** (Оффшоры 100%)"
            
        success_embed = disnake.Embed(description=msg, color=disnake.Color.green())
        await inter.send(embed=success_embed, ephemeral=True)

    @disnake.ui.button(label="🛠️ Улучшения", style=disnake.ButtonStyle.secondary, row=0)
    async def upgrades(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        embed = embed_builder.get_embed(
            "biz_upgrade_menu", 
            max_lvl=15,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        view = UpgradeView(self.bot, self.owner_id, self.biz_data, self.index)
        await inter.response.edit_message(embed=embed, view=view)

class Business(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.biz_loop.start()
        self.economy_loop.start()

    def cog_unload(self):
        self.biz_loop.cancel()
        self.economy_loop.cancel()

    @tasks.loop(hours=4)
    async def economy_loop(self):
        if not CFG.economy_events:
            return

        event = random.choice(CFG.economy_events)

        min_f = event["min_factor"]
        max_f = event["max_factor"]
        name = event["name"]
        
        new_factor = round(random.uniform(min_f, max_f), 2)

        await self.bot.db.update_economy_state(new_factor, name)

        CFG.current_factor = new_factor
        CFG.current_status = name

        if ECONOMY_NEWS_CHANNEL_ID:
            channel = self.bot.get_channel(ECONOMY_NEWS_CHANNEL_ID)
            if not channel:
                channel = await self.bot.fetch_channel(ECONOMY_NEWS_CHANNEL_ID)
            
            if channel:
                base = CFG.supply_price
                new_price = int(base * new_factor)
                
                color = disnake.Color.green() if new_factor < 1.0 else disnake.Color.red()
                if 0.9 <= new_factor <= 1.1: color = disnake.Color.blue()
                
                embed = disnake.Embed(title=f"Экономические новости", color=color)
                embed.description = (
                    f"**{name}**\n"
                    f"Коэффициент рынка: **x{new_factor}**\n"
                    f"Цена за ед. сырья: **{format_money(new_price)}**"
                )
                embed.timestamp = disnake.utils.utcnow()
                
                await channel.send(embed=embed)

    @economy_loop.before_loop
    async def before_economy_loop(self):
        await self.bot.wait_until_ready()
        while not getattr(self.bot, "db", None):
            await asyncio.sleep(1)

        factor, status = await self.bot.db.get_economy_state()
        CFG.current_factor = factor
        CFG.current_status = status

    @tasks.loop(seconds=CFG.tick_time)
    async def biz_loop(self):
        async with self.bot.db.conn.execute("SELECT * FROM businesses") as cursor:
            businesses = await cursor.fetchall()
        
        for biz in businesses:
            biz = dict(biz)
            info = CFG.types.get(biz['type'])
            if not info: continue

            auto_lvl = biz.get('automation_lvl', 0)
            reduce = auto_lvl * CFG.upgrades.get('automation', {}).get('reduce_consume', 0)
            consume = max(1, info['consume'] - reduce)
            
            if biz['supplies'] >= consume:
                mark_lvl = biz.get('marketing_lvl', 0)
                mark_bonus = CFG.upgrades.get('marketing', {}).get('multiplier', 1.0)
                multiplier = 1 + (mark_lvl * (mark_bonus - 1))
                income = int(info['income'] * multiplier)

                await self.bot.db.update_biz_stats(biz['id'], -consume, income)

    @biz_loop.before_loop
    async def before_biz_loop(self):
        await self.bot.wait_until_ready()
        while not getattr(self.bot, "db", None):
            await asyncio.sleep(1)

    @commands.slash_command(name="бизнес", description="Управление бизнесом")
    @prison_check()
    async def business(self, inter):
        pass

    async def biz_autocomplete(self, inter, string: str):
        selected_type = inter.filled_options.get("тип")
        
        if not selected_type:
            return ["⬅️ Сначала выберите категорию бизнеса!"]

        choices = []
        for key, info in CFG.types.items():
            if key.startswith(selected_type):
                if string.lower() in info['name'].lower():
                    choices.append(f"{info['name']} — {format_money(info['cost'])}")
        
        return choices[:25]

    @business.sub_command(name="инфо", description="Панель управления бизнесом")
    @prison_check()
    async def biz_info(self, inter):
        embed, view = await render_dashboard(self.bot, inter.author)
        
        if not embed:
            embed = embed_builder.get_embed(
                "biz_no_business",
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            return await inter.send(embed=embed)
            
        await inter.send(embed=embed, view=view)

    @business.sub_command(name="купить", description="Купить новый бизнес")
    @prison_check()
    async def buy(
        self, 
        inter,
        biz_type: str = commands.Param(
            name="тип",
            description="Категория бизнеса",
            choices={
                "🏪 Ларьки (Начальные)": "stall",
                "🏭 Заводы (Продвинутые)": "factory",
                "🚀 Корпорации (Элитные)": "corp"
            }
        ),
        biz_name: str = commands.Param(
            name="бизнес",
            description="Выберите конкретное предприятие",
            autocomplete=biz_autocomplete
        )
    ):
        
        if biz_name == "⬅️ Сначала выберите категорию бизнеса!":
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Вы не выбрали бизнес.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        selected_key = None
        for key, info in CFG.types.items():
            if biz_name.startswith(info['name']):
                if key.startswith(biz_type):
                    selected_key = key
                    break
        
        if not selected_key:
            return await inter.send(
                embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        user_businesses = await self.bot.db.get_user_businesses(inter.author.id)
        for biz in user_businesses:
            if biz['type'] == selected_key:
                return await inter.send(
                    embed=embed_builder.get_embed("error_generic", text=f"У вас уже есть **{CFG.types[selected_key]['name']}**!", author_avatar=inter.author.display_avatar.url),
                    ephemeral=True
                )

        info = CFG.types[selected_key]
        cost = info['cost']

        marriage = await self.bot.db.get_marriage(inter.author.id)
        if marriage and "family_capital" in (marriage.get('improvements') or ""):
             fam_cfg = ECO_CFG.get('family', {}).get('improvements', {}).get('family_capital', {})
             discount_pct = fam_cfg.get('discount_percent', 0)
             cost = int(cost * (1 - (discount_pct / 100)))

        user_db = await self.bot.db.get_user(inter.author)
        if user_db['money'] < cost:
            return await inter.send(
                embed=embed_builder.get_embed("error_no_money_details", balance=user_db['money'], needed=cost, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        await self.bot.db.update_money(inter.author, -cost, 0)
        await self.bot.db.create_business(inter.author.id, selected_key)

        embed = embed_builder.get_embed(
            "biz_buy_success",
            biz_name=info['name'],
            price=format_money(cost),
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.send(embed=embed)

    @business.sub_command(name="продать", description="Продать один из своих бизнесов")
    @prison_check()
    async def biz_sell(self, inter):
        businesses = await self.bot.db.get_user_businesses(inter.author.id)
        
        if not businesses:
            embed = embed_builder.get_embed(
                "biz_no_business",
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            return await inter.send(embed=embed)

        if len(businesses) == 1:
            biz_data = businesses[0]
            info = CFG.types.get(biz_data['type'])
            if not info: return await inter.send(embed=disnake.Embed(description="Ошибка конфигурации бизнеса", color=disnake.Color.red()), ephemeral=True)
            
            sell_price = int(info['cost'] * SELL_RATIO)
            
            embed = embed_builder.get_embed(
                "biz_sell_confirm",
                biz_name=info['name'],
                amount=sell_price,
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            view = BizSellConfirmView(self.bot, inter.author.id, biz_data, sell_price, info['name'])
            await inter.send(embed=embed, view=view)
            return

        embed = embed_builder.get_embed(
            "biz_sell_select",
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        view = BizSellSelectView(self.bot, businesses)
        await inter.send(embed=embed, view=view)

def setup(bot):
    bot.add_cog(Business(bot))