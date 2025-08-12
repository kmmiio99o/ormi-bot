import discord
from discord import app_commands
from discord.ext import commands
import datetime

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="userinfo", description="Shows information about a user")
    @app_commands.describe(member="The user to get information about")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        """Shows information about a user"""
        member = member or interaction.user

        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        role_count = len(roles)

        embed = discord.Embed(
            title=f"Info about {member.display_name} UwU~",
            color=member.color,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)

        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Nickname", value=member.display_name, inline=True)
        embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, 'R'), inline=True)
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, 'R'), inline=True)

        if roles:
            roles_text = ", ".join(roles[-5:])
            if role_count > 5:
                roles_text += f" and {role_count - 5} more..."
            embed.add_field(name=f"Roles [{role_count}]", value=roles_text, inline=False)

        embed.add_field(name="Status", value=str(member.status).title(), inline=True)

        if member.activity:
            if isinstance(member.activity, discord.Game):
                embed.add_field(name="Playing", value=member.activity.name, inline=True)
            elif isinstance(member.activity, discord.Streaming):
                embed.add_field(name="Streaming", value=f"[{member.activity.name}]({member.activity.url})", inline=True)
            elif isinstance(member.activity, discord.Spotify):
                embed.add_field(name="Listening to", value=f"Spotify: [{member.activity.title} by {member.activity.artist}](https://open.spotify.com/track/{member.activity.track_id})", inline=True)
            # Handle other activity types like CustomActivity if needed

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Displays server statistics")
    async def serverinfo(self, interaction: discord.Interaction):
        """Shows server information"""
        guild = interaction.guild

        # Basic server info
        embed = discord.Embed(
            title=f"Information about {guild.name}",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="ID", value=guild.id, inline=True)
        if guild.owner:
            embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="Created At", value=discord.utils.format_dt(guild.created_at, 'F'), inline=True)

        # Member counts
        total_members = guild.member_count
        bots = sum(1 for m in guild.members if m.bot)
        humans = total_members - bots
        embed.add_field(name="Members", value=f"{total_members} ( Humans: {humans} | Bots: {bots} )", inline=True)

        # Channel counts
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        embed.add_field(name="Channels", value=f"Total: {text_channels + voice_channels} ( Text: {text_channels} | Voice: {voice_channels} | Categories: {categories} )", inline=True)

        # Counts for roles, emojis, stickers
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="Emojis", value=f"{len(guild.emojis)}/{guild.emoji_limit}", inline=True)
        embed.add_field(name="Stickers", value=len(guild.stickers), inline=True)

        # Boost info
        embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier}", inline=True)
        embed.add_field(name="Boosts", value=guild.premium_subscription_count, inline=True)

        # Features (show a few key ones or limit the list)
        if guild.features:
             # Show a few common/interesting features
             key_features = [f for f in guild.features if f in ['COMMUNITY', 'VERIFIED', 'PARTNERED', 'VANITY_URL', 'INVITE_SPLASH', 'ANIMATED_ICON', 'BANNER']]
             if key_features:
                 embed.add_field(name="Key Features", value=", ".join(key_features), inline=False)

        if guild.description:
            embed.add_field(name="Description", value=guild.description, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Shows user avatar")
    @app_commands.describe(member="The user whose avatar to show")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        """Shows user avatar"""
        target_member = member or interaction.user

        if not target_member.avatar:
            return await interaction.response.send_message(
                f"{target_member.mention} doesn't have an avatar set.",
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"{target_member.display_name}'s Avatar",
            color=target_member.color
        )
        embed.set_image(url=target_member.avatar.url)
        # Add a field with the direct link
        embed.add_field(name="Direct Link", value=f"[Click here]({target_member.avatar.url})", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roleinfo", description="Shows information about a role")
    @app_commands.describe(role="The role to get information about")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Shows information about a role"""
        # Calculate permissions
        permissions = []
        for perm, value in role.permissions:
            if value:
                # Convert permission name to readable format
                perm_name = perm.replace('_', ' ').title()
                permissions.append(perm_name)

        # Create embed
        embed = discord.Embed(
            title=f"Info about @{role.name}",
            color=role.color,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        embed.add_field(name="ID", value=role.id, inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Position", value=f"{role.position} (of {len(interaction.guild.roles)-1})", inline=True) # -1 for @everyone
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Managed", value="Yes" if role.managed else "No", inline=True)

        # Add member count
        member_count = len(role.members)
        embed.add_field(name="Members", value=member_count, inline=True)

        # Add permissions if they exist
        if permissions:
            # Limit permissions shown to avoid overly long embeds
            perms_text = ", ".join(permissions[:15])
            if len(permissions) > 15:
                perms_text += f" and {len(permissions) - 15} more..."
            embed.add_field(name="Permissions", value=perms_text, inline=False)
        else:
            embed.add_field(name="Permissions", value="None", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Shows bot latency")
    async def ping(self, interaction: discord.Interaction):
        """Shows bot latency"""
        latency = round(self.bot.latency * 1000)  # Convert to milliseconds

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: **{latency}ms**",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="emojiinfo", description="Shows emoji information (ID, creation date)")
    @app_commands.describe(emoji="The emoji to get information about (e.g., 😀 or :my_emoji:)")
    async def emojiinfo(self, interaction: discord.Interaction, emoji: str):
        """Shows emoji information"""

        # Try to convert the string input to a PartialEmoji or handle as Unicode
        try:
            # Attempt to convert if it's a custom emoji string like <:name:id> or <a:name:id>
            partial_emoji = discord.PartialEmoji.from_str(emoji)
            if partial_emoji.is_unicode_emoji():
                 # It's a unicode emoji passed as a string directly
                 # from_str might not correctly parse pure unicode strings in all cases,
                 # so we handle it directly if the original input is just the emoji character.
                 # Let's re-check the original input.
                 # If emoji is a single unicode char or a standard emoji sequence, treat it as such.
                 # A simple check: if it doesn't look like <...> and isn't just whitespace/empty
                 if not emoji.startswith('<') and not emoji.endswith('>') and emoji.strip():
                      # Treat as unicode emoji
                      name = emoji # Unicode emojis don't have a distinct 'name' in this context
                      emoji_id = None
                      animated = False
                      url = None
                      is_unicode = True
                 else:
                      raise ValueError("Could not parse as custom emoji")
            else:
                # It's a custom emoji successfully parsed by from_str
                name = partial_emoji.name
                emoji_id = partial_emoji.id
                animated = partial_emoji.animated
                url = partial_emoji.url
                is_unicode = False
        except (TypeError, ValueError):
            # If from_str fails or it's determined to be unicode
            # Check if the input itself looks like a unicode emoji string
            if emoji and not (emoji.startswith('<') and emoji.endswith('>')):
                name = emoji
                emoji_id = None
                animated = False
                url = None
                is_unicode = True
            else:
                await interaction.response.send_message(
                    "❌ Please provide a valid emoji (e.g., `😀` or `:my_custom_emoji:`).",
                    ephemeral=True
                )
                return

        embed = discord.Embed(
            title=f"Info about {name}",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        if is_unicode:
            embed.add_field(name="Type", value="Standard Unicode Emoji", inline=False)
            embed.add_field(name="Representation", value=name, inline=False)
            # Optionally, you could try to find a name for common unicode emojis using external libraries
            # or a predefined mapping, but it's complex. For now, just show the emoji itself.
        else: # Custom emoji
            embed.set_thumbnail(url=url)
            embed.add_field(name="ID", value=emoji_id, inline=True)
            embed.add_field(name="Animated", value="Yes" if animated else "No", inline=True)
            # Emojis don't have a direct 'created_at', but their ID contains a timestamp
            if emoji_id:
                try:
                    emoji_created_at = discord.utils.snowflake_time(emoji_id)
                    embed.add_field(name="Created At", value=discord.utils.format_dt(emoji_created_at, 'F'), inline=True)
                except (ValueError, TypeError):
                    # Shouldn't happen with valid snowflakes, but good to be safe
                    pass
            embed.add_field(name="Direct Link", value=f"[Click here]({url})", inline=False)
            # Note: Getting the specific guild requires iterating through bot.guilds or having a more complex lookup,
            # and the bot needs to share a guild with the emoji.

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="uptime", description="Shows how long the bot has been online")
    async def uptime(self, interaction: discord.Interaction):
        """Shows how long the bot has been online"""
        # This assumes you have a self.bot.start_time attribute set when the bot starts
        # e.g., in your main bot file: self.start_time = discord.utils.utcnow()
        try:
            uptime_delta = discord.utils.utcnow() - self.bot.start_time
            days = uptime_delta.days
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            uptime_string = f"{days}d {hours}h {minutes}m {seconds}s"

            embed = discord.Embed(
                title="⏱️ Bot Uptime",
                description=f"The bot has been online for **{uptime_string}**",
                color=discord.Color.green()
            )
        except AttributeError:
            # Fallback if start_time is not set
            embed = discord.Embed(
                title="⏱️ Bot Uptime",
                description="Uptime information is not available.",
                color=discord.Color.red()
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="recentjoins", description="Shows recently joined members (last 10)")
    async def recentjoins(self, interaction: discord.Interaction):
        """Shows recently joined members"""
        # Get members sorted by join date (newest first)
        members = sorted(
            [m for m in interaction.guild.members if not m.bot], # Filter out bots if desired, or remove the filter
            key=lambda m: m.joined_at,
            reverse=True
        )[:10] # Get last 10

        if not members:
             return await interaction.response.send_message("No recent members found.", ephemeral=True)

        embed = discord.Embed(
            title="👥 Recently Joined Members",
            description="Last 10 members to join the server:",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        for i, member in enumerate(members, 1):
            # You can format this differently if you want
            embed.add_field(
                name=f"{i}. {member.display_name}",
                value=f"Joined: {discord.utils.format_dt(member.joined_at, 'R')}\n"
                      f"Account created: {discord.utils.format_dt(member.created_at, 'R')}",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))
