import disnake
import asyncio

from config import SELL_RATIO, ECO_CFG
from disnake.ext import commands
from utils.embeds import EmbedBuilder, format_money
from utils.decorators import prison_check, maintenance_check, blacklist_check


embed_builder = EmbedBuilder()

class InviteView(disnake.ui.View):
    def __init__(self, bot, owner: disnake.Member, tenant: disnake.Member, rent: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.owner = owner
        self.tenant = tenant
        self.rent = rent
        self.value = None

    @disnake.ui.button(label="✅ Согласиться", style=disnake.ButtonStyle.green)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.tenant.id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url)
            )

        house = await self.bot.db.get_house(self.owner.id)
        if not house:
             return await inter.edit_original_response(
                 embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url)
             )
             
        await self.bot.db.add_tenant(self.tenant.id, self.owner.id, self.rent)
        self.value = True

        embed = embed_builder.get_embed(
            "house_new_tenant", 
            user_mention=self.tenant.mention,
            author_name=self.owner.display_name,
            author_avatar=self.owner.display_avatar.url
        )
        
        await inter.response.edit_message(content=None, embed=embed, view=None)
        
        self.stop()

    @disnake.ui.button(label="❌ Отказаться", style=disnake.ButtonStyle.red)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.tenant.id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url)
            )
            
        self.value = False
        
        embed = disnake.Embed(description=f"❌ {self.tenant.mention} отклонил приглашение в дом.", color=disnake.Color.red())
        await inter.response.edit_message(content=None, embed=embed, view=None)
        
        self.stop()

class RoomControlView(disnake.ui.View):
    def __init__(self, bot, channel, owner_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.channel = channel
        self.owner_id = owner_id
        self.is_locked = False

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.owner_id:
            await inter.edit_original_response(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url)
            )
            return False
        return True

    @disnake.ui.button(label="Название", style=disnake.ButtonStyle.blurple, emoji="✏️")
    async def rename(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_modal(
            title="Переименовать комнату",
            custom_id="rename_modal",
            components=[disnake.ui.TextInput(label="Новое название", custom_id="name")]
        )
        try:
            modal_inter = await self.bot.wait_for("modal_submit", check=lambda i: i.custom_id == "rename_modal" and i.author.id == inter.author.id, timeout=60)
            new_name = modal_inter.text_values["name"]
            await self.channel.edit(name=new_name)
            await modal_inter.response.send_message(
                embed=disnake.Embed(description=f"✅ Комната переименована в **{new_name}**", color=disnake.Color.green())
            )
        except asyncio.TimeoutError:
            pass

    @disnake.ui.button(label="Закрыть/Открыть", style=disnake.ButtonStyle.red, emoji="🔒")
    async def lock(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.is_locked = not self.is_locked
        overwrite = disnake.PermissionOverwrite(connect=not self.is_locked)
        await self.channel.set_permissions(inter.guild.default_role, overwrite=overwrite)
        
        status = "закрыта" if self.is_locked else "открыта"
        button.style = disnake.ButtonStyle.green if self.is_locked else disnake.ButtonStyle.red
        button.emoji = "🔓" if self.is_locked else "🔒"
        
        await inter.response.edit_message(view=self)
        await inter.followup.send(
            embed=disnake.Embed(description=f"🚪 Комната {status} для всех.", color=disnake.Color.green())
        )

    @disnake.ui.button(label="Кикнуть", style=disnake.ButtonStyle.gray, emoji="👢")
    async def kick_user(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        members = [m for m in self.channel.members if m.id != self.owner_id]
        if not members:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="👀 В комнате никого нет.", author_avatar=inter.author.display_avatar.url)
            )
        
        target = members[0]
        await target.move_to(None)
        await inter.edit_original_response(
            embed=disnake.Embed(description=f"👢 {target.mention} был выгнан.", color=disnake.Color.green())
        )

class SellHouseView(disnake.ui.View):
    def __init__(self, bot, author, sell_price, house_name):
        super().__init__(timeout=60)
        self.bot = bot
        self.author = author
        self.sell_price = sell_price
        self.house_name = house_name
        self.value = None

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.author.id:
            await inter.edit_original_response(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url)
            )
            return False
        return True

    @disnake.ui.button(label="Подтвердить продажу", style=disnake.ButtonStyle.danger, emoji="💸")
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.value = True

        await self.bot.db.execute("DELETE FROM houses WHERE user_id = ?", (self.author.id,))
        await self.bot.db.update_money(self.author, int(self.sell_price), 0)

        embed = embed_builder.get_embed(
            "estate_sell_success",
            house_name=self.house_name,
            amount=self.sell_price,
            author_name=self.author.display_name,
            author_avatar=self.author.display_avatar.url
        )

        await inter.response.edit_message(embed=embed, view=None)
        self.stop()

    @disnake.ui.button(label="Отмена", style=disnake.ButtonStyle.secondary)
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.value = False
        embed = disnake.Embed(description="❌ Продажа отменена.", color=disnake.Color.red())
        await inter.response.edit_message(content=None, embed=embed, view=None)
        self.stop()


