import disnake
import config

from disnake.ext import commands
from utils.embeds import EmbedBuilder
from utils.decorators import prison_check, maintenance_check, blacklist_check
from utils.commission import commission_manager


embed_builder = EmbedBuilder()

class PaySystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="передать", description="Перевести деньги другому пользователю")
    @blacklist_check()
    @maintenance_check()
    @prison_check()
    async def pay(
        self, 
        inter, 
        member: disnake.Member = commands.Param(name="кому", description="Получатель перевода"),
        source: str = commands.Param(name="откуда", description="Счет списания", choices={"Наличные": "money", "Банк": "bank"}),
        target: str = commands.Param(name="куда", description="Счет зачисления", choices={"Наличные": "money", "Банк": "bank"}),
        amount: int = commands.Param(name="сумма", description="Сумма перевода")
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

        if amount <= 0:
            return await inter.edit_original_response(
                embed=embed_builder.get_embed("error_zero_amount", author_avatar=inter.author.display_avatar.url)
            )

        sender_data = await self.bot.db.get_user(inter.author)
        if not sender_data:
            await self.bot.db.add_user(inter.author)
            sender_data = await self.bot.db.get_user(inter.author)

        target_data = await self.bot.db.get_user(member)
        if not target_data:
            await self.bot.db.add_user(member)

        current_balance = sender_data[source] 
        
        if current_balance < amount:
            account_name = "Наличных" if source == "money" else "В Банке"
            return await inter.edit_original_response(
                embed=embed_builder.get_embed(
                    "error_no_money_details", 
                    balance=f"{current_balance} ({account_name})", 
                    needed=amount,
                    author_avatar=inter.author.display_avatar.url
                )
            )

        fee, net_amount = commission_manager.calculate(amount, "pay")

        if source == "money":
            await self.bot.db.update_money(inter.author, -amount, 0)
        else:
            await self.bot.db.update_money(inter.author, 0, -amount)

        if target == "money":
            await self.bot.db.update_money(member, net_amount, 0)
        else:
            await self.bot.db.update_money(member, 0, net_amount)
            
        await self.bot.db.add_transaction(
            sender_id=inter.author.id,
            target_id=member.id,
            amount=amount,
            source=source,
            target=target
        )

        type_map = {"money": "💵 Наличные", "bank": "💳 Банк"}

        embed_success = embed_builder.get_embed(
            name="success_pay",
            sender_mention=inter.author.mention,
            sender_avatar=inter.author.display_avatar.url,
            target_mention=member.mention,
            amount=amount,
            received=net_amount, 
            fee=fee,             
            source_type=type_map[source],
            target_type=type_map[target],
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )

        await inter.edit_original_response(embed=embed_success)

        log_channel = inter.guild.get_channel(config.LOG_ECONOMY)
        if log_channel:
            embed_log = embed_builder.get_embed(
                name="log_pay",
                sender_mention=inter.author.mention,
                target_mention=member.mention,
                amount=amount,
                fee=fee,
                source_type=type_map[source],
                target_type=type_map[target],
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            await log_channel.send(embed=embed_log)

def setup(bot):
    bot.add_cog(PaySystem(bot))