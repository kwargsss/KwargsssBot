import disnake
import random
import asyncio

from config import *
from config import WEDDING_PRICE, ECO_CFG
from disnake.ext import commands, tasks
from utils.embeds import EmbedBuilder, format_money
from utils.decorators import custom_cooldown, maintenance_check, prison_check, blacklist_check
from utils.commission import commission_manager 


embed_builder = EmbedBuilder()

FAM_CFG = ECO_CFG.get("family", {})
BIZ_CFG = ECO_CFG.get("business", {})
TICK_TIME = ECO_CFG["business"].get("tick_time_seconds", 600)

class ImprovementsView(disnake.ui.View):
    def __init__(self, bot, author_id, marriage):
        super().__init__(timeout=60)
        self.bot = bot
        self.author_id = author_id
        self.marriage = marriage
        
        current_imps = marriage['improvements'].split(',') if marriage['improvements'] else []
        
        for key, info in FAM_CFG.get("improvements", {}).items():
            purchased = key in current_imps
            can_buy = marriage['level'] >= info['level_req'] and marriage['balance'] >= info['price']
            
            label = f"{info['name']} (Lvl {info['level_req']})"
            if purchased:
                style = disnake.ButtonStyle.secondary
                label += " [Куплено]"
                disabled = True
            elif can_buy:
                style = disnake.ButtonStyle.success
                label += f" - {format_money(info['price'])}"
                disabled = False
            else:
                style = disnake.ButtonStyle.danger
                label += f" - {format_money(info['price'])}"
                disabled = True
                
            button = disnake.ui.Button(label=label, custom_id=key, style=style, disabled=disabled)
            button.callback = self.make_callback(key, info)
            self.add_item(button)

    def make_callback(self, key, info):
        async def callback(inter: disnake.MessageInteraction):
            if inter.author.id != self.author_id: return
            
            m = await self.bot.db.get_marriage(self.author_id)
            if m['balance'] < info['price']:
                embed = embed_builder.get_embed("error_no_money_details", balance=m['balance'], needed=info['price'], author_avatar=inter.author.display_avatar.url)
                return await inter.edit_original_response(embed=embed)
                
            await self.bot.db.update_family_balance(m['id'], -info['price'])
            await self.bot.db.add_family_improvement(m['id'], key)
            
            embed = embed_builder.get_embed("family_improvement_success", imp_name=info['name'], author_avatar=inter.author.display_avatar.url)
            
            new_m = await self.bot.db.get_marriage(self.author_id)
            await inter.response.edit_message(embed=embed, view=ImprovementsView(self.bot, self.author_id, new_m))
        return callback

