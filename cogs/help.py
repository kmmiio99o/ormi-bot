import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View
from typing import Optional
import datetime
import random
import asyncio
from utils.logger import get_logger

logger = get_logger(__name__)

class CategorySelect(Select):
    def __init__(self, categories, current_category=None):
        options = []
        for category_name, category_data in categories.items():
            # Add indicator if this is the current category
            indicator = "✨ " if category_name == current_category else ""
            options.append(
                discord.SelectOption(
                    label=f"{category_data['emoji']} {indicator}{category_name.split(' ', 1)[1] if ' ' in category_name else category_name}",
                    description=category_data['description'],
                    emoji=category_data['emoji'],
                    value=category_name
                )
            )

        super().__init__(
            placeholder="✨ Select a category...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.categories = categories

    async def callback(self, interaction: discord.Interaction):
        selected_category = self.categories[self.values[0]]

        # Create animated embed for selected category
        embed = await self.create_category_embed(interaction, selected_category, self.values[0])

        # Update the view with the new selection indicator
        new_view = HelpView(self.categories, current_category=self.values[0])
        new_view.add_item(CategorySelect(self.categories, current_category=self.values[0]))

        await interaction.response.edit_message(embed=embed, view=new_view)

    async def create_category_embed(self, interaction, category_data, category_name):
        """Create an animated embed for the selected category"""
        # Create base embed
        embed = discord.Embed(
            color=category_data['color'],
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        # Set default title and description in case no specific category matches
        title = f"❓ {category_name}"
        description = category_data['description']

        # Category-specific animations and formatting
        if "Information" in category_name:
            # Information category animation
            title = f"📚 {category_name}"
            description = f"{category_data['description']}\n\n" \
                          f"🔍 *Gathering information...*"

            # Add typing animation
            typing_dots = "." * ((int(datetime.datetime.now().timestamp()) % 3) + 1)
            description = description.replace("...", typing_dots)

            # Add book animation
            book_emoji = random.choice(["📖", "📗", "📘", "📙", "📔", "📒", "📓"])
            title = f"{book_emoji} {category_name}"

            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1026243190444474459.webp?size=96&quality=lossless")

        elif "Fun" in category_name:
            # Fun category animation
            title = f"🎭 {category_name}"
            description = f"{category_data['description']}\n\n" \
                          f"🎉 *Loading fun activities...*"

            # Add random fun emoji
            fun_emojis = ["🎪", "🎡", "🎠", "🎲", "🎯", "🎳", "🎮"]
            title = f"{random.choice(fun_emojis)} {category_name}"

            # Add spinning animation
            spinning_index = int(datetime.datetime.now().timestamp() * 2) % 8
            spinner = "◴◷⚅⚄⚃⚂⚁⚱"[spinning_index]
            description = description.replace("...", f" {spinner}")

            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1026243185895837716.webp?size=96&quality=lossless")

        elif "Moderation" in category_name:
            # Moderation category animation
            title = f"👮 {category_name}"
            description = f"{category_data['description']}\n\n" \
                          f"🛡️ *Loading moderation tools...*"

            # Shield animation
            shield_animation = ["🛡️", "🛡️✨", "✨🛡️", "✨🛡️✨"]
            animation_index = int(datetime.datetime.now().timestamp() * 2) % len(shield_animation)
            title = f"{shield_animation[animation_index]} {category_name}"

            # Add progress bar
            progress = int((datetime.datetime.now().timestamp() % 10) / 10 * 10)
            progress_bar = "🟩" * progress + "⬜" * (10 - progress)
            description = f"{category_data['description']}\n\n{progress_bar}"

            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1026243181986291723.webp?size=96&quality=lossless")

        elif "Configuration" in category_name:
            # Configuration category animation
            title = f"⚙️ {category_name}"
            description = f"{category_data['description']}\n\n" \
                          f"🔧 *Setting up configuration...*"

            # Gear animation
            gear_emojis = ["⚙️", "⚙️🔧", "🔧⚙️", "🔧⚙️🔧"]
            animation_index = int(datetime.datetime.now().timestamp() * 2) % len(gear_emojis)
            title = f"{gear_emojis[animation_index]} {category_name}"

            # Add loading bar
            progress = int((datetime.datetime.now().timestamp() % 10) / 10 * 10)
            progress_bar = "🟦" * progress + "⬜" * (10 - progress)
            description = f"{category_data['description']}\n\n{progress_bar}"

            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1026243177785704458.webp?size=96&quality=lossless")

        # Set the final title and description
        embed.title = title
        embed.description = description

        # Add commands to embed with permission indicators
        # --- KEY CHANGE: Show ALL commands, regardless of user's actual permissions ---
        for cmd in category_data['commands']:
            cmd_name = cmd[0]
            cmd_desc = cmd[1]

            # Add permission indicators with emojis (based on command definition)
            if len(cmd) > 2:
                permission_type = cmd[2].__name__
                if permission_type == 'is_admin':
                    cmd_desc += " `👑 Admin`"
                elif permission_type == 'is_owner':
                    cmd_desc += " `👑 Bot Owner`"
                elif permission_type == 'has_kick_permission':
                    cmd_desc += " `👢 Kick`"
                elif permission_type == 'has_ban_permission':
                    cmd_desc += " `🔨 Ban`"
                elif permission_type == 'has_moderate_members':
                    cmd_desc += " `🔇 Mute`"
                elif permission_type == 'has_manage_messages':
                    cmd_desc += " `🧹 Purge`"
                elif permission_type == 'has_manage_channels':
                    cmd_desc += " `🔒 Channel`"
                elif permission_type == 'has_manage_nicknames':
                    cmd_desc += " `✏️ Nickname`"

            # Add cute formatting to command descriptions
            if "Moderation" in category_name:
                cmd_desc = f"🛡️ {cmd_desc}"
            elif "Information" in category_name:
                cmd_desc = f"ℹ️ {cmd_desc}"
            elif "Fun" in category_name:
                cmd_desc = f"🎭 {cmd_desc}"
            elif "Configuration" in category_name:
                cmd_desc = f"⚙️ {cmd_desc}"

            embed.add_field(
                name=f"`{cmd_name}`",
                value=cmd_desc,
                inline=False
            )

        # Add cute footer based on category
        # Set default footer text in case no specific category matches
        footer_text = "✨ Discover something new! ✨"

        if "Information" in category_name:
            footer_text = "📚 Knowledge is power! Keep learning nyaa~"
        elif "Fun" in category_name:
            footer_text = "🎭 Life is too short to be serious all the time!"
        elif "Moderation" in category_name:
            footer_text = "👮 Keeping the server safe and sound! UwU"
        elif "Configuration" in category_name:
            footer_text = "⚙️ Customizing your server experience~"

        # Add random cute emoji to footer
        cute_emojis = ["🌸", "🐾", "✨", "💫", "🎀", "🍭", "🧸", "🐇", "🦊", "🐻"]
        footer_text += f" {random.choice(cute_emojis)}"

        embed.set_footer(
            text=footer_text,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )

        return embed

class HelpView(View):
    def __init__(self, categories, current_category=None):
        super().__init__(timeout=180.0)  # 3 minute timeout
        self.categories = categories
        self.message: Optional[discord.Message] = None
        self.current_category = current_category

    async def on_timeout(self):
        """Disable the view when it times out"""
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                item.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except (discord.NotFound, discord.HTTPException):
            pass

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.category_emojis = {
            "ℹ️ Information": "📚",
            "🎭 Fun": "🎭",
            "👮 Moderation": "👮",
            "⚙️ Configuration": "⚙️",
            "🔧 Utilities": "🔧"
        }

    @app_commands.command(name="help", description="Shows all available commands with beautiful interface")
    async def help(self, interaction: discord.Interaction):
        """Shows all available commands with a dropdown menu and animations"""
        # Define command categories with enhanced descriptions
        # --- NO CHANGES HERE: Categories and commands are defined as before ---
        categories = {
            'ℹ️ Information': {
                'emoji': 'ℹ️',
                'description': '🔍 General information commands to learn about users and servers',
                'color': 0x3498db,
                'commands': [
                    ('/userinfo [member]', 'Shows detailed information about a user'),
                    ('/serverinfo', 'Displays comprehensive server statistics and details'),
                    ('/ping', 'Shows bot latency and connection quality with animations'),
                    ('/uptime', 'Shows how long the bot has been online with cute formatting'),
                    ('/avatar [member]', 'Shows user avatar with direct link'),
                    ('/roleinfo <role>', 'Shows detailed information about a role'),
                    ('/emojiinfo <emoji>', 'Shows emoji information (ID, creation date)'),
                    ('/recentjoins', 'Shows recently joined members (last 10)'),
                ]
            },
            '🎭 Fun': {
                'emoji': '🎭',
                'description': '🎉 Fun and entertainment commands to spice up your server',
                'color': 0xFF6B6B,
                'commands': [
                    ('/rate <thing>', 'Rates something 1-10 with animated stars ✨'),
                    ('/rps <rock|paper|scissors>', 'Play rock-paper-scissors with cute animations'),
                    ('/8ball <question>', 'Ask the magic 8-ball a question with mystical responses'),
                    ('/ascii <text>', 'Converts text to beautiful ASCII art'),
                    ('/random [min] [max]', 'Generates random number with cute visualization'),
                    ('/ship <user1> <user2>', 'Ship two users together with compatibility percentage'),
                    ('/howgay <user>', 'Measures gay percentage with fun meter animation'),
                    ('/simprate <user>', 'Checks how much a user simps with cute rating'),
                ]
            },
            '👮 Moderation': {
                'emoji': '👮',
                'description': '🛡️ Powerful moderation tools to keep your server safe and organized',
                'color': 0xE74C3C,
                'commands': [
                    ('/kick <member> [reason]', 'Kicks a user from the server with confirmation', self.has_kick_permission),
                    ('/ban <user_id> [duration] [reason]', 'Bans a user from the server permanently or temporarily', self.has_ban_permission),
                    ('/unban <user_id>', 'Unbans a previously banned user', self.has_ban_permission),
                    ('/softban <member> [days] [reason]', 'Bans and immediately unbans to delete messages', self.has_ban_permission),
                    ('/mute <member> [duration] [reason]', 'Mutes a user for a specified time with timer', self.has_moderate_members),
                    ('/unmute <member>', 'Unmutes a user with confirmation', self.has_moderate_members),
                    ('/warn <member> [reason]', 'Gives a warning to a user with case ID', self.has_kick_permission),
                    ('/warnings <member>', 'Shows a user\'s warnings with detailed info', self.has_kick_permission),
                    ('/clearwarns <member>', 'Clears a user\'s warnings with confirmation', self.has_kick_permission),
                    ('/delwarn <case_id>', 'Deletes a specific warning with verification', self.has_kick_permission),
                    ('/editcase <case_id> <new_reason>', 'Edits the reason for a specific warning', self.has_kick_permission),
                    ('/case <case_id>', 'Shows details about a specific warning', self.has_kick_permission),
                    ('/purge <amount> [user]', 'Deletes messages (1-100) with user filter', self.has_manage_messages),
                    ('/slowmode <seconds>', 'Sets slowmode for the channel (0-21600)', self.has_manage_channels),
                    ('/lock [reason]', 'Locks the channel to prevent sending messages', self.has_manage_channels),
                    ('/unlock [reason]', 'Unlocks a previously locked channel', self.has_manage_channels),
                    ('/nick <member> [nickname]', 'Changes a user\'s nickname with preview', self.has_manage_nicknames),
                    ('/nuke', 'Deletes all messages in the channel with safety check', self.has_manage_messages),
                    ('/fg [channel]', 'Toggles file and GIF sending permissions for a channel', self.has_manage_channels),
                    ('/voicekick <member> [reason]', 'Kicks a user from voice channel', self.has_manage_channels),
                    ('/voiceban <member> [reason]', 'Prevents user from joining voice channels', self.has_manage_channels),
                    ('/voiceunban <member> [reason]', 'Allows user to join voice channels again', self.has_manage_channels),
                    ('/massban <ids> [reason]', 'Bans multiple users at once', self.has_ban_permission),
                    ('/hierarchy', 'Shows server power hierarchy with visual ranking', self.has_moderate_members),
                ]
            },
            '⚙️ Configuration': {
                'emoji': '⚙️',
                'description': '🔧 Server configuration commands to customize your experience',
                'color': 0x7289DA,
                'commands': [
                    ('/prefix <prefix>', 'Changes the bot prefix for this server', self.is_admin),
                    ('/slc <channel>', 'Sets log channel for moderation actions', self.is_admin),
                    ('/sdlc <channel>', 'Sets deleted messages log channel', self.is_admin),
                    ('/swc <channel>', 'Sets welcome channel for new members', self.is_admin),
                    ('/swm <message>', 'Sets welcome message for new members', self.is_admin),
                    ('/autorole <role>', 'Sets role for new members automatically', self.is_admin),
                    ('/color <hex>', 'Shows color sample from HEX code', self.is_admin),
                ]
            },
            '🛠️ Utilities': { # Or add these to '⚙️ Configuration'
                'emoji': '🛠️', # Or use '⚙️'
                'description': ' handy tools and utilities for everyday use',
                'color': 0xF1C40F, # A suitable color, e.g., gold/yellow
                'commands': [
                    ('/afk [reason]', 'Sets your AFK status. The bot will notify users who mention you.'),
                    ('/snipe', 'Shows the last deleted message in the current channel.'),
                    ('/invite', 'Generates an invite link for the bot.'),
                    ('/vote <question> <options>', 'Creates a poll. Separate options with | (e.g., Option1 | Option2).'),
                    ('/lastfm <username>', 'Shows statistics for a Last.fm user.'),
                    ('/color <color_input>', 'Shows a color sample. Use HEX (e.g., #FF5733) or name (e.g., red).'),
                ]
            },
        }

        # --- KEY CHANGE: Create visible categories WITHOUT filtering commands ---
        # Everyone sees all commands now, regardless of their actual permissions.
        # The permission indicators will inform them what they need.
        visible_categories = {}
        is_owner = interaction.user.id in self.bot.config.get('owners', [])
        is_admin = interaction.permissions.administrator

        # Iterate through categories and include ALL commands in each
        for category_name, category_data in categories.items():
            # Include the category with ALL its defined commands
            # No filtering based on interaction.user's permissions here
            visible_categories[category_name] = {
                'emoji': category_data['emoji'],
                'description': category_data['description'],
                'color': category_data['color'],
                'commands': category_data['commands'] # Show all commands
            }


        # Create initial help embed with animation
        embed = discord.Embed(
            title="✨ Bot Command Help Center ✨",
            description=(
                "Select a category below to see available commands!\n\n"
                "💫 *Loading interactive menu...*"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        # Add animated typing effect
        typing_dots = "." * ((int(datetime.datetime.now().timestamp()) % 3) + 1)
        if embed.description is not None:
            embed.description = embed.description.replace("...", typing_dots)

        # Add cute animated header
        cute_emojis = ["🌸", "🐾", "✨", "💫", "🎀", "🍭", "🧸", "🐇", "🦊", "🐻"]
        header_emoji = random.choice(cute_emojis)
        embed.title = f"{header_emoji} Bot Command Help Center {header_emoji}"

        # Add category statistics (shows total commands available)
        total_commands = sum(len(cat['commands']) for cat in visible_categories.values())
        embed.add_field(
            name="📊 Command Statistics",
            value=(
                f"**Total Categories:** {len(visible_categories)}\n"
                f"**Total Commands:** {total_commands}\n"
                f"**Your Permissions:** {'Owner' if is_owner else 'Admin' if is_admin else 'Member'}"
            ),
            inline=False
        )

        # Add cute tips section
        tips = [
            "💡 Tip: Some commands have special permissions requirements!",
            "💡 Tip: Moderation commands require appropriate permissions!",
            "💡 Tip: Fun commands are available to everyone!",
            "💡 Tip: Configuration commands require admin permissions!",
            "💡 Tip: Use `/ping` to check bot responsiveness!",
            "💡 Tip: `/purge` can delete up to 100 messages at once!",
            "💡 Tip: `/slowmode` accepts values from 0-21600 seconds!"
        ]
        embed.add_field(
            name="💡 Helpful Tips",
            value=random.choice(tips),
            inline=False
        )

        # Set cute footer with user info
        embed.set_footer(
            text=f"Requested by {interaction.user.display_name} ~ {datetime.datetime.now().strftime('%H:%M')}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )

        # Set a random cute thumbnail
        thumbnails = [
            "https://cdn.discordapp.com/emojis/1026243190444474459.webp?size=96&quality=lossless",
            "https://cdn.discordapp.com/emojis/1026243185895837716.webp?size=96&quality=lossless",
            "https://cdn.discordapp.com/emojis/1026243181986291723.webp?size=96&quality=lossless",
            "https://cdn.discordapp.com/emojis/1026243177785704458.webp?size=96&quality=lossless"
        ]
        embed.set_thumbnail(url=random.choice(thumbnails))

        # Create view with dropdown
        view = HelpView(visible_categories)
        select = CategorySelect(visible_categories)
        view.add_item(select)

        # Send initial message
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

        # Store the message reference for timeout handling
        # Ensure 'message' is always defined for subsequent edits.
        message = await interaction.original_response()
        view.message = message

        # Add subtle animation effect after initial load
        await asyncio.sleep(1.5)

        try:
            # Update embed with a more complete message
            embed.description = "Click the dropdown below to select a category nyaa~ 🐾\n\n"

            # Add a cute animated progress bar
            progress = "🟩" * 10  # Full progress since loading is done
            embed.add_field(
                name="✅ Loading Complete",
                value=f"Ready to serve! {progress}",
                inline=False
            )

            # Update the message
            # The original_response() call already ensures the response is done.
            await message.edit(embed=embed, view=view)
        except (discord.NotFound, discord.HTTPException) as e:
            logger.error(f"Error updating help message: {e}")

    # Permission check methods (same as before)
    def has_kick_permission(self, interaction: discord.Interaction) -> bool:
        return interaction.permissions.kick_members

    def has_ban_permission(self, interaction: discord.Interaction) -> bool:
        return interaction.permissions.ban_members

    def has_moderate_members(self, interaction: discord.Interaction) -> bool:
        return interaction.permissions.moderate_members

    def has_manage_messages(self, interaction: discord.Interaction) -> bool:
        return interaction.permissions.manage_messages

    def has_manage_channels(self, interaction: discord.Interaction) -> bool:
        return interaction.permissions.manage_channels

    def has_manage_nicknames(self, interaction: discord.Interaction) -> bool:
        return interaction.permissions.manage_nicknames

    def is_admin(self, interaction: discord.Interaction) -> bool:
        return interaction.permissions.administrator

    def is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in self.bot.config.get('owners', [])

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
