from disnake.ext import commands
from utils.embeds import EmbedBuilder
from utils.decorators import prison_check, maintenance_check


embed_builder = EmbedBuilder()

class Transactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="транзакции", description="История ваших переводов")
    @prison_check()
    @maintenance_check()
    async def transactions(self, inter):
        await inter.response.defer()

        history = await self.bot.db.get_user_transactions(inter.author.id)

        if not history:
            history_text = "*Транзакций не найдено...*"
        else:
            lines = []
            for t in history:
                is_sender = (t['sender_id'] == inter.author.id)
                
                other_id = t['target_id'] if is_sender else t['sender_id']
                amount = t['amount']
                time_str = f"<t:{int(t['created_at'])}:d>"
                
                icon_src = "💵" if t['source_type'] == "money" else "💳"
                icon_trg = "💵" if t['target_type'] == "money" else "💳"

                if is_sender:
                    line = f"🔴 **-{amount}** | {icon_src} ➔ {icon_trg} <@{other_id}> | {time_str}"
                else:
                    line = f"🟢 **+{amount}** | <@{other_id}> {icon_src} ➔ {icon_trg} Вы | {time_str}"
                
                lines.append(line)
            
            history_text = "\n".join(lines)

        embed = embed_builder.get_embed(
            name="transaction_history",
            user_mention=inter.author.mention,
            history_text=history_text,
            author_name=inter.author.display_name,
            author_avatar=inter.author.display_avatar.url
        )
        await inter.send(embed=embed)

def setup(bot):
    bot.add_cog(Transactions(bot))