class FamilyBizDashboardView(disnake.ui.View):
    def __init__(self, bot, user_id, marriage_id, biz_data, index, total_count):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.marriage_id = marriage_id
        self.biz_data = biz_data
        self.index = index
        self.total_count = total_count

        self.add_item(self.create_action_btn("📦 Закупить сырье", disnake.ButtonStyle.primary, "supplies"))
        self.add_item(self.create_action_btn("💰 Снять прибыль", disnake.ButtonStyle.success, "collect"))
        self.add_item(self.create_action_btn("🛠️ Улучшения", disnake.ButtonStyle.secondary, "upgrades"))

        if total_count > 1:
            self.add_item(self.create_nav_btn("⬅️", -1))
            self.add_item(self.create_nav_btn("➡️", 1))

    def create_nav_btn(self, label, direction):
        btn = disnake.ui.Button(label=label, style=disnake.ButtonStyle.secondary, row=1)
        async def callback(inter):
            if inter.author.id != self.user_id: return
            await render_family_biz_dashboard(self.bot, inter, self.index + direction, edit=True)
        btn.callback = callback
        return btn

    def create_action_btn(self, label, style, action):
        btn = disnake.ui.Button(label=label, style=style, row=0)
        async def callback(inter):
            if inter.author.id != self.user_id: return
            if action == "supplies":
                await inter.response.send_modal(FamilySuppliesModal(self.bot, self.biz_data, self.index))
            elif action == "collect":
                await self.collect_money(inter)
            elif action == "upgrades":
                embed = embed_builder.get_embed("biz_upgrade_menu", max_lvl=15, author_avatar=inter.author.display_avatar.url)
                view = FamilyUpgradeView(self.bot, self.user_id, self.marriage_id, self.biz_data, self.index)
                await inter.response.edit_message(embed=embed, view=view)
        btn.callback = callback
        return btn

    async def collect_money(self, inter):
        current = await self.bot.db.get_family_business(self.biz_data['id'])
        balance = current['balance']
        
        if balance <= 0:
            return await inter.edit_original_response(embed=embed_builder.get_embed("error_generic", text="Касса пуста.", author_avatar=inter.author.display_avatar.url))

        offshore_lvl = self.biz_data.get('offshore_lvl', 0)
        evasion_per_lvl = BIZ_CFG['upgrades'].get('offshore', {}).get('tax_evasion', 0.0)
        discount = min(1.0, offshore_lvl * evasion_per_lvl)
        
        tax, net_profit = commission_manager.calculate(balance, "business_withdraw", discount_factor=discount)

        await self.bot.db.update_family_biz_stats(self.biz_data['id'], 0, -balance)
        await self.bot.db.update_family_balance(self.marriage_id, net_profit)

        await render_family_biz_dashboard(self.bot, inter, self.index, edit=True)
        await inter.edit_original_response(f"✅ В семейный бюджет зачислено: **{format_money(net_profit)}**")

class FamilySuppliesModal(disnake.ui.Modal):
    def __init__(self, bot, biz_data, index):
        self.bot = bot
        self.biz_data = biz_data
        self.index = index
        self.supply_price = BIZ_CFG.get("supply_price", 10)
        
        super().__init__(
            title="Закупка сырья (Семья)",
            components=[disnake.ui.TextInput(label="Количество", custom_id="amount", placeholder=f"Цена: {self.supply_price}$/ед.")]
        )

    async def callback(self, inter: disnake.ModalInteraction):
        try: amount = int(inter.text_values["amount"])
        except: return
        if amount <= 0: return
        
        cost = amount * self.supply_price
        marriage = await self.bot.db.get_marriage(inter.author.id)
        
        if marriage['balance'] < cost:
            return await inter.edit_original_response(f"В семье недостаточно денег! Нужно: {cost}")
            
        type_info = FAM_CFG['businesses'][self.biz_data['type']]
        log_bonus = self.biz_data.get('logistics_lvl', 0) * BIZ_CFG['upgrades']['logistics']['add_storage']
        max_storage = type_info['storage'] + log_bonus
        free = max_storage - self.biz_data['supplies']

        if self.biz_data['supplies'] + amount > max_storage:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text=f"Склад переполнен! Свободно мест: {free}", author_avatar=inter.author.display_avatar.url)
            )

        await self.bot.db.update_family_balance(marriage['id'], -cost)
        await self.bot.db.update_family_biz_stats(self.biz_data['id'], amount, 0)
        
        await render_family_biz_dashboard(self.bot, inter, self.index, edit=True)

