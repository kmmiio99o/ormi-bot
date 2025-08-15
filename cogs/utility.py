# cogs/utility.py

import discord
from discord import app_commands
from discord.ext import commands
import datetime
import json
import os
import aiohttp
from typing import Optional

# --- AFK Data Storage ---
# Ensure the data directory exists
os.makedirs('data', exist_ok=True)
AFK_DATA_FILE = 'data/afk_data.json'

def load_afk_data():
    """Load AFK data from file."""
    if os.path.exists(AFK_DATA_FILE):
        try:
            with open(AFK_DATA_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_afk_data(data):
    """Save AFK data to file."""
    try:
        with open(AFK_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except IOError:
        return False

# --- Snipe Data Storage ---
# Simple in-memory storage for last deleted message per channel
# Note: For production bots, consider using a more persistent/robust method
# and handling large guilds/channels efficiently.
snipe_data = {} # {channel_id: {'content': str, 'author': discord.User/Member, 'timestamp': datetime}}

class UtilityCog(commands.Cog):
    """Cog for utility commands like AFK, snipe, polls, etc."""

    def __init__(self, bot):
        self.bot = bot
        # Load AFK data when the cog is loaded
        self.afk_data = load_afk_data()
        # Initialize aiohttp session for web requests (e.g., Last.fm)
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    # --- AFK Command ---
    @app_commands.command(name="afk", description="Sets your AFK status.")
    @app_commands.describe(reason="The reason you are going AFK.")
    async def afk(self, interaction: discord.Interaction, reason: str = "Not specified"):
        """Sets AFK status for a user."""
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id) if interaction.guild else "DM"

        if guild_id not in self.afk_data:
            self.afk_data[guild_id] = {}

        self.afk_data[guild_id][user_id] = {
            "reason": reason,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        # Save data immediately
        if not save_afk_data(self.afk_data):
            await interaction.response.send_message(
                "❌ An error occurred while saving your AFK status.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="💤 AFK Status Set",
            description=f"You are now marked as AFK.\n**Reason:** {reason}",
            color=discord.Color.light_grey(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text="I'll notify others when you're mentioned.")
        await interaction.response.send_message(embed=embed)

    # --- AFK Listener (to notify when AFK user is mentioned) ---
    # This requires an event listener, not a slash command.
    # It's included here as part of the AFK functionality.
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listener to handle AFK notifications and status removal."""
        if message.author.bot or not message.guild:
            return

        # 1. Check if message author is AFK
        author_id = str(message.author.id)
        guild_id = str(message.guild.id)
        was_afk = False
        afk_reason = None
        afk_time = None

        if guild_id in self.afk_data and author_id in self.afk_data[guild_id]:
            was_afk = True
            afk_info = self.afk_data[guild_id][author_id]
            afk_reason = afk_info.get("reason", "Not specified")
            afk_time = datetime.datetime.fromisoformat(afk_info["timestamp"])
            del self.afk_data[guild_id][author_id]
            
            if not self.afk_data[guild_id]:
                del self.afk_data[guild_id]
            save_afk_data(self.afk_data)

            # Send welcome back embed
            welcome_embed = discord.Embed(
                title="👋 Welcome Back!",
                description=f"{message.author.mention}, I've removed your AFK status",
                color=discord.Color.green()
            )
            welcome_embed.add_field(
                name="You were AFK for",
                value=discord.utils.format_dt(afk_time, "R"),
                inline=True
            )
            if afk_reason != "Not specified":
                welcome_embed.add_field(
                    name="Your Reason",
                    value=afk_reason,
                    inline=False
                )
            await message.channel.send(embed=welcome_embed)

        # 2. Check mentioned AFK users
        for user in message.mentions:
            user_id = str(user.id)
            if guild_id in self.afk_data and user_id in self.afk_data[guild_id]:
                afk_info = self.afk_data[guild_id][user_id]
                afk_time = datetime.datetime.fromisoformat(afk_info["timestamp"])
                reason = afk_info.get("reason", "Not specified")
                
                # Send AFK mention embed
                mention_embed = discord.Embed(
                    title="💤 AFK User Mentioned",
                    description=f"{user.mention} is currently AFK",
                    color=discord.Color.orange()
                )
                mention_embed.add_field(
                    name="Reason",
                    value=reason,
                    inline=False
                )
                mention_embed.add_field(
                    name="AFK Since", 
                    value=discord.utils.format_dt(afk_time, "R"),
                    inline=True
                )
                mention_embed.set_footer(text="They'll be notified of your mention when they return")
                await message.channel.send(embed=mention_embed)

    # --- Snipe Command ---
    @app_commands.command(name="snipe", description="Shows the last deleted message in this channel.")
    async def snipe(self, interaction: discord.Interaction):
        """Shows the last deleted message in the current channel."""
        channel_id = interaction.channel.id

        if channel_id not in snipe_data:
            return await interaction.response.send_message(
                "❌ There's nothing to snipe in this channel!",
                ephemeral=True
            )

        snipe_info = snipe_data[channel_id]
        content = snipe_info['content']
        author = snipe_info['author']
        timestamp = snipe_info['timestamp']

        embed = discord.Embed(
            title="🕵️ Sniped Message",
            description=content if content else "*No content (e.g., attachment only)*",
            color=discord.Color.dark_teal(),
            timestamp=timestamp
        )
        embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
        embed.set_footer(text=f"Deleted in #{interaction.channel.name}")

        await interaction.response.send_message(embed=embed)

    # --- Snipe Listener (to capture deleted messages) ---
    # This also requires an event listener.
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Listener to store deleted messages for sniping."""
        # Ignore bot messages or messages in private channels
        if message.author.bot or not message.guild:
            return

        # Store the deleted message info
        snipe_data[message.channel.id] = {
            'content': message.content,
            'author': message.author,
            'timestamp': message.created_at # Use the original creation time
        }
        # Optionally, you could store attachments, embeds, etc. here too.

    # --- Invite Command ---
    @app_commands.command(name="invite", description="Generates an invite link for the bot.")
    async def invite(self, interaction: discord.Interaction):
        """Generates an invite link for the bot."""
        # Requires 'applications.commands' scope for slash commands
        # and relevant permissions scopes.
        # Adjust permissions integer as needed.
        permissions = discord.Permissions(
            # General
            read_messages=True,
            send_messages=True,
            send_messages_in_threads=True,
            manage_messages=True, # For purge/snipe if needed
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            # Moderation
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            manage_nicknames=True,
            manage_channels=True,
            manage_roles=True,
            view_audit_log=True,
            # Voice (if applicable)
            move_members=True,
            mute_members=True,
            # Misc
            manage_guild=True, # For prune, clearinvites if needed
            create_public_threads=True,
            create_private_threads=True,
            use_external_emojis=True,
            use_external_stickers=True,
            use_embedded_activities=True,
            use_external_sounds=True,
            send_voice_messages=True,
            # Add more based on your bot's specific needs
        )

        invite_url = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=permissions,
            scopes=('bot', 'applications.commands')
        )

        embed = discord.Embed(
            title="🔗 Invite Me!",
            description=f"Click the link below to add me to your server!\n[Invite Link]({invite_url})",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Vote (Poll) Command ---
    @app_commands.command(name="vote", description="Creates a poll.")
    @app_commands.describe(question="The poll question.", options="Poll options separated by '|'. Max 10.")
    async def vote(self, interaction: discord.Interaction, question: str, options: str):
        """Creates a poll with up to 10 options."""
        option_list = [opt.strip() for opt in options.split('|') if opt.strip()]

        if not option_list:
            return await interaction.response.send_message(
                "❌ Please provide at least one option for the poll.",
                ephemeral=True
            )

        if len(option_list) > 10:
            return await interaction.response.send_message(
                "❌ You can only have up to 10 options in a poll.",
                ephemeral=True
            )

        if len(option_list) < 2:
             return await interaction.response.send_message(
                "❌ Please provide at least two options for the poll.",
                ephemeral=True
            )


        # Use number emojis for reactions (0-9)
        number_emojis = ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
        # Or use letter emojis (A-J) if preferred
        # letter_emojis = ['🇦', '🇧', '🇨', '🇩', '🇪', '🇫', '🇬', '🇭', '🇮', '🇯']

        embed = discord.Embed(
            title=f"📊 {question}",
            description="",
            color=discord.Color.random(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Poll created by {interaction.user.display_name}")

        for i, option in enumerate(option_list):
            # embed.description += f"{number_emojis[i+1]} {option}\n" # Start from 1️⃣
            embed.add_field(name=f"{number_emojis[i+1]} Option", value=option, inline=False)

        # Send the poll message first
        await interaction.response.send_message(embed=embed)
        # Get the message object to add reactions
        poll_message = await interaction.original_response()

        # Add reaction emojis
        for i in range(1, len(option_list) + 1): # Start from 1️⃣
            try:
                await poll_message.add_reaction(number_emojis[i])
            except discord.HTTPException:
                pass # Ignore if reaction fails to add

    # --- Color Command ---
    @app_commands.command(name="color", description="Shows a color sample from HEX code or name.")
    @app_commands.describe(color_input="HEX code (e.g., #FF5733) or color name (e.g., red, blue).")
    async def color(self, interaction: discord.Interaction, color_input: str):
        """Shows a color sample from HEX code or name."""
        try:
            # Try parsing as HEX first
            if color_input.startswith('#'):
                hex_input = color_input[1:]
            else:
                hex_input = color_input

            # Validate HEX format (should be 3 or 6 characters of 0-9, A-F)
            if not all(c in '0123456789ABCDEFabcdef' for c in hex_input) or len(hex_input) not in (3, 6):
                # If not valid HEX, try interpreting as a common color name
                # This is a basic mapping, you can expand it or use a library
                color_names = {
                    'red': '#FF0000', 'green': '#008000', 'blue': '#0000FF',
                    'yellow': '#FFFF00', 'purple': '#800080', 'orange': '#FFA500',
                    'pink': '#FFC0CB', 'brown': '#A52A2A', 'black': '#000000',
                    'white': '#FFFFFF', 'gray': '#808080', 'grey': '#808080',
                    'cyan': '#00FFFF', 'magenta': '#FF00FF', 'lime': '#00FF00',
                    'navy': '#000080', 'maroon': '#800000', 'olive': '#808000',
                    'teal': '#008080', 'silver': '#C0C0C0'
                }
                hex_input = color_names.get(color_input.lower())
                if not hex_input:
                    return await interaction.response.send_message(
                        f"❌ Invalid HEX code or unknown color name: `{color_input}`.\n"
                        f"Please use a format like `#FF5733` or a name like `red`.",
                        ephemeral=True
                    )

            # Standardize to 6-digit HEX
            if len(hex_input) == 3:
                hex_input = ''.join([c*2 for c in hex_input])

            # Create Discord Color object
            color_obj = discord.Color(int(hex_input, 16))

            embed = discord.Embed(
                title=f"🎨 Color Sample: {color_input}",
                description=f"**HEX:** `#{hex_input}`\n"
                            f"**RGB:** `rgb({color_obj.r}, {color_obj.g}, {color_obj.b})`\n"
                            f"**Integer:** `{color_obj.value}`",
                color=color_obj
            )
            # Add a large colored field or use the side color effectively
            embed.add_field(name="Preview", value="The color is shown in the embed border.", inline=False)

            await interaction.response.send_message(embed=embed)

        except ValueError:
            await interaction.response.send_message(
                f"❌ Invalid color input: `{color_input}`.\n"
                f"Please use a format like `#FF5733` or a name like `red`.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {e}",
                ephemeral=True
            )


async def setup(bot):
    """Setup function for the utility cog."""
    await bot.add_cog(UtilityCog(bot))
