import disnake
import asyncio
import random
import time

from config import WEDDING_PRICE
from disnake.ext import commands
from utils.embeds import EmbedBuilder
from utils.decorators import custom_cooldown

embed_builder = EmbedBuilder()

class ProposalView(disnake.ui.View):
    def __init__(self, bot, author, target):
        super().__init__(timeout=60)
        self.bot = bot
        self.author = author
        self.target = target
        self.value = None

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.target.id:
            await inter.send(
                embed=embed_builder.get_embed("error_interaction_owner", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
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

    @commands.slash_command(name="семья", description="Семейные команды")
    async def family(self, inter):
        pass

    @family.sub_command(name="свадьба", description=f"Предложить руку и сердце (Цена: {WEDDING_PRICE})")
    async def marry(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="партнер", description="Выберите свою половинку")
    ):
        if member.id == inter.author.id:
            return await inter.send(
                embed=embed_builder.get_embed("error_self_action", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        
        if member.bot:
            return await inter.send(
                embed=embed_builder.get_embed("error_bot_action", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        balance = await self.bot.db.get_balance(inter.author, "money")
        if balance < WEDDING_PRICE:
            return await inter.send(
                embed=embed_builder.get_embed("error_no_money_details", balance=balance, needed=WEDDING_PRICE, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        m_author = await self.bot.db.get_marriage(inter.author.id)
        if m_author:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Вы уже состоите в браке!", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        
        m_target = await self.bot.db.get_marriage(member.id)
        if m_target:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text=f"{member.display_name} уже в браке!", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
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
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Вы не состоите в браке.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
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
        await inter.send(embed=embed)

    @family.sub_command(name="профиль", description="Посмотреть профиль семьи")
    async def profile(self, inter):
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage:
            embed = embed_builder.get_embed(
                "info_no_family",
                user_mention=inter.author.mention,
                author_avatar=inter.author.display_avatar.url
            )
            return await inter.send(embed=embed)

        embed = embed_builder.get_embed(
            "family_profile",
            user1_mention=f"<@{marriage['user1_id']}>",
            user2_mention=f"<@{marriage['user2_id']}>",
            balance=marriage['balance'],
            level=marriage['level'],
            xp=marriage['love_xp'] % 100,
            date=int(marriage['marriage_date']),
            author_avatar=inter.author.display_avatar.url
        )
        await inter.send(embed=embed)

    @family.sub_command(name="пополнить", description="Пополнить семейный бюджет")
    async def deposit(
        self, 
        inter, 
        amount: int = commands.Param(name="сумма", description="Сумма пополнения", gt=0)
    ):
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Вы не в браке.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        user_money = await self.bot.db.get_balance(inter.author, "money")
        if user_money < amount:
            return await inter.send(
                embed=embed_builder.get_embed("error_no_money_details", balance=user_money, needed=amount, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
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
        
        await inter.send(embed=embed)

    @family.sub_command(name="снять", description="Снять деньги из семейного бюджета")
    async def withdraw(
        self, 
        inter, 
        amount: int = commands.Param(name="сумма", description="Сумма снятия", gt=0)
    ):
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Вы не в браке.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        if marriage['balance'] < amount:
             return await inter.send(
                embed=embed_builder.get_embed("error_no_money_details", balance=marriage['balance'], needed=amount, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
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
        
        await inter.send(embed=embed)

    @family.sub_command(name="любовь", description="Отправить любовь партнеру")
    @custom_cooldown("love")
    async def love(self, inter):
        marriage = await self.bot.db.get_marriage(inter.author.id)
        if not marriage:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Вам некому дарить любовь :(", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
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
        await inter.send(embed=embed)

def setup(bot):
    bot.add_cog(Marriage(bot))