class FamilyBizSellSelect(disnake.ui.StringSelect):
    def __init__(self, bot, businesses, user_id, marriage_id):
        self.bot = bot
        self.businesses_map = {str(b['id']): b for b in businesses}
        self.user_id = user_id
        self.marriage_id = marriage_id
        self.sell_ratio = ECO_CFG.get("global", {}).get("sell_ratio", 0.5)
        
        options = []
        for b in businesses:
            info = FAM_CFG['businesses'].get(b['type'])
            if not info: continue
            
            sell_price = int(info['cost'] * SELL_RATIO)
            price_fmt = format_money(sell_price)
            
            options.append(disnake.SelectOption(
                label=f"{info['name']}",
                description=f"Продать за {price_fmt}",
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
        if inter.author.id != self.user_id: return

        biz_id = self.values[0]
        biz_data = self.businesses_map.get(biz_id)
        
        if not biz_data:
            return await inter.edit_original_response(embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url))
            
        info = FAM_CFG['businesses'].get(biz_data['type'])
        sell_price = int(info['cost'] * self.sell_ratio)    

        embed = embed_builder.get_embed(
            "family_biz_sell_confirm",
            biz_name=info['name'],
            amount=format_money(sell_price),
            author_avatar=inter.author.display_avatar.url
        )
        view = FamilyBizSellConfirmView(self.bot, self.user_id, self.marriage_id, biz_data, sell_price, info['name'])
        await inter.response.edit_message(embed=embed, view=view)

class FamilyBizSellSelectView(disnake.ui.View):
    def __init__(self, bot, businesses, user_id, marriage_id):
        super().__init__(timeout=60)
        self.add_item(FamilyBizSellSelect(bot, businesses, user_id, marriage_id))

class FamilyUpgradeView(disnake.ui.View):
    def __init__(self, bot, user_id, marriage_id, biz_data, index):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.marriage_id = marriage_id
        self.biz_data = biz_data
        self.index = index
        
        for key, info in BIZ_CFG['upgrades'].items():
            lvl = biz_data.get(f"{key}_lvl", 0)
            cost = int(info['cost'] * (BIZ_CFG['upgrade_cost_exponent'] ** lvl))
            
            button = disnake.ui.Button(
                label=f"{info['name']} (Lvl {lvl+1}) - {format_money(cost)}",
                custom_id=key,
                style=disnake.ButtonStyle.secondary
            )
            button.callback = self.make_callback(key, cost)
            self.add_item(button)
            
    def make_callback(self, key, base_cost):
        async def callback(inter):
            if inter.author.id != self.user_id: return
            
            marriage = await self.bot.db.get_marriage(self.user_id)
            has_capital = "family_capital" in (marriage['improvements'] or "")
            
            final_cost = base_cost
            if has_capital:
                discount = FAM_CFG['improvements']['family_capital']['discount_percent'] / 100
                final_cost = int(base_cost * (1 - discount))
            
            if marriage['balance'] < final_cost:
                return await inter.edit_original_response(f"В семье мало денег! Нужно: {final_cost}")
                
            await self.bot.db.update_family_balance(self.marriage_id, -final_cost)
            await self.bot.db.upgrade_family_biz(self.biz_data['id'], f"{key}_lvl")
            
            new_biz = await self.bot.db.get_family_business(self.biz_data['id'])
            view = FamilyUpgradeView(self.bot, self.user_id, self.marriage_id, new_biz, self.index)
            embed = inter.message.embeds[0]
            await inter.response.edit_message(embed=embed, view=view)
        return callback
        
    @disnake.ui.button(label="🔙 Назад", style=disnake.ButtonStyle.danger, row=4)
    async def back(self, button, inter):
        await render_family_biz_dashboard(self.bot, inter, self.index, edit=True)

class FamilyBizSellConfirmView(disnake.ui.View):
    def __init__(self, bot, user_id, marriage_id, biz_data, sell_price, biz_name):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.marriage_id = marriage_id
        self.biz_data = biz_data
        self.sell_price = sell_price
        self.biz_name = biz_name

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.user_id:
            await inter.edit_original_response(embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url))
            return False
        return True

    @disnake.ui.button(label="✅ Подтвердить продажу", style=disnake.ButtonStyle.danger)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        exists = await self.bot.db.get_family_business(self.biz_data['id'])
        if not exists:
            return await inter.edit_original_response(embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url))

        await self.bot.db.delete_family_business(self.biz_data['id'])
        await self.bot.db.update_family_balance(self.marriage_id, self.sell_price)

        embed = embed_builder.get_embed(
            "family_biz_sell_success",
            biz_name=self.biz_name,
            amount=format_money(self.sell_price),
            author_avatar=inter.author.display_avatar.url
        )

        await inter.response.edit_message(embed=embed, view=None)
        self.stop()

    @disnake.ui.button(label="❌ Отмена", style=disnake.ButtonStyle.secondary)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        embed = disnake.Embed(title="❌ Отмена", description="Продажа отменена.", color=disnake.Color.red())
        await inter.response.edit_message(embed=embed, view=None)
        self.stop()