class Estate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cfg = ECO_CFG
        self.estate_cfg = ECO_CFG.get("estate", {})
        self.channels_cfg = ECO_CFG.get("channels", {})
        self.temp_channels = []

    @commands.slash_command(name="недвижимость", description="Меню недвижимости")
    @blacklist_check()
    @maintenance_check()
    @prison_check()
    async def estate(self, inter):
        await inter.response.defer()
        pass

    async def house_autocomplete(self, inter, string: str):
        selected_type = inter.filled_options.get("тип")
        if not selected_type:
            return ["⬅️ Сначала выберите тип жилья!"]

        houses = self.estate_cfg.get("houses", {})  
        choices = []
        for key, info in houses.items():
            if info.get("group") == selected_type:
                if string.lower() in info['name'].lower():
                    choices.append(f"{info['name']} — {format_money(info['price'])}")
        return choices[:25]

    @estate.sub_command(name="подселить", description="Подселить игрока в дом")
    async def invite(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя"), 
        rent: int = commands.Param(default=0, name="цена", description="Цена за 24 часа")
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

        house = await self.bot.db.get_house(inter.author.id)
        if not house:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url)
            )

        house_conf = ECO_CFG.get("estate", {}).get("houses", {}).get(house['type'])
        current_tenants = await self.bot.db.get_house_tenants(inter.author.id)
        
        if len(current_tenants) >= house_conf['max_tenants']:
            embed = embed_builder.get_embed(
                "error_house_full", 
                house_type=house_conf['name'], 
                limit=house_conf['max_tenants'],
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            return await inter.edit_original_response(embed=embed)

        target_house, status = await self.bot.db.get_living_space(member.id)
        if target_house:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text=f"❌ {member.display_name} уже имеет жилье!", author_avatar=inter.author.display_avatar.url)
            )

        embed_sent = embed_builder.get_embed(
            "house_invite_sent", 
            user_mention=member.mention, 
            price=rent,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        
        await inter.edit_original_response(embed=embed_sent)

        embed_invite = embed_builder.get_embed(
            "house_invite_received", 
            author_mention=inter.author.mention, 
            price=rent if rent > 0 else "Бесплатно",
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        
        view = InviteView(self.bot, inter.author, member, rent)
        await inter.channel.send(content=member.mention, embed=embed_invite, view=view)

    @estate.sub_command(name="выселить", description="Выселить жильца")
    async def kick(self, inter, member: disnake.Member = commands.Param(name="пользователь", description="Выберите пользователя")):
        await inter.response.defer()
        house = await self.bot.db.get_house(inter.author.id)
        if not house:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url)
            )

        tenant_info = await self.bot.db.get_tenant_info(member.id)
        if not tenant_info or tenant_info['owner_id'] != inter.author.id:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Этот пользователь не живет у вас.", author_avatar=inter.author.display_avatar.url)
            )

        await self.bot.db.remove_tenant(member.id)
        await inter.edit_original_response(embed=disnake.Embed(description=f"✅ Вы выселили {member.mention} из дома.", color=disnake.Color.green()))

    @estate.sub_command(name="съехать", description="Съехать из дома")
    async def leave(self, inter):
        await inter.response.defer()
        tenant_info = await self.bot.db.get_tenant_info(inter.author.id)
        if not tenant_info:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Вы нигде не подселены.", author_avatar=inter.author.display_avatar.url)
            )

        owner = await self.bot.fetch_user(tenant_info['owner_id'])
        await self.bot.db.remove_tenant(inter.author.id)
        
        embed = embed_builder.get_embed(
            "house_leave", 
            owner_mention=owner.mention if owner else "Неизвестно",
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )

        await inter.edit_original_response(embed=embed)

    @estate.sub_command(name="жильцы", description="Список жильцов")
    async def tenants_list(self, inter):
        await inter.response.defer()
        house = await self.bot.db.get_house(inter.author.id)
        if not house:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url)
            )

        tenants = await self.bot.db.get_house_tenants(inter.author.id)
        if not tenants:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="📂 У вас никто не живет.", author_avatar=inter.author.display_avatar.url)
            )

        desc = ""
        for t in tenants:
            desc += f"<@{t['user_id']}> | Рента: {t['rent_price']}$\n"

        embed = embed_builder.get_embed(
            "house_tenants_list", 
            description=desc,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

    @estate.sub_command(name="инфо", description="Показать информацию о доме")
    async def info(
        self, 
        inter, 
    ):
        await inter.response.defer()
        target = inter.author
        
        house = await self.bot.db.get_house(target.id)
        is_owner = True
        tenant_info = None

        if not house:
            tenant_info = await self.bot.db.get_tenant_info(target.id)
            if tenant_info:
                house = await self.bot.db.get_house(tenant_info['owner_id'])
                is_owner = False
                if not house:
                     return await inter.edit_original_response(
                         embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url)
                     )
            else:
                return await inter.edit_original_response(
                    embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url)
                )

        house_type = house['type']
        houses_cfg = self.estate_cfg.get("houses", {})
        conf = houses_cfg.get(house_type)
        
        if not conf:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Конфигурация дома не найдена.", author_avatar=inter.author.display_avatar.url)
            )

        owner_id = house['user_id']
        tenants = await self.bot.db.get_house_tenants(owner_id)

        if conf.get("group") == "mansion":
            thumb = "https://cdn-icons-png.flaticon.com/512/2558/2558943.png"
        elif conf.get("group") == "flat":
            thumb = "https://cdn-icons-png.flaticon.com/512/2558/2558988.png"
        else:
            thumb = "https://cdn-icons-png.flaticon.com/512/619/619153.png"

        common_data = {
            "house_name": conf['name'],
            "bought_at": f"<t:{house['bought_at']}:D>",
            "tenants_count": len(tenants),
            "max_tenants": conf['max_tenants'],
            "slots": conf['slots'],
            "bitrate": conf['bitrate'] // 1000,
            "thumbnail_url": thumb,
            "author_name": inter.author.display_name,
            "author_avatar": inter.author.display_avatar.url
        }

        if is_owner:
            sell_price = int(conf['price'] * SELL_RATIO)
            embed = embed_builder.get_embed(
                "house_info_owner",
                **common_data,
                price=format_money(conf['price']),
                sell_price=format_money(sell_price)
            )
        else:
            owner_user = await self.bot.get_or_fetch_user(owner_id)
            owner_name = owner_user.display_name if owner_user else "Неизвестно"
            rent = tenant_info['rent_price'] if tenant_info else 0
            
            embed = embed_builder.get_embed(
                "house_info_tenant",
                **common_data,
                owner_name=owner_name,
                rent_price=format_money(rent)
            )

        await inter.edit_original_response(embed=embed)

    @estate.sub_command(name="купить", description="Купить новый дом")
    async def buy(
        self, 
        inter, 
        house_type: str = commands.Param(
            name="тип", 
            description="Выберите категорию жилья",
            choices={
                "🏚️ Трейлеры (Эконом)": "trailer",
                "🏢 Квартиры (Средний)": "flat",
                "🏰 Особняки (Элитный)": "mansion"
            }
        ),
        house_name: str = commands.Param(
            name="дом", 
            description="Выберите конкретный объект",
            autocomplete=house_autocomplete
        )
    ):
        await inter.response.defer()
        if house_name == "⬅️ Сначала выберите тип жилья!":
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Вы не выбрали дом.", author_avatar=inter.author.display_avatar.url)
            )

        houses = self.estate_cfg.get("houses", {})
        selected_key = None
        
        for key, info in houses.items():
            if house_name.startswith(info['name']):
                if info.get("group") == house_type:
                    selected_key = key
                    break
        
        if not selected_key:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="Дом не найден или не соответствует выбранному типу.", author_avatar=inter.author.display_avatar.url)
            )

        conf = houses[selected_key]
        price = conf["price"]

        marriage = await self.bot.db.get_marriage(inter.author.id)
        if marriage and "family_capital" in (marriage.get('improvements') or ""):
             discount_pct = ECO_CFG.get('family', {}).get('improvements', {}).get('family_capital', {}).get('discount_percent', 0)
             price = int(price * (1 - (discount_pct / 100)))

        user_db = await self.bot.db.get_user(inter.author)
        if user_db["money"] < price:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_no_money_details", balance=user_db["money"], needed=price, author_avatar=inter.author.display_avatar.url)
            )
            
        current_house = await self.bot.db.get_house(inter.author.id)
        if current_house:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text="У вас уже есть жильё! Сначала продайте его.", author_avatar=inter.author.display_avatar.url)
            )

        await self.bot.db.update_money(inter.author, -price, 0)
        await self.bot.db.set_house(inter.author.id, selected_key)

        embed = embed_builder.get_embed(
            "estate_buy_success",
            house_name=conf['name'],
            price=price,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.edit_original_response(embed=embed)

    @estate.sub_command(name="продать", description="Продать текущий дом за часть стоимости")
    async def sell(self, inter):
        await inter.response.defer()
        house = await self.bot.db.get_house(inter.author.id)
        if not house:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url)
            )
        
        house_type_key = house["type"]
        houses = self.estate_cfg.get("houses", {})
        house_info = houses.get(house_type_key)
        
        if not house_info:
            original_price = 0
            house_name = "Неизвестная недвижимость"
        else:
            original_price = house_info["price"]
            house_name = house_info["name"]

        sell_price = int(original_price * SELL_RATIO)

        embed = embed_builder.get_embed(
            "estate_sell_confirm",
            house_name=house_name,
            original_price=original_price,
            ratio=int(SELL_RATIO*100),
            sell_price=sell_price,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )

        view = SellHouseView(self.bot, inter.author, sell_price, house_name)
        await inter.edit_original_response(embed=embed, view=view)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if after.channel and (not before.channel or before.channel.id != after.channel.id):
            gen_id = ECO_CFG.get("channels", {}).get("estate_generator_id")
            
            if after.channel.id == gen_id:
                house_data, status = await self.bot.db.get_living_space(member.id)
                
                if not house_data:
                    return await member.move_to(None)

                h_type = house_data['type']
                estate_cfg = ECO_CFG.get("estate", {})
                conf = estate_cfg.get("houses", {}).get(h_type)
                
                if not conf:
                    return await member.move_to(None)

                h_name = f"{conf['name']} {member.display_name}"
                cat_id = ECO_CFG.get("channels", {}).get("estate_category_id")
                category = member.guild.get_channel(cat_id)

                overwrites = {
                    member.guild.default_role: disnake.PermissionOverwrite(connect=False),
                    member: disnake.PermissionOverwrite(manage_channels=True, move_members=True, connect=True)
                }
                
                voice = await member.guild.create_voice_channel(
                    name=h_name,
                    category=category,
                    user_limit=conf["slots"],
                    overwrites=overwrites
                )
                
                self.temp_channels.append(voice.id)
                await member.move_to(voice)
                
                view = RoomControlView(self.bot, voice, member.id)
                
                embed = embed_builder.get_embed("estate_room_welcome", user_mention=member.mention)
                await voice.send(embed=embed, view=view)

        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                await before.channel.delete()
                self.temp_channels.remove(before.channel.id)

def setup(bot):
    bot.add_cog(Estate(bot))