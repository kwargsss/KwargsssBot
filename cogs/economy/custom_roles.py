import disnake

from disnake.ext import commands
from config import *
from utils.embeds import EmbedBuilder
from utils.decorators import maintenance_check, prison_check


embed_builder = EmbedBuilder()

class RoleApprovalView(disnake.ui.View):
    def __init__(self, bot, author_id, role_name, role_color_hex, price):
        super().__init__(timeout=None)
        self.bot = bot
        self.author_id = author_id
        self.role_name = role_name
        self.role_color_hex = role_color_hex
        self.price = price

    @disnake.ui.button(label="Подтвердить", style=disnake.ButtonStyle.green, custom_id="approve_role_buy")
    async def approve(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        guild = inter.guild
        member = guild.get_member(self.author_id)
        
        if not member:
            await inter.send(
                embed=embed_builder.get_embed("error_not_found", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
            for child in self.children:
                child.disabled = True
            await inter.message.edit(view=self)
            self.stop()
            return

        balance = await self.bot.db.get_balance(member, "money")
        if balance < self.price:
            await inter.send(
                embed=embed_builder.get_embed("error_no_money_details", balance=balance, needed=self.price, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
            return

        await inter.response.defer()

        try:
            color_int = int(self.role_color_hex.replace("#", ""), 16)
            color = disnake.Color(color_int)
        except:
            color = disnake.Color.default()

        try:
            role = await guild.create_role(name=self.role_name, color=color, reason=f"Покупка роли пользователем {member.display_name}")
            await member.add_roles(role)
            
            await self.bot.db.update_money(member, -self.price, 0)

            news_channel = guild.get_channel(ECONOMY_NEWS_CHANNEL_ID)
            if news_channel:
                embed_news = embed_builder.get_embed(
                    name="role_buy_success",
                    user_mention=member.mention,
                    role_name=self.role_name,
                    user_avatar=member.display_avatar.url,
                    author_name=inter.author.display_name,
                    author_avatar=inter.author.display_avatar.url
                )
                await news_channel.send(content=member.mention, embed=embed_news)

            embed = inter.message.embeds[0]
            embed.color = disnake.Color.green()
            embed.add_field(
                name="Итог", 
                value=f"✅ **Одобрено администратором:** {inter.author.mention}", 
                inline=False
            )
            
            await inter.message.edit(embed=embed, view=None)
            
            await inter.send(
                embed=disnake.Embed(description="✅ Роль создана и выдана.", color=disnake.Color.green()),
                ephemeral=True
            )

        except disnake.Forbidden:
            await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Ошибка: У бота нет прав на создание/выдачу ролей.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
        except Exception as e:
            await inter.send(
                embed=embed_builder.get_embed("error_generic", text=f"Произошла ошибка: {e}", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

    @disnake.ui.button(label="Отклонить", style=disnake.ButtonStyle.red, custom_id="deny_role_buy")
    async def deny(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        
        guild = inter.guild
        member = guild.get_member(self.author_id)

        news_channel = guild.get_channel(ECONOMY_NEWS_CHANNEL_ID)
        if news_channel:
            embed_news = embed_builder.get_embed(
                name="role_buy_denied",
                user_mention=member.mention if member else f"<@{self.author_id}>",
                role_name=self.role_name,
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            await news_channel.send(embed=embed_news)

        embed = inter.message.embeds[0]
        embed.color = disnake.Color.red()
        embed.add_field(
            name="Итог", 
            value=f"❌ **Отклонено администратором:** {inter.author.mention}", 
            inline=False
        )
        
        await inter.message.edit(embed=embed, view=None)

        await inter.send(
            embed=disnake.Embed(description="⛔ Заявка отклонена.", color=disnake.Color.red()),
            ephemeral=True
        )


class CustomRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_price = ECO_CFG["global"].get("custom_role_price", 1000000)

    @commands.slash_command(name="роль", description="Управление личными ролями")
    @prison_check()
    @maintenance_check()
    async def role(self, inter):
        pass

    @role.sub_command(name="купить", description="Купить личную роль")
    @prison_check()
    @maintenance_check()
    async def buy(
        self, 
        inter, 
        name: str = commands.Param(name="название", description="Название роли"), 
        color: str = commands.Param(name="цвет", description="HEX цвет (например: #ff0000)")
    ):
        if not color.startswith("#"):
            color = "#" + color
        
        try:
            int(color.replace("#", ""), 16)
        except ValueError:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Неверный формат цвета. Используйте HEX (например: #ff0000)", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        balance = await self.bot.db.get_balance(inter.author, "money")
        if balance < self.role_price:
            return await inter.send(
                embed=embed_builder.get_embed("error_no_money_details", balance=balance, needed=self.role_price, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        log_channel = self.bot.get_channel(LOG_ECONOMY)
        if not log_channel:
            return await inter.send(
                embed=embed_builder.get_embed("error_generic", text="Ошибка: Канал логов экономики не настроен.", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )

        embed_log = embed_builder.get_embed(
            name="role_buy_request",
            user_mention=inter.author.mention,
            user_id=inter.author.id,
            role_name=name,
            role_color=color,
            price=self.role_price,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )

        view = RoleApprovalView(self.bot, inter.author.id, name, color, self.role_price)
        await log_channel.send(embed=embed_log, view=view)

        await inter.send(
            embed=disnake.Embed(description="✅ Ваша заявка отправлена администрации на проверку.", color=disnake.Color.green()),
            ephemeral=True
        )

def setup(bot):
    bot.add_cog(CustomRoles(bot))