import disnake
import json
import os

from disnake.ext import commands
from utils.embeds import EmbedBuilder, format_money

embed_builder = EmbedBuilder()


def get_economy_config():
    path = "data/economy_config.json" 
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

async def generate_whois_embed(bot, member: disnake.Member, author: disnake.Member):
    db_user = await bot.db.get_user(member)
    if not db_user:
        await bot.db.add_user(member)
        db_user = await bot.db.get_user(member)

    stats = await bot.db.get_user_extended_stats(member.id)
    active_warns = await bot.db.get_warns_count(member.id)

    roles = [role.mention for role in member.roles if role.name != "@everyone"]
    roles.reverse()

    if len(roles) > 10:
        roles_str = ", ".join(roles[:10]) + f" ...и еще {len(roles) - 10}"
    elif not roles:
        roles_str = "Нет ролей"
    else:
        roles_str = ", ".join(roles)

    return embed_builder.get_embed(
        name="admin_whois",
        user_display_name=member.display_name,
        user_id=member.id,
        user_avatar=member.display_avatar.url,
        created_at=int(member.created_at.timestamp()),
        joined_at=int(member.joined_at.timestamp()) if member.joined_at else 0,
        bio=db_user['bio'],
        money=db_user['money'],
        bank=db_user['bank'],
        rate=db_user['rate'],
        tickets_total=stats['tickets_total'],
        tickets_open=stats['tickets_open'],
        warns_total=stats['warns_total'],
        warns_active=active_warns,
        mutes_total=stats['mutes_total'],
        bans_total=stats['bans_total'],
        roles=roles_str,
        roles_count=len(roles),
        author_name=author.display_name,
        author_avatar=author.display_avatar.url
    )

async def generate_history_embed(bot, member: disnake.Member, author: disnake.Member):
    history = await bot.db.get_user_transactions(member.id)

    if not history:
        history_text = "*Транзакций не найдено...*"
    else:
        lines = []
        for t in history:
            is_sender = (t['sender_id'] == member.id)
            other_id = t['target_id'] if is_sender else t['sender_id']
            amount = t['amount']
            time_str = f"<t:{int(t['created_at'])}:d>" 

            icon_src = "💵" if t['source_type'] == "money" else "💳"
            icon_trg = "💵" if t['target_type'] == "money" else "💳"

            if is_sender:
                line = f"🔴 **-{amount}** | Вы {icon_src} ➔ {icon_trg} <@{other_id}> | {time_str}"
            else:
                line = f"🟢 **+{amount}** | <@{other_id}> {icon_src} ➔ {icon_trg} Вы | {time_str}"
            lines.append(line)
        
        history_text = "\n".join(lines)

    return embed_builder.get_embed(
        name="transaction_history",
        user_mention=member.mention,
        history_text=history_text,
        author_name=author.display_name,
        author_avatar=author.display_avatar.url       
    )

async def generate_family_embed(bot, member: disnake.Member, author: disnake.Member):
    marriage = await bot.db.get_marriage(member.id)

    if not marriage:
        return embed_builder.get_embed(
            name="info_no_family",
            user_mention=member.mention,
            author_name=author.display_name,
            author_avatar=author.display_avatar.url
        )
    else:
        return embed_builder.get_embed(
            name="family_profile",
            user1_mention=f"<@{marriage['user1_id']}>",
            user2_mention=f"<@{marriage['user2_id']}>",
            balance=marriage['balance'],
            level=marriage['level'],
            xp=marriage['love_xp'] % 100,
            date=int(marriage['marriage_date']),
            author_name=author.display_name,
            author_avatar=author.display_avatar.url
        )