async def render_family_biz_dashboard(bot, inter, index=0, edit=False):
    marriage = await bot.db.get_marriage(inter.author.id)
    if not marriage: 
        if not edit:
            return await inter.edit_original_response(embed=embed_builder.get_embed("error_generic", text="У вас нет семьи.", author_avatar=inter.author.display_avatar.url))
        return
    
    businesses = await bot.db.get_family_businesses(marriage['id'])
    if not businesses:
        embed = embed_builder.get_embed("error_generic", text="У вашей семьи нет бизнесов.", author_avatar=inter.author.display_avatar.url)
        if edit: return 
        return await inter.edit_original_response(embed=embed)
        
    if index >= len(businesses): index = 0
    if index < 0: index = len(businesses) - 1
    
    biz = businesses[index]
    info = FAM_CFG['businesses'].get(biz['type'])
    if not info: return 
    
    log_bonus = biz.get('logistics_lvl', 0) * BIZ_CFG['upgrades']['logistics']['add_storage']
    max_storage = info['storage'] + log_bonus
    pct = min(100, int((biz['supplies'] / max_storage) * 100)) if max_storage > 0 else 0
    bar = "🟦" * (pct // 10) + "⬜" * (10 - (pct // 10))
    
    levels = []
    for key, upg in BIZ_CFG['upgrades'].items():
        levels.append(f"{upg['name']}: {biz.get(f'{key}_lvl', 0)}")
    
    status = "🟢 Работает" if biz['supplies'] >= info['consume'] else "🔴 Нет сырья"
    owners = f"<@{marriage['user1_id']}> & <@{marriage['user2_id']}>"
    
    count_str = f" ({index + 1}/{len(businesses)})" if len(businesses) > 1 else ""

    embed = embed_builder.get_embed(
        "family_biz_dashboard",
        biz_name=f"{info['name']}{count_str}",
        owners=owners,
        balance=format_money(biz['balance']),
        supplies=biz['supplies'],
        max_storage=max_storage,
        storage_progress=bar,
        upgrades="\n".join(levels),
        status=status,
        author_avatar=inter.author.display_avatar.url
    )
    
    view = FamilyBizDashboardView(bot, inter.author.id, marriage['id'], biz, index, len(businesses))
    
    if edit:
        await inter.response.edit_message(embed=embed, view=view)
    else:
        await inter.edit_original_response(embed=embed, view=view)

class ProposalView(disnake.ui.View):
    def __init__(self, bot, author, target):
        super().__init__(timeout=60)
        self.bot = bot
        self.author = author
        self.target = target
        self.value = None

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.target.id:
            await inter.edit_original_response(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url)
            )
            return False
        return True

    @disnake.ui.button(label="Согласиться", style=disnake.ButtonStyle.green, emoji="💍")
    async def accept(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.value = True
        
        await self.bot.db.update_money(self.author, -WEDDING_PRICE, 0)
        await self.bot.db.create_marriage(self.author.id, self.target.id)

        embed = embed_builder.get_embed(
            "success_marriage",
            user1=self.author.display_name,
            user2=self.target.display_name,
            author_avatar=self.author.display_avatar.url 
        )
        
        await inter.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

    @disnake.ui.button(label="Отказ", style=disnake.ButtonStyle.red)
    async def decline(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.value = False
        
        embed = disnake.Embed(
            description=f"💔 {self.target.mention} отклонил(а) предложение.",
            color=disnake.Color.red()
        )
        await inter.response.edit_message(content=None, embed=embed, view=None)
        self.stop()


class Marriage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fam_biz_loop.start()

    def cog_unload(self):
        self.fam_biz_loop.cancel()

    @commands.slash_command(name="семья", description="Семейные команды")
    @blacklist_check()
    @maintenance_check()
    @prison_check()
    async def family(self, inter):
        await inter.response.defer()
        pass

    @family.sub_command(name="свадьба", description=f"Предложить руку и сердце (Цена: {WEDDING_PRICE})")
    async def marry(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="партнер", description="Выберите свою половинку")
    ):
        await inter.response.defer()

        if member.id == inter.author.id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_self_action", author_avatar=inter.author.display_avatar.url)
            )
        
        if member.bot:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_bot_action", author_avatar=inter.author.display_avatar.url)
            )

        balance = await self.bot.db.get_balance(inter.author, "money")
        if balance < WEDDING_PRICE:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_no_money_details", balance=balance, needed=WEDDING_PRICE, author_avatar=inter.author.display_avatar.url)
            )

        m_author = await self.bot.db.get_marriage(inter.author.id)
        if m_author:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Вы уже состоите в браке!", author_avatar=inter.author.display_avatar.url)
            )
        
        m_target = await self.bot.db.get_marriage(member.id)
        if m_target:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text=f"{member.display_name} уже в браке!", author_avatar=inter.author.display_avatar.url)
            )

        embed = embed_builder.get_embed(
            "proposal",
            author_mention=inter.author.mention,
            target_mention=member.mention,
            price=WEDDING_PRICE,
            author_avatar=inter.author.display_avatar.url
        )
        
        view = ProposalView(self.bot, inter.author, member)
        await inter.response.send_message(content=member.mention, embed=embed, view=view)

    @family.sub_command(name="развод", description="Расторгнуть брак")
    async def divorce(self, inter):
        await inter.response.defer()
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Вы не состоите в браке.", author_avatar=inter.author.display_avatar.url)
            )

        partner_id = marriage['user2_id'] if marriage['user1_id'] == inter.author.id else marriage['user1_id']
        balance = marriage['balance']
        
        share = balance // 2
        
        if share > 0:
            await self.bot.db.update_money(disnake.Object(id=inter.author.id), share, 0)
            await self.bot.db.update_money(disnake.Object(id=partner_id), share, 0)

        await self.bot.db.delete_marriage(marriage['id'])
        
        user1 = inter.author.display_name
        try:
            partner_user = await self.bot.fetch_user(partner_id)
            user2 = partner_user.display_name
        except:
            user2 = "Неизвестно"

        embed = embed_builder.get_embed(
            "success_divorce",
            user1=user1,
            user2=user2,
            share=share,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

    @family.sub_command(name="профиль", description="Посмотреть профиль семьи")
    async def profile(self, inter):
        await inter.response.defer()
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage:
            embed = embed_builder.get_embed("info_no_family", user_mention=inter.author.mention, author_avatar=inter.author.display_avatar.url)
            return await inter.edit_original_response(embed=embed)

        imps_raw = marriage.get('improvements', '')
        imps_list = imps_raw.split(',') if imps_raw else []
        imps_cfg = ECO_CFG.get("family", {}).get("improvements", {})
        imps_str = "\n".join([f"✅ {imps_cfg[i]['name']}" for i in imps_list if i in imps_cfg]) or "Нет улучшений"

        businesses = await self.bot.db.get_family_businesses(marriage['id'])
        biz_str = ""
        if businesses:
            for b in businesses:
                info = FAM_CFG['businesses'].get(b['type'])
                if info:
                    biz_str += f"🏢 **{info['name']}**\n💰 {format_money(b['balance'])} | 📦 {b['supplies']}\n"
        else:
            biz_str = "Нет бизнесов"

        embed = embed_builder.get_embed(
            "family_profile",
            user1_mention=f"<@{marriage['user1_id']}>",
            user2_mention=f"<@{marriage['user2_id']}>",
            balance=format_money(marriage['balance']),
            level=marriage['level'],
            xp=marriage['love_xp'] % 100,
            date=int(marriage['marriage_date']),
            author_avatar=inter.author.display_avatar.url
        )
        embed.add_field(name="🌟 Улучшения", value=imps_str, inline=False)
        embed.add_field(name="💼 Семейный бизнес", value=biz_str, inline=False)
        await inter.edit_original_response(embed=embed)

    @family.sub_command(name="улучшения", description="Магазин улучшений семьи")
    async def improvements(self, inter):
        await inter.response.defer()
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage: 
            return await inter.edit_original_response(embed=embed_builder.get_embed("error_generic", text="Вы не в браке.", author_avatar=inter.author.display_avatar.url))
        
        embed = embed_builder.get_embed(
            "family_improvements_list",
            level=marriage['level'],
            balance=format_money(marriage['balance']),
            author_avatar=inter.author.display_avatar.url
        )
        view = ImprovementsView(self.bot, inter.author.id, marriage)
        await inter.edit_original_response(embed=embed, view=view)

    @family.sub_command(name="пополнить", description="Пополнить семейный бюджет")
    async def deposit(
        self, 
        inter, 
        amount: int = commands.Param(name="сумма", description="Сумма пополнения", gt=0)
    ):
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Вы не в браке.", author_avatar=inter.author.display_avatar.url)
            )

        user_money = await self.bot.db.get_balance(inter.author, "money")
        if user_money < amount:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_no_money_details", balance=user_money, needed=amount, author_avatar=inter.author.display_avatar.url)
            )

        await self.bot.db.update_money(inter.author, -amount, 0)
        await self.bot.db.update_family_balance(marriage['id'], amount)

        embed = embed_builder.get_embed(
            "family_deposit",
            amount=amount,
            new_bank=marriage['balance'] + amount,
            new_money=user_money - amount,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        
        await inter.edit_original_response(embed=embed)

    @family.sub_command(name="снять", description="Снять деньги из семейного бюджета")
    async def withdraw(
        self, 
        inter, 
        amount: int = commands.Param(name="сумма", description="Сумма снятия", gt=0)
    ):
        await inter.response.defer()
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Вы не в браке.", author_avatar=inter.author.display_avatar.url)
            )

        if marriage['balance'] < amount:
             return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_no_money_details", balance=marriage['balance'], needed=amount, author_avatar=inter.author.display_avatar.url)
            )

        await self.bot.db.update_money(inter.author, amount, 0)
        await self.bot.db.update_family_balance(marriage['id'], -amount)

        user_money = await self.bot.db.get_balance(inter.author, "money")
        new_family_balance = marriage['balance'] - amount

        embed = embed_builder.get_embed(
            "family_withdraw",
            amount=amount,
            new_bank=new_family_balance,
            new_money=user_money,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        
        await inter.edit_original_response(embed=embed)

    @family.sub_command_group(name="бизнес", description="Управление семейным бизнесом")
    async def family_biz(self, inter):
        await inter.response.defer()
        pass

    @family_biz.sub_command(name="продать", description="Продать семейный бизнес")
    async def fb_sell(self, inter):
        await inter.response.defer()

        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage: 
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Вы не в браке.", author_avatar=inter.author.display_avatar.url)
            )

        businesses = await self.bot.db.get_family_businesses(marriage['id'])
        
        if not businesses:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="У семьи нет бизнесов для продажи.", author_avatar=inter.author.display_avatar.url)
            )

        sell_ratio = ECO_CFG.get("global", {}).get("sell_ratio", 0.5)

        if len(businesses) == 1:
            biz_data = businesses[0]
            info = FAM_CFG['businesses'].get(biz_data['type'])
            if not info: 
                return await inter.edit_original_response("Ошибка конфигурации бизнеса")
            
            sell_price = int(info['cost'] * sell_ratio)
            
            embed = embed_builder.get_embed(
                "family_biz_sell_confirm",
                biz_name=info['name'],
                amount=format_money(sell_price),
                author_avatar=inter.author.display_avatar.url
            )
            view = FamilyBizSellConfirmView(self.bot, inter.author.id, marriage['id'], biz_data, sell_price, info['name'])
            await inter.edit_original_response(embed=embed, view=view)
            return

        embed = embed_builder.get_embed(
            "family_biz_sell_select",
            author_avatar=inter.author.display_avatar.url
        )
        view = FamilyBizSellSelectView(self.bot, businesses, inter.author.id, marriage['id'])
        await inter.edit_original_response(embed=embed, view=view)

    @family_biz.sub_command(name="купить", description="Купить семейный бизнес")
    async def fb_buy(self, inter, biz_type: str = commands.Param(name="тип", description="Выберите бизнес", choices={"🍷 Винодельня": "family_winery", "🏨 Отель": "family_hotel"})):
        await inter.response.defer()
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage: 
            return await inter.edit_original_response(embed=embed_builder.get_embed("error_generic", text="Вы не в браке.", author_avatar=inter.author.display_avatar.url))

        imps = marriage.get('improvements', '').split(',')
        if "family_business" not in imps:
            return await inter.edit_original_response(embed=embed_builder.get_embed("error_no_family_improvement", imp_name="Семейный бизнес", author_avatar=inter.author.display_avatar.url))

        current_biz = await self.bot.db.get_family_businesses(marriage['id'])

        for b in current_biz:
            if b['type'] == biz_type:
                info = FAM_CFG['businesses'][biz_type]
                return await inter.edit_original_response(
                    embed=embed_builder.get_embed(
                        "error_family_biz_duplicate", 
                        biz_name=info['name'], 
                        author_avatar=inter.author.display_avatar.url
                    )
                )

        if len(current_biz) >= 2:
            return await inter.edit_original_response(embed=embed_builder.get_embed("error_generic", text="Максимум 2 семейных бизнеса!", author_avatar=inter.author.display_avatar.url))

        info = FAM_CFG['businesses'][biz_type]
        cost = info['cost']
        
        if "family_capital" in imps:
            discount = ECO_CFG['family']['improvements']['family_capital']['discount_percent'] / 100
            cost = int(cost * (1 - discount))

        if marriage['balance'] < cost:
            return await inter.edit_original_response(f"В семье недостаточно денег! Цена: {format_money(cost)}")

        await self.bot.db.update_family_balance(marriage['id'], -cost)
        await self.bot.db.create_family_business(marriage['id'], biz_type)
        
        embed = embed_builder.get_embed("family_biz_buy_success", biz_name=info['name'], price=format_money(cost), author_avatar=inter.author.display_avatar.url)
        await inter.edit_original_response(embed=embed)

    @family_biz.sub_command(name="инфо", description="Управление семейными бизнесами")
    async def fb_info(self, inter):
        await inter.response.defer()
        await render_family_biz_dashboard(self.bot, inter)

    @family.sub_command(name="любовь", description="Отправить любовь партнеру")
    @custom_cooldown("love")
    async def love(self, inter):
        await inter.response.defer()
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Вам некому дарить любовь :(", author_avatar=inter.author.display_avatar.url)
            )
        
        xp_amount = random.randint(15, 30)
        await self.bot.db.add_love_xp(marriage['id'], xp_amount)
        
        updated_marriage = await self.bot.db.get_marriage(inter.author.id)
        
        embed = embed_builder.get_embed(
            "success_love",
            user1_mention=f"<@{marriage['user1_id']}>",
            user2_mention=f"<@{marriage['user2_id']}>",
            level=updated_marriage['level'],
            author_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

    @tasks.loop(seconds=TICK_TIME)
    async def fam_biz_loop(self):
        async with self.bot.db.conn.execute("SELECT * FROM marriages_businesses") as cursor:
            businesses = await cursor.fetchall()
            
        for biz in businesses:
            biz = dict(biz)
            info = FAM_CFG['businesses'].get(biz['type'])
            if not info: continue
            
            auto_lvl = biz.get('automation_lvl', 0)
            consume = max(1, info['consume'] - auto_lvl)
            
            if biz['supplies'] >= consume:
                mark_lvl = biz.get('marketing_lvl', 0)
                mark_bonus = BIZ_CFG['upgrades']['marketing']['multiplier']
                multiplier = 1 + (mark_lvl * (mark_bonus - 1))
                income = int(info['income'] * multiplier)
                
                await self.bot.db.update_family_biz_stats(biz['id'], -consume, income)

    @fam_biz_loop.before_loop
    async def before_fam_loop(self):
        await self.bot.wait_until_ready()

        while not getattr(self.bot, "db", None):
            await asyncio.sleep(1)

def setup(bot):
    bot.add_cog(Marriage(bot))