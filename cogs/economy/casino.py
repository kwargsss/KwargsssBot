import disnake
import random
import asyncio

from config import ECO_CFG
from disnake.ext import commands
from utils.embeds import EmbedBuilder, format_money
from utils.decorators import prison_check, maintenance_check, blacklist_check


embed_builder = EmbedBuilder()

class BlackjackView(disnake.ui.View):
    def __init__(self, bot, author, bet):
        super().__init__(timeout=60)
        self.bot = bot
        self.author = author
        self.bet = bet
        self.deck = self.generate_deck()
        self.player_hand = [self.draw(), self.draw()]
        self.dealer_hand = [self.draw(), self.draw()]
        self.ended = False

    def generate_deck(self):
        suits = ["♠️", "♥️", "♦️", "♣️"]
        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        deck = [(r, s) for s in suits for r in ranks] * 4 # 4 колоды
        random.shuffle(deck)
        return deck

    def draw(self):
        return self.deck.pop()

    def calculate_score(self, hand):
        score = 0
        aces = 0
        values = {"2":2, "3":3, "4":4, "5":5, "6":6, "7":7, "8":8, "9":9, "10":10, "J":10, "Q":10, "K":10, "A":11}
        
        for rank, suit in hand:
            score += values[rank]
            if rank == "A": aces += 1
            
        while score > 21 and aces:
            score -= 10
            aces -= 1
        return score

    def format_hand(self, hand, hide_dealer=False):
        if hide_dealer:
            return f"{hand[0][0]}{hand[0][1]} | 🎴 ?"
        return " | ".join([f"{r}{s}" for r, s in hand])

    async def end_game(self, inter, reason, win_multiplier=0):
        self.ended = True

        for child in self.children:
            child.disabled = True
        
        p_score = self.calculate_score(self.player_hand)
        d_score = self.calculate_score(self.dealer_hand)

        prize = int(self.bet * win_multiplier)

        if win_multiplier > 1:
            await self.bot.db.update_money(self.author, prize, 0)
            embed_name = "casino_win"
            color = disnake.Color.green()
            title = "🎉 Победа в Блэкджек!"
        elif win_multiplier == 1: 
            await self.bot.db.update_money(self.author, self.bet, 0)
            embed_name = "casino_win"
            color = disnake.Color.yellow()
            title = "🤝 Ничья"
            prize = self.bet
        else: 
            embed_name = "casino_lose"
            color = disnake.Color.red()
            title = "😢 Проигрыш"
            prize = 0

        embed = embed_builder.get_embed(
            "casino_blackjack_game",
            player_hand=self.format_hand(self.player_hand),
            player_score=p_score,
            dealer_hand=self.format_hand(self.dealer_hand),
            dealer_score=d_score,
            bet=format_money(self.bet),
            author_avatar=self.author.display_avatar.url
        )
        
        embed.title = title
        embed.color = color
        embed.description += f"\n\n**Итог:** {reason}"
        if prize > 0:
             embed.description += f"\n💰 Возврат: **{format_money(prize)}**"

        if inter.response.is_done():
            await inter.edit_original_message(embed=embed, view=None)
        else:
            await inter.response.edit_message(embed=embed, view=None)
        
        self.stop()

    @disnake.ui.button(label="Взять (Hit)", style=disnake.ButtonStyle.primary)
    async def hit(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.author.id: return
        
        self.player_hand.append(self.draw())
        score = self.calculate_score(self.player_hand)
        
        if score > 21:
            await self.end_game(inter, "Перебор! (Bust)", 0)
        else:
            embed = embed_builder.get_embed(
                "casino_blackjack_game",
                player_hand=self.format_hand(self.player_hand),
                player_score=score,
                dealer_hand=self.format_hand(self.dealer_hand, hide_dealer=True),
                dealer_score="?",
                bet=format_money(self.bet),
                author_avatar=self.author.display_avatar.url
            )
            await inter.response.edit_message(embed=embed, view=self)

    @disnake.ui.button(label="Хватит (Stand)", style=disnake.ButtonStyle.danger)
    async def stand(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.author.id: return
        await inter.response.defer()
        
        while self.calculate_score(self.dealer_hand) < 17:
            self.dealer_hand.append(self.draw())
            
        p_score = self.calculate_score(self.player_hand)
        d_score = self.calculate_score(self.dealer_hand)
        
        if d_score > 21:
            await self.end_game(inter, "Дилер перебрал! Вы выиграли.", 2.0)
        elif d_score > p_score:
            await self.end_game(inter, "У дилера больше.", 0)
        elif d_score < p_score:
            await self.end_game(inter, "У вас больше!", 2.0)
        else:
            await self.end_game(inter, "Равный счет.", 1.0)


class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cfg = ECO_CFG.get("casino", {})

    async def check_balance(self, inter, amount):
        user_db = await self.bot.db.get_user(inter.author)
        money = user_db['money']
        
        if amount < self.cfg.get("min_bet", 10):
            await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text=f"Минимальная ставка: {format_money(self.cfg.get('min_bet', 10))}", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
            return False
            
        if amount > self.cfg.get("max_bet", 1000000):
            await inter.edit_original_response(
                embed=embed_builder.get_embed("error_generic", text=f"Максимальная ставка: {format_money(self.cfg.get('max_bet', 1000000))}", author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
            return False

        if money < amount:
            await inter.edit_original_response(
                embed=embed_builder.get_embed("error_no_money_details", balance=format_money(money), needed=amount, author_avatar=inter.author.display_avatar.url),
                ephemeral=True
            )
            return False
            
        return True

    @commands.slash_command(name="казино", description="Играть в азартные игры")
    @blacklist_check()
    @maintenance_check()
    @prison_check()
    async def casino(self, inter):
        await inter.response.defer()
        pass

    @casino.sub_command(name="слоты", description="Крутить барабан")
    async def slots(self, inter, bet: int = commands.Param(name="ставка", gt=0)):
        await inter.response.defer()
        if not await self.check_balance(inter, bet): return

        await self.bot.db.update_money(inter.author, -bet, 0)
        
        symbols = self.cfg["slots"]["symbols"]
        row = [random.choice(symbols) for _ in range(3)]

        await inter.response.send_message(
            embed=disnake.Embed(description=f"🎰 | {symbols[0]} {symbols[1]} {symbols[2]} | ...крутим...", color=disnake.Color.blurple())
        )
        await asyncio.sleep(1)
        
        result_text = f"🎰 | {row[0]} {row[1]} {row[2]} |"
        
        win_mult = 0
        if row[0] == row[1] == row[2]:
            if row[0] == "7️⃣":
                win_mult = self.cfg["slots"]["multipliers"].get("777", 50.0)
            else:
                win_mult = self.cfg["slots"]["multipliers"].get("3_match", 5.0)
        elif row[0] == row[1] or row[1] == row[2] or row[0] == row[2]:
            win_mult = self.cfg["slots"]["multipliers"].get("2_match", 2.0)
            
        if win_mult > 0:
            prize = int(bet * win_mult)
            await self.bot.db.update_money(inter.author, prize, 0)
            
            embed = embed_builder.get_embed(
                "casino_win",
                game_name="Слоты 🎰",
                bet=format_money(bet),
                prize=format_money(prize),
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            embed.description = f"{result_text}\n\n" + embed.description
        else:
            embed = embed_builder.get_embed(
                "casino_lose",
                game_name="Слоты 🎰",
                bet=format_money(bet),
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            embed.description = f"{result_text}\n\n" + embed.description

        await inter.edit_original_message(content=None, embed=embed)

    @casino.sub_command(name="кости", description="Бросить кубики")
    async def dice(self, inter, bet: int = commands.Param(name="ставка", gt=0)):
        await inter.response.defer()
        if not await self.check_balance(inter, bet): return

        await self.bot.db.update_money(inter.author, -bet, 0)
        
        user_roll = random.randint(1, 6) + random.randint(1, 6)
        bot_roll = random.randint(1, 6) + random.randint(1, 6)
        
        desc = f"🎲 Вы выбросили: **{user_roll}**\n🤖 Бот выбросил: **{bot_roll}**"
        
        if user_roll > bot_roll:
            prize = int(bet * 2)
            await self.bot.db.update_money(inter.author, prize, 0)
            embed = embed_builder.get_embed("casino_win", game_name="Кости 🎲", bet=format_money(bet), prize=format_money(prize), author_name=inter.author.display_name, author_avatar=inter.author.display_avatar.url)
            embed.description = f"{desc}\n\n" + embed.description
        elif user_roll < bot_roll:
            embed = embed_builder.get_embed("casino_lose", game_name="Кости 🎲", bet=format_money(bet), author_name=inter.author.display_name, author_avatar=inter.author.display_avatar.url)
            embed.description = f"{desc}\n\n" + embed.description
        else:
            await self.bot.db.update_money(inter.author, bet, 0)
            embed = disnake.Embed(title="🤝 Ничья", description=f"{desc}\n\n💰 Ставка возвращена.", color=disnake.Color.yellow())
            
        await inter.edit_original_response(embed=embed)

    @casino.sub_command(name="блэкджек", description="Карточная игра 21")
    async def blackjack(self, inter, bet: int = commands.Param(name="ставка", gt=0)):
        await inter.response.defer()
        if not await self.check_balance(inter, bet): return

        await self.bot.db.update_money(inter.author, -bet, 0)
        
        view = BlackjackView(self.bot, inter.author, bet)
        
        p_score = view.calculate_score(view.player_hand)
        if p_score == 21:
            payout = self.cfg.get("blackjack", {}).get("blackjack_payout", 2.5)
            prize = int(bet * payout)
            await self.bot.db.update_money(inter.author, prize, 0)
            
            embed = embed_builder.get_embed(
                "casino_win",
                game_name="Блэкджек (Натуральный!) 🃏",
                bet=format_money(bet),
                prize=format_money(prize),
                author_name=inter.author.display_name,
                author_avatar=inter.author.display_avatar.url
            )
            embed.description = f"**Ваши карты:** {view.format_hand(view.player_hand)}\n\n" + embed.description
            return await inter.edit_original_response(embed=embed)

        embed = embed_builder.get_embed(
            "casino_blackjack_game",
            player_hand=view.format_hand(view.player_hand),
            player_score=p_score,
            dealer_hand=view.format_hand(view.dealer_hand, hide_dealer=True),
            dealer_score="?",
            bet=format_money(bet),
            author_avatar=inter.author.display_avatar.url
        )
        
        await inter.edit_original_response(embed=embed, view=view)

def setup(bot):
    bot.add_cog(Casino(bot))