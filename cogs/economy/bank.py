from disnake.ext import commands
from utils.embeds import EmbedBuilder
from utils.decorators import prison_check
from utils.commission import commission_manager


embed_builder = EmbedBuilder()

class BankSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="банк", description="Снять или положить деньги")
    @prison_check()
    async def bank(self, inter):
        pass

    @bank.sub_command(name="положить", description="Положить деньги в банк")
    @prison_check()
    async def deposit(
        self, 
        inter, 
        amount: int = commands.Param(name="сумма", description="Сколько положить")
    ):
        if amount <= 0:
            return await inter.send(
                embed=embed_builder.get_embed("error_zero_amount", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        user_data = await self.bot.db.get_user(inter.author)
        if not user_data:
            await self.bot.db.add_user(inter.author)
            user_data = await self.bot.db.get_user(inter.author)

        cash = user_data['money']
        if cash < amount:
            return await inter.send(
                embed=embed_builder.get_embed("error_no_money_details", balance=cash, needed=amount, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        await self.bot.db.update_money(inter.author, -amount, amount)

        new_data = await self.bot.db.get_user(inter.author)
        
        embed = embed_builder.get_embed(
            name="success_deposit",
            amount=amount,
            new_bank=new_data['bank'],
            new_money=new_data['money'],
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url    
        )
        await inter.send(embed=embed)

    @bank.sub_command(name="снять", description="Снять деньги с банка")
    async def withdraw(
        self, 
        inter, 
        amount: int = commands.Param(name="сумма", description="Сколько снять")
    ):
        if amount <= 0:
            return await inter.send(
                embed=embed_builder.get_embed("error_zero_amount", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        user_data = await self.bot.db.get_user(inter.author)
        if not user_data:
            await self.bot.db.add_user(inter.author)
            user_data = await self.bot.db.get_user(inter.author)

        bank_balance = user_data['bank']
        if bank_balance < amount:
            return await inter.send(
                embed=embed_builder.get_embed("error_no_money_details", balance=bank_balance, needed=amount, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        fee, received = commission_manager.calculate(amount, "bank_withdraw")

        await self.bot.db.update_money(inter.author, received, -amount)

        new_data = await self.bot.db.get_user(inter.author)

        embed = embed_builder.get_embed(
            name="success_withdraw",
            amount=amount,
            fee=fee,
            received=received,
            new_bank=new_data['bank'],
            new_money=new_data['money'],
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url    
        )
        await inter.send(embed=embed)

def setup(bot):
    bot.add_cog(BankSystem(bot))