async def generate_house_embed(bot, member: disnake.Member, author: disnake.Member):
    house_raw = await bot.db.get_house(member.id)
    house = dict(house_raw) if house_raw else None
    
    is_owner = True
    tenant_info = None

    if not house:
        tenant_info = await bot.db.get_tenant_info(member.id)
        if tenant_info:
            is_owner = False
            owner_house_raw = await bot.db.get_house(tenant_info['owner_id'])
            if owner_house_raw:
                house = dict(owner_house_raw)
            else:
                tenant_info = None

    if not house:
        return disnake.Embed(
            description="❌ У пользователя нет недвижимости (не владеет и не снимает).", 
            color=disnake.Color.red()
        )

    full_config = get_economy_config()
    estate_config = full_config.get("estate", {})
    houses_config = estate_config.get("houses", {})
    
    house_type_key = house['type']
    house_info = houses_config.get(house_type_key, {})

    group_map = {
        "trailer": "🏚️ Трейлер (Эконом)",
        "flat": "🏢 Квартира (Средний)",
        "mansion": "🏰 Особняк (Элитный)"
    }

    house_name = house.get("name") or house_info.get("name", "Неизвестный дом")
    group_raw = house_info.get("group", "unknown")
    group_name = group_map.get(group_raw, group_raw.capitalize())
    
    if is_owner:
        current_tenants = await bot.db.get_house_tenants(member.id)
        current_count = len(current_tenants)
        max_tenants = house_info.get("max_tenants", 0)

        slots_tenant_str = f"{current_count}/{max_tenants}"
        
        price = format_money(house_info.get("price", 0))
        slots = house_info.get("slots", 0)
        bitrate = int(house_info.get("bitrate", 64000) / 1000)
        can_rename = "✅ Да" if house_info.get("can_rename", False) else "❌ Нет"
        bought_at = house['bought_at']

        return embed_builder.get_embed(
            name="user_house",
            display_name=member.display_name,
            avatar_url=member.display_avatar.url,
            author_name=author.display_name,
            author_avatar=author.display_avatar.url,
            house_name=house_name,
            group_name=group_name,
            price=price,
            slots=slots,
            slots_tenant=slots_tenant_str,
            bitrate=bitrate,
            can_rename=can_rename,
            bought_at=bought_at
        )
    
    else:
        owner_id = tenant_info['owner_id']
        rent_price = format_money(tenant_info['rent_price']) 
        joined_at = tenant_info['joined_at']

        return embed_builder.get_embed(
            name="user_house_tenant",
            display_name=member.display_name,
            avatar_url=member.display_avatar.url,
            author_name=author.display_name,
            author_avatar=author.display_avatar.url,
            house_name=house_name,
            group_name=group_name,
            owner_mention=f"<@{owner_id}>",
            rent_price=rent_price,
            joined_at=joined_at
        )
    
async def generate_business_embed(bot, member: disnake.Member, author: disnake.Member):
    businesses = await bot.db.get_user_businesses(member.id)

    if not businesses:
        return disnake.Embed(
            description="❌ У пользователя нет активных бизнесов.", 
            color=disnake.Color.red()
        )

    embed = embed_builder.get_embed(
        name="user_businesses",
        display_name=member.display_name,
        avatar_url=member.display_avatar.url,
        count=len(businesses),
        author_name=author.display_name,
        author_avatar=author.display_avatar.url
    )

    raw_config = embed_builder.data.get("user_businesses", {})
    field_layout = raw_config.get("field_layout", "**Баланс:** `{balance}`\n**Сырьё:** `{supplies}`")

    economy_cfg = get_economy_config()

    full_business_config = economy_cfg.get("business", {})
    biz_types_config = full_business_config.get("types", {})
    
    fallback_names = {
        "shop": "Магазин", "factory": "Завод", "mine": "Шахта", "farm": "Ферма"
    }

    for biz in businesses:
        b_type = biz['type']
        conf = biz_types_config.get(b_type, {})
        
        if "name" in conf:
            display_name = conf["name"]
        else:
            rus_name = fallback_names.get(b_type, b_type.capitalize())
            icon = "🏢"
            display_name = f"{icon} {rus_name}"

        upgrades_list = [
            f"📢 Маркетинг: `{biz.get('marketing_lvl', 0)}`",
            f"🚚 Логистика: `{biz.get('logistics_lvl', 0)}`",
            f"🛡️ Охрана: `{biz.get('security_lvl', 0)}`",
            f"🤖 Автоматизация: `{biz.get('automation_lvl', 0)}`",
            f"🏝️ Оффшоры: `{biz.get('offshore_lvl', 0)}`"
        ]
        
        upgrades_str = "\n".join([f"> {u}" for u in upgrades_list])
        
        total_lvl = 1 + biz.get('marketing_lvl', 0) + biz.get('logistics_lvl', 0) + \
                    biz.get('security_lvl', 0) + biz.get('automation_lvl', 0) + \
                    biz.get('offshore_lvl', 0)

        value_text = field_layout.format(
            balance=format_money(biz['balance']),
            supplies=biz['supplies'],
            earnings=format_money(biz['total_earnings']),
            total_lvl=total_lvl,
            upgrades=upgrades_str
        )

        embed.add_field(
            name=f"{display_name} (ID: {biz['id']})",
            value=value_text,
            inline=False
        )

    return embed

