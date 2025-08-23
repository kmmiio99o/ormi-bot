import discord
import logging
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

async def send_configuration_guide(guild):
    """Send configuration guide to moderator channel when bot joins a server"""
    # Find a moderator-only channel
    mod_channel = await find_moderator_channel(guild)

    if not mod_channel:
        logger.info(f"No moderator channel found for guild {guild.name}")
        return  # Don't send anything if no mod channel found

    # Create configuration guide embed
    embed = discord.Embed(
        title="✨ Ormi Bot setup guide! ✨",
        description=(
            "Hello there, server moderators! 🌸\n\n"
            "I'm here to help make your server even more amazing with fun commands and moderation tools!"
        ),
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )

    # Add a cute header field
    embed.add_field(
        name="💖 Getting Started",
        value="Let me show you how to configure me properly:",
        inline=False
    )

    # Basic Configuration
    embed.add_field(
        name="🔧 Basic Setup",
        value=(
            "`/slc <channel>` - Set server log channel\n"
            "`/sdlc <channel>` - Set deleted messages log channel"
        ),
        inline=False
    )

    # Welcome System
    embed.add_field(
        name="👋 Welcome New Members",
        value=(
            "`/swc <channel>` - Set welcome channel\n"
            "`/swm <message>` - Set welcome message *(supports {member.mention}, {member.name}, {guild.name})*"
        ),
        inline=False
    )

    # Autorole
    embed.add_field(
        name="🤖 Automatic Roles",
        value="`/autorole <role>` - Automatically assign a role to new members",
        inline=False
    )

    # Moderation
    embed.add_field(
        name="👮 Moderation Tools",
        value=(
            "`/kick <user>` - Remove a user from the server\n"
            "`/ban <user>` - Ban a user from the server\n"
            "`/mute <user>` - Temporarily silence a user\n"
            "`/warn <user>` - Give a user a warning"
        ),
        inline=False
    )

    # Fun Commands
    embed.add_field(
        name="🎭 Fun & Entertainment",
        value=(
            "`/ship <user1> <user2>` - Calculate compatibility between users\n"
            "`/howgay <user>` - Check someone's gay percentage\n"
            "`/simprate <user>` - See how much someone simps\n"
            "`/8ball <question>` - Ask the magic 8-ball\n"
            "`/rate <thing>` - Rate something 1-10 with stars"
        ),
        inline=False
    )

    # Giveaways
    embed.add_field(
        name="🎉 Giveaways",
        value=(
            "`/giveaway <duration> <prize>` - Create a new giveaway\n"
            "`/endgiveaway <message_id>` - End a giveaway early\n"
            "`/reroll <message_id>` - Reroll winners for a giveaway"
        ),
        inline=False
    )

    # Help Command
    embed.add_field(
        name="📚 Need More Help?",
        value=(
            "`/help` - See all my commands with a cute interactive menu\n\n"
            "💡 *Pro Tip: Most commands have detailed descriptions - just start typing `/` to see them!*"
        ),
        inline=False
    )

    # Footer with personality
    embed.set_footer(
        text="Made with ❤️",
        icon_url=guild.me.avatar.url if guild.me.avatar else None
    )

    # Try to add a cute thumbnail if the bot has an avatar
    if guild.me.avatar:
        embed.set_thumbnail(url=guild.me.avatar.url)

    try:
        await mod_channel.send(embed=embed)
        logger.info(f"Configuration guide sent to {mod_channel.name} in {guild.name}")
    except discord.Forbidden:
        logger.warning(f"Cannot send messages in {mod_channel.name} in {guild.name}")
    except Exception as e:
        logger.error(f"Error sending configuration guide to {guild.name}: {e}")

async def find_moderator_channel(guild):
    """Find a channel that's likely to be a moderator-only channel"""
    # Common names for moderator-only channels
    mod_channel_names = [
        'moderators', 'moderator-only', 'staff', 'admin',
        'admins', 'mod-channel', 'mod-chat', 'staff-chat',
        'moderators-only', 'admin-chat', 'bot-setup', 'configuration',
        'settings'
    ]

    # Look for exact name matches first
    for channel in guild.text_channels:
        if channel.name.lower() in mod_channel_names:
            # Check if we have permissions to send messages
            if channel.permissions_for(guild.me).send_messages:
                return channel

    # Check for partial name matches
    for channel in guild.text_channels:
        for name in mod_channel_names:
            if name in channel.name.lower():
                if channel.permissions_for(guild.me).send_messages:
                    return channel

    # Look for channels with "mod" in the name and restricted permissions
    for channel in guild.text_channels:
        if 'mod' in channel.name.lower() or 'staff' in channel.name.lower():
            # Check if this channel has restricted permissions (likely mod-only)
            permissions = channel.overwrites_for(guild.default_role)
            if permissions.send_messages is False or permissions.view_channel is False:
                if channel.permissions_for(guild.me).send_messages:
                    return channel

    # If we still haven't found anything, look for channels where @everyone
    # can't view or send messages (strong indicator of mod-only channels)
    for channel in guild.text_channels:
        permissions = channel.overwrites_for(guild.default_role)
        if (permissions.view_channel is False or
            permissions.send_messages is False or
            permissions.read_messages is False):
            if channel.permissions_for(guild.me).send_messages:
                return channel

    # No suitable channel found
    return None
