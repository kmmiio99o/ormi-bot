import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import pyfiglet
import asyncio

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Synchronized emoji sets for consistent visual style
        self.love_emojis = ["💖", "💕", "💓", "💗", "💘", "💝", "💞"]
        self.rainbow_emojis = ["🌈", "🏳️‍🌈", "🏳️‍⚧️"]
        self.heart_emojis = ["♡", "♥", "♡", "♥"]
        self.animation_chars = ["|", "/", "-", "\\"]

    @app_commands.command(name="rate", description="Rates something 1-10 with stars ✨")
    @app_commands.describe(thing="What to rate")
    async def rate(self, interaction: discord.Interaction, thing: str):
        """Rates something 1-10 with stars ✨"""
        # Convert to lowercase for easier processing
        thing_lower = thing.lower()
        
        # Check for positive/negative keywords to make it seem like it's actually rating
        positive_keywords = ['good', 'great', 'awesome', 'amazing', 'best', 'love', 'like', 'cool', 'nice', 'fun', 'happy', 'wonderful', 'fantastic', 'excellent']
        negative_keywords = ['bad', 'terrible', 'awful', 'hate', 'worst', 'suck', 'horrible', 'boring', 'sad', 'unhappy', 'dislike']
        
        # Count positive and negative keywords
        positive_count = sum(1 for word in positive_keywords if word in thing_lower)
        negative_count = sum(1 for word in negative_keywords if word in thing_lower)
        
        # Base rating on hash of the input for consistency (same input = same rating)
        hash_value = sum(ord(c) for c in thing_lower) % 100
        
        # Calculate rating (1-10) based on keywords and hash
        base_rating = 5 + (positive_count - negative_count)
        rating = max(1, min(10, base_rating + (hash_value % 6) - 2))
        
        # Create stars
        stars = "⭐" * rating + "☆" * (10 - rating)
        
        # Add a reason that matches the rating
        if rating >= 9:
            reason = "Absolutely amazing! This is perfection!"
        elif rating >= 7:
            reason = "Really great! I'm impressed with this!"
        elif rating >= 5:
            reason = "Pretty good! Solid choice overall."
        elif rating >= 3:
            reason = "It's okay, but could use some improvement."
        else:
            reason = "Needs work. This one's not great..."
        
        # Add special cases for certain inputs
        special_cases = {
            "bot": "As a bot myself, I have to give fellow bots a perfect score! 🤖",
            "discord": "Discord is awesome! No surprise here. 💬",
            "python": "Python is the best programming language! 🐍",
            "javascript": "JavaScript is... interesting. It works, I guess. 🌐",
            "me": f"You're a {rating}/10 kind of person! Keep being awesome! 😊",
            "myself": f"You're a {rating}/10 kind of person! Self-love is important! 💖",
            "nothing": "Nothing gets a perfect 10 for being nothing! ✨",
            "something": "Something is better than nothing! Good choice. 🌟"
        }
        
        for special_thing, special_reason in special_cases.items():
            if special_thing in thing_lower:
                reason = special_reason
                break
        
        embed = discord.Embed(
            title=f"Rating for '{thing}'",
            description=f"{stars} ({rating}/10)\n*{reason}*",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        # Add a cute footer with the user's name
        embed.set_footer(
            text=f"Rated by {interaction.user.display_name} ~ UwU",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
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

    @app_commands.command(name="ship", description="Calculate ship compatibility between two users")
    @app_commands.describe(user1="First user to ship", user2="Second user to ship (optional)")
    async def ship(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member = None):
        """Calculate ship compatibility between two users"""
        if user2 is None:
            user2 = interaction.user

        if user1 == user2:
            return await interaction.response.send_message(
                "❌ You can't ship with yourself! Find a friend to ship with nyaa~",
                ephemeral=True
            )

        love_emoji = random.choice(self.love_emojis)
        loading_embed = discord.Embed(
            title=f"{love_emoji} Ship Calculator {love_emoji}",
            description=f"Calculating compatibility between {user1.mention} and {user2.mention}...",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        loading_embed.set_footer(
            text=f"Calculating... {love_emoji}",
            icon_url=user1.avatar.url if user1.avatar else None
        )
        await interaction.response.send_message(embed=loading_embed)

        percentage = random.randint(70, 100)
        for i in range(3):
            love_emoji = random.choice(self.love_emojis)
            loading_embed.description = f"Calculating compatibility between {user1.mention} and {user2.mention}... {love_emoji}"
            loading_embed.set_footer(
                text=f"Calculating... {'.' * (i + 1)}",
                icon_url=user1.avatar.url if user1.avatar else None
            )
            await asyncio.sleep(0.5)
            await interaction.edit_original_response(embed=loading_embed)

        name1 = user1.display_name[:len(user1.display_name)//2]
        name2 = user2.display_name[len(user2.display_name)//2:]
        ship_name = (name1 + name2).title()

        # 10 emoji for 10% each
        emoji_count = 10
        filled = int(percentage / 100 * emoji_count)
        love_emoji = random.choice(self.love_emojis)
        meter = love_emoji * filled + "💔" * (emoji_count - filled)

        if percentage >= 95:
            message = "🔥 **SOULMATES!** 🔥 Perfect match! Destiny has brought you together!"
        elif percentage >= 85:
            message = "💫 **MEANT TO BE!** 💫 You two are a match made in heaven!"
        elif percentage >= 75:
            message = "✨ **GREAT MATCH!** ✨ Strong connection, keep nurturing it!"
        else:
            message = "🌸 **PRETTY GOOD!** 🌸 You have great potential together!"

        embed = discord.Embed(
            title=f"{love_emoji} {ship_name} {love_emoji}",
            description=f"{user1.mention} ❤️ {user2.mention}\n\n"
                        f"{meter} **{percentage}%**\n\n"
                        f"{message}",
            color=discord.Color.pink(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(
            text="Love is in the air! ✨ UwU",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="howgay", description="Checks how gay a user is")
    @app_commands.describe(user="The user to check (defaults to yourself)")
    async def howgay(self, interaction: discord.Interaction, user: discord.Member = None):
        """Checks how gay a user is"""
        user = user or interaction.user

        rainbow_emoji = random.choice(self.rainbow_emojis)
        loading_embed = discord.Embed(
            title=f"{rainbow_emoji} Gay Meter {rainbow_emoji}",
            description=f"Measuring gay percentage for {user.mention}...",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        loading_embed.set_footer(
            text="Measuring... |",
            icon_url=user.avatar.url if user.avatar else None
        )
        await interaction.response.send_message(embed=loading_embed)

        percentage = random.randint(0, 100)
        for i in range(5):
            rainbow_emoji = random.choice(self.rainbow_emojis)
            char = self.animation_chars[i % len(self.animation_chars)]
            loading_embed.set_footer(
                text=f"Measuring... {char}",
                icon_url=user.avatar.url if user.avatar else None
            )
            await asyncio.sleep(0.4)
            await interaction.edit_original_response(embed=loading_embed)

        # 10 emoji for 10% each
        emoji_count = 10
        filled = int(percentage / 100 * emoji_count)
        rainbow_emoji = random.choice(self.rainbow_emojis)
        meter = rainbow_emoji * filled + "⚪" * (emoji_count - filled)

        if percentage >= 90:
            level = f"{rainbow_emoji}✨ ULTRA GAY GOD ✨{rainbow_emoji}"
            description = "You're radiating pure rainbow energy! The LGBTQ+ community crown you their QUEEN/KING! 🌟👑"
        elif percentage >= 75:
            level = f"{rainbow_emoji} ULTRA GAY {rainbow_emoji}"
            description = "You're practically made of rainbows! Your gayness is off the charts! 🌈💖"
        elif percentage >= 60:
            level = f"{rainbow_emoji} VERY GAY {rainbow_emoji}"
            description = "You're spreading rainbow vibes everywhere you go! Keep shining! ✨💫"
        elif percentage >= 40:
            level = f"{rainbow_emoji} GAY {rainbow_emoji}"
            description = "You've got those sweet rainbow vibes! Living your truth! 💕"
        elif percentage >= 25:
            level = f"{rainbow_emoji} A BIT GAY {rainbow_emoji}"
            description = "You've got a sprinkle of rainbow in your life! Nothing wrong with that! 🌼"
        else:
            level = f"{rainbow_emoji} NOT VERY GAY {rainbow_emoji}"
            description = "You're more of a pastel shade than a full rainbow... but that's okay! 🌤️"

        embed = discord.Embed(
            title=level,
            description=description,
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(
            name="Gay Meter",
            value=f"{meter}\n**{percentage}%**",
            inline=False
        )
        embed.set_footer(
            text="Love is love! 💖 Stay proud! ✨",
            icon_url=user.avatar.url if user.avatar else None
        )
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="simprate", description="Checks how much a user simps")
    @app_commands.describe(user="The user to check (defaults to yourself)")
    async def simprate(self, interaction: discord.Interaction, user: discord.Member = None):
        """Checks how much a user simps"""
        user = user or interaction.user

        heart_emoji = random.choice(self.heart_emojis)
        loading_embed = discord.Embed(
            title=f"{heart_emoji} Simp Meter {heart_emoji}",
            description=f"Measuring simp level for {user.mention}...",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        loading_embed.set_footer(
            text="Measuring... ♡",
            icon_url=user.avatar.url if user.avatar else None
        )
        await interaction.response.send_message(embed=loading_embed)

        percentage = random.randint(0, 100)
        for i in range(5):
            heart_emoji = random.choice(self.heart_emojis)
            char = self.heart_emojis[i % len(self.heart_emojis)]
            loading_embed.set_footer(
                text=f"Measuring... {char}",
                icon_url=user.avatar.url if user.avatar else None
            )
            await asyncio.sleep(0.4)
            await interaction.edit_original_response(embed=loading_embed)

        # 10 emoji for 10% each
        emoji_count = 10
        filled = int(percentage / 100 * emoji_count)
        love_emoji = random.choice(self.love_emojis)
        meter = love_emoji * filled + "⚪" * (emoji_count - filled)

        if percentage >= 90:
            level = f"💝 ULTRA SIMP GODDESS 💝"
            description = "You're simping so hard you've reached godhood! The simp council bows before you! 🙇‍♀️👑"
        elif percentage >= 75:
            level = f"💖 HARD SIMP 💖"
            description = "You're simping at an Olympic level! Your devotion knows no bounds! 🏆💞"
        elif percentage >= 60:
            level = f"💗 DEDICATED SIMP 💗"
            description = "You're fully committed to the simp life! Your heart is in the right place! ❤️"
        elif percentage >= 40:
            level = f"💕 CASUAL SIMP 💕"
            description = "You're enjoying the simp life without going overboard! Balance is key! 🌸"
        elif percentage >= 25:
            level = f"💓 LIGHT SIMP 💓"
            description = "You're dipping your toes in the simp waters! Nothing wrong with a little devotion! 🌼"
        else:
            level = f"💔 NOT A SIMP 💔"
            description = "You're keeping your heart protected! No simp energy detected! 🛡️"

        embed = discord.Embed(
            title=f"{level} ({percentage}%)",
            description=description,
            color=discord.Color.pink(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(
            name="Simp Meter",
            value=f"{meter}\n**{percentage}%**",
            inline=False
        )
        embed.set_footer(
            text="Simp responsibly! 💖 Or don't, we don't judge! ✨",
            icon_url=user.avatar.url if user.avatar else None
        )
        await interaction.edit_original_response(embed=embed)

async def setup(bot):
    await bot.add_cog(FunCog(bot))