async def generate_finance_embed(bot, member: disnake.Member, author: disnake.Member):
    deposit = await bot.db.get_active_deposit(member.id)
    loan = await bot.db.get_active_loan(member.id)
    rating = await bot.db.get_credit_rating(member.id)

    if deposit:
        end_date = f"<t:{int(deposit['end_time'])}:D>"
        profit = format_money(deposit['profit_amount'])
        amount = format_money(deposit['amount'])
        dep_str = (
            f"> **Сумма:** {amount}\n"
            f"> **Прибыль:** {profit}\n"
            f"> **Окончание:** {end_date}"
        )
    else:
        dep_str = "```Нет активных вкладов```"

    if loan:
        due_date = f"<t:{int(loan['due_date'])}:D>"
        paid = format_money(loan['amount_paid'])
        total = format_money(loan['amount_total'])
        loan_str = (
            f"> **Долг:** {total}\n"
            f"> **Выплачено:** {paid}\n"
            f"> **Срок до:** {due_date}"
        )
    else:
        loan_str = "```Нет активных кредитов```"

    return embed_builder.get_embed(
        "whois_finance",
        rating=rating,
        deposit_info=dep_str,
        loan_info=loan_str,
        author_name=author.display_name,
        author_avatar=author.display_avatar.url
    )

class WhoisView(disnake.ui.View):
    def __init__(self, bot, target, author):
        super().__init__(timeout=300)
        self.bot = bot
        self.target = target
        self.author = author

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.author.id:
            await inter.edit_original_response(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
            return False
        return True

    @disnake.ui.button(label="Транзакции", style=disnake.ButtonStyle.primary, emoji="💸", row=0)
    async def show_history(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        embed = await generate_history_embed(self.bot, self.target, self.author)
        self._reset_buttons()
        button.disabled = True
        await inter.edit_original_message(embed=embed, view=self)

    @disnake.ui.button(label="Семья", style=disnake.ButtonStyle.success, emoji="💍", row=0)
    async def show_family(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        embed = await generate_family_embed(self.bot, self.target, self.author)
        self._reset_buttons()
        button.disabled = True
        await inter.edit_original_message(embed=embed, view=self)

    @disnake.ui.button(label="Бизнесы", style=disnake.ButtonStyle.secondary, emoji="🏢", row=0)
    async def show_businesses(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        embed = await generate_business_embed(self.bot, self.target, self.author)
        self._reset_buttons()
        button.disabled = True
        await inter.edit_original_message(embed=embed, view=self)

    @disnake.ui.button(label="Дом", style=disnake.ButtonStyle.primary, emoji="🏠", row=0)
    async def show_house(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        embed = await generate_house_embed(self.bot, self.target, self.author)
        self._reset_buttons()
        button.disabled = True
        await inter.edit_original_message(embed=embed, view=self)

    @disnake.ui.button(label="Финансы", style=disnake.ButtonStyle.success, emoji="💰", custom_id="finance_info")
    async def finance_info(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        embed = await generate_finance_embed(self.bot, self.target, self.author)
        self._reset_buttons()
        button.disabled = True
        await inter.edit_original_message(embed=embed, view=self)

    @disnake.ui.button(label="Назад", style=disnake.ButtonStyle.danger, emoji="🔙", disabled=True, row=1)
    async def go_back(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        embed = await generate_whois_embed(self.bot, self.target, self.author)
        self._reset_buttons()
        button.disabled = True 
        await inter.edit_original_message(embed=embed, view=self)

    def _reset_buttons(self):
        for child in self.children:
            child.disabled = False
            if child.label != "Назад":
                child.disabled = False
            else:
                child.disabled = False 

class Whois(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="аюзер", description="Полная информация о пользователе")
    async def whois(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя")
    ):
        await inter.response.defer()

        embed = await generate_whois_embed(self.bot, member, inter.author)
        view = WhoisView(self.bot, member, inter.author)
        
        await inter.edit_original_response(embed=embed, view=view)

def setup(bot):
    bot.add_cog(Whois(bot))