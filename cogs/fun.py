import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import pyfiglet

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rate", description="Rates something 1-10 with stars ✨")
    @app_commands.describe(thing="What to rate")
    async def rate(self, interaction: discord.Interaction, thing: str):
        """Rates something 1-10 with stars ✨"""
        rating = random.randint(1, 10)
        stars = "⭐" * rating + "☆" * (10 - rating)

        embed = discord.Embed(
            title=f"Rating for '{thing}'",
            description=f"{stars} ({rating}/10)",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rps", description="Play rock-paper-scissors")
    @app_commands.describe(choice="Your choice: rock, paper, or scissors")
    async def rps(self, interaction: discord.Interaction, choice: str):
        """Play rock-paper-scissors ✨"""
        # Normalize the choice
        choice = choice.lower()
        if choice not in ['rock', 'paper', 'scissors']:
            return await interaction.response.send_message(
                "❌ Invalid choice! Use `rock`, `paper` or `scissors`",
                ephemeral=True
            )

        # Bot's choice
        bot_choice = random.choice(['rock', 'paper', 'scissors'])

        # Determine result
        if choice == bot_choice:
            result = "It's a tie! (◕‿◕)"
        elif (choice == 'rock' and bot_choice == 'scissors') or \
             (choice == 'paper' and bot_choice == 'rock') or \
             (choice == 'scissors' and bot_choice == 'paper'):
            result = "You win! 🎉"
        else:
            result = "I win! 😈"

        embed = discord.Embed(
            title="Rock-Paper-Scissors",
            description=f"**Your choice:** {choice.title()}\n"
                        f"**My choice:** {bot_choice.title()}\n"
                        f"**Result:** {result}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="8ball", description="Ask magic 8-ball a question")
    @app_commands.describe(question="Your question for the 8-ball")
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        """Ask magic 8-ball a question"""
        responses = [
            "It is certain. UwU",
            "It is decidedly so. Nyaa~",
            "Without a doubt. (•̀ᴗ•́)و",
            "Yes - definitely. 🥰",
            "You may rely on it. ✨",
            "As I see it, yes. 💫",
            "Most likely. 🌈",
            "Outlook good. 🌟",
            "Yes. 🌸",
            "Signs point to yes. 🌼",
            "Reply hazy, try again. 🌫️",
            "Ask again later. 🌙",
            "Better not tell you now. 🌚",
            "Cannot predict now. 🌌",
            "Concentrate and ask again. 🌠",
            "Don't count on it. 💀",
            "My reply is no. ❌",
            "My sources say no. 🔮",
            "Outlook not so good. 🌧️",
            "Very doubtful. 🌪️"
        ]

        response = random.choice(responses)

        embed = discord.Embed(
            title="🎱 Magic 8-Ball",
            description=f"**Question:** {question}\n"
                        f"**Answer:** {response}",
            color=discord.Color.dark_blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ascii", description="Converts text to ASCII art")
    @app_commands.describe(text="Text to convert to ASCII art")
    async def ascii_art(self, interaction: discord.Interaction, text: str):
        """Converts text to ASCII art"""
        try:
            # Generate ASCII art with pyfiglet
            ascii_text = pyfiglet.figlet_format(text, font="standard")

            # Discord has a 2000 character limit
            if len(ascii_text) > 1990:
                return await interaction.response.send_message(
                    "❌ Text too long for ASCII art conversion!",
                    ephemeral=True
                )

            await interaction.response.send_message(f"```{ascii_text}```")
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error generating ASCII art: {e}",
                ephemeral=True
            )

    @app_commands.command(name="random", description="Generates random number")
    @app_commands.describe(min_val="Minimum value (default: 1)", max_val="Maximum value (default: 100)")
    async def random_number(self, interaction: discord.Interaction, min_val: int = 1, max_val: int = 100):
        """Generates random number"""
        if min_val > max_val:
            return await interaction.response.send_message(
                "❌ Minimum value must be less than or equal to maximum value!",
                ephemeral=True
            )

        num = random.randint(min_val, max_val)

        embed = discord.Embed(
            title="🎲 Random Number Generator",
            description=f"Your random number between {min_val} and {max_val} is:\n"
                        f"**{num}**",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(FunCog(bot))
