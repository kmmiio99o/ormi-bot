import discord
from discord import app_commands
from discord.ext import commands
import datetime
import re
import json
import os
from typing import Optional
from utils.permissions import has_higher_role
from utils.logger import get_logger
from config.config_manager import load_guild_config, save_guild_config

logger = get_logger(__name__)

class AdvancedModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Create warnings directory if it doesn't exist
        os.makedirs('data/warnings', exist_ok=True)

    def get_warnings_path(self, guild_id: int):
        """Get path to warnings file for a guild"""
        return f'data/warnings/{guild_id}.json'

    def load_warnings(self, guild_id: int):
        """Load warnings for a guild"""
        warnings_path = self.get_warnings_path(guild_id)
        if not os.path.exists(warnings_path):
            return {}
        try:
            with open(warnings_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.error(f"Error loading warnings for guild {guild_id}")
            return {}

    def save_warnings(self, guild_id: int, warnings: dict):
        """Save warnings for a guild"""
        warnings_path = self.get_warnings_path(guild_id)
        try:
            with open(warnings_path, 'w') as f:
                json.dump(warnings, f, indent=4)
            return True
        except IOError:
            logger.error(f"Error saving warnings for guild {guild_id}")
            return False

    def generate_case_id(self, guild_id: int):
        """Generate a unique case ID"""
        warnings = self.load_warnings(guild_id)
        case_id = 1
        while str(case_id) in warnings:
            case_id += 1
        return str(case_id)

    @app_commands.command(name="warn", description="Warns a user")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The user to warn", reason="Reason for the warning")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Not specified"):
        """Warns a user with case ID tracking"""
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't warn users with equal or higher role!",
                ephemeral=True
            )
        # Generate unique case ID
        case_id = self.generate_case_id(interaction.guild.id)
        # Create warning entry
        warning = {
            "case_id": case_id,
            "moderator_id": interaction.user.id,
            "reason": reason,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        # Load existing warnings
        warnings = self.load_warnings(interaction.guild.id)
        # Add warning to user's record
        if str(member.id) not in warnings:
            warnings[str(member.id)] = []
        warnings[str(member.id)].append(warning)
        # Save warnings
        if not self.save_warnings(interaction.guild.id, warnings):
            return await interaction.response.send_message(
                "❌ Failed to save warning. Please try again.",
                ephemeral=True
            )
        # Create embed for response
        embed = discord.Embed(
            title="⚠️ User Warned",
            description=f"{member.mention} has been warned!\n"
                        f"**Case ID:** `{case_id}`\n"
                        f"**Reason:** {reason}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        # Send warning to user via DM
        dm_embed = discord.Embed(
            title="⚠️ You've been warned",
            description=f"You have received a warning on **{interaction.guild.name}**",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        dm_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        dm_embed.add_field(name="Case ID", value=case_id, inline=True)
        dm_embed.set_footer(text=f"Server: {interaction.guild.name}")
        try:
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            # User has DMs disabled
            pass
        await interaction.response.send_message(embed=embed)
        logger.info(f"{interaction.user} warned {member} in {interaction.guild} (Case ID: {case_id}) for: {reason}")

    @app_commands.command(name="warnings", description="Shows a user's warnings")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The user to check warnings for")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        """Shows a user's warnings"""
        # Load warnings
        warnings = self.load_warnings(interaction.guild.id)
        # Check if user has warnings
        if str(member.id) not in warnings or not warnings[str(member.id)]:
            return await interaction.response.send_message(
                f"❌ {member.mention} has no warnings!",
                ephemeral=True
            )
        # Create embed
        embed = discord.Embed(
            title=f"⚠️ Warnings for {member.display_name}",
            description=f"{member.mention} has **{len(warnings[str(member.id)])}** warning{'s' if len(warnings[str(member.id)]) != 1 else ''}!",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        # Add warnings to embed (limit to 10 most recent)
        for i, warning in enumerate(warnings[str(member.id)][:10], 1):
            moderator = self.bot.get_user(warning['moderator_id'])
            moderator_mention = moderator.mention if moderator else f"<@{warning['moderator_id']}>"
            warning_time = datetime.datetime.fromisoformat(warning['timestamp'])
            time_str = discord.utils.format_dt(warning_time, 'R')
            embed.add_field(
                name=f"Case #{warning['case_id']}",
                value=f"**Moderator:** {moderator_mention}\n"
                      f"**Reason:** {warning['reason']}\n"
                      f"**When:** {time_str}",
                inline=False
            )
        # Add note if there are more than 10 warnings
        if len(warnings[str(member.id)]) > 10:
            embed.add_field(
                name="Note",
                value=f"And {len(warnings[str(member.id)]) - 10} more warnings...",
                inline=False
            )
        await interaction.response.send_message(embed=embed)
        logger.info(f"{interaction.user} checked warnings for {member} in {interaction.guild}")

    @app_commands.command(name="clearwarns", description="Clears a user's warnings")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The user to clear warnings for")
    async def clearwarns(self, interaction: discord.Interaction, member: discord.Member):
        """Clears a user's warnings"""
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't clear warnings for users with equal or higher role!",
                ephemeral=True
            )
        # Load warnings
        warnings = self.load_warnings(interaction.guild.id)
        # Check if user has warnings
        if str(member.id) not in warnings or not warnings[str(member.id)]:
            return await interaction.response.send_message(
                f"❌ {member.mention} has no warnings to clear!",
                ephemeral=True
            )
        # Clear warnings
        warnings[str(member.id)] = []
        # Save warnings
        if not self.save_warnings(interaction.guild.id, warnings):
            return await interaction.response.send_message(
                "❌ Failed to clear warnings. Please try again.",
                ephemeral=True
            )
        # Create embed
        embed = discord.Embed(
            title="✅ Warnings Cleared",
            description=f"Cleared all warnings for {member.mention}!",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        await interaction.response.send_message(embed=embed)
        logger.info(f"{interaction.user} cleared warnings for {member} in {interaction.guild}")

    @app_commands.command(name="delwarn", description="Deletes a specific warning")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(case_id="The case ID of the warning to delete")
    async def delwarn(self, interaction: discord.Interaction, case_id: str):
        """Deletes a specific warning"""
        # Load warnings
        warnings = self.load_warnings(interaction.guild.id)
        # Find and delete the warning
        warning_found = False
        for user_id, user_warnings in warnings.items():
            for i, warning in enumerate(user_warnings):
                if warning['case_id'] == case_id:
                    # Remove the warning
                    del warnings[user_id][i]
                    # If user has no warnings left, remove their entry
                    if not warnings[user_id]:
                        del warnings[user_id]
                    warning_found = True
                    break
            if warning_found:
                break
        if not warning_found:
            return await interaction.response.send_message(
                f"❌ Warning with case ID `{case_id}` not found!",
                ephemeral=True
            )
        # Save warnings
        if not self.save_warnings(interaction.guild.id, warnings):
            return await interaction.response.send_message(
                "❌ Failed to delete warning. Please try again.",
                ephemeral=True
            )
        # Create embed
        embed = discord.Embed(
            title="✅ Warning Deleted",
            description=f"Deleted warning with case ID: `{case_id}`",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        await interaction.response.send_message(embed=embed)
        logger.info(f"{interaction.user} deleted warning with case ID {case_id} in {interaction.guild}")

    @app_commands.command(name="case", description="Shows details about a specific warning")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(case_id="The case ID to get information about")
    async def case(self, interaction: discord.Interaction, case_id: str):
        """Shows details about a specific warning"""
        # Load warnings
        warnings = self.load_warnings(interaction.guild.id)
        # Find the warning
        warning_data = None
        target_user = None
        for user_id, user_warnings in warnings.items():
            for warning in user_warnings:
                if warning['case_id'] == case_id:
                    warning_data = warning
                    target_user = user_id
                    break
            if warning_data:
                break
        if not warning_data:
            return await interaction.response.send_message(
                f"❌ Warning with case ID `{case_id}` not found!",
                ephemeral=True
            )
        # Get user object
        try:
            user = await self.bot.fetch_user(int(target_user))
        except discord.NotFound:
            user = None
        # Create embed
        embed = discord.Embed(
            title=f"🔍 Case #{case_id}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        # Add user info if available
        if user:
            embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
            embed.add_field(name="User", value=user.mention, inline=True)
        # Get moderator
        moderator = self.bot.get_user(warning_data['moderator_id'])
        moderator_mention = moderator.mention if moderator else f"<@{warning_data['moderator_id']}>"
        embed.add_field(name="Moderator", value=moderator_mention, inline=True)
        # Add warning details
        warning_time = datetime.datetime.fromisoformat(warning_data['timestamp'])
        time_str = discord.utils.format_dt(warning_time, 'F')
        relative_time = discord.utils.format_dt(warning_time, 'R')
        embed.add_field(name="Date", value=f"{time_str} ({relative_time})", inline=False)
        embed.add_field(name="Reason", value=warning_data['reason'], inline=False)
        await interaction.response.send_message(embed=embed)
        logger.info(f"{interaction.user} checked case {case_id} in {interaction.guild}")

    @app_commands.command(name="editcase", description="Edits the reason for a specific warning")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(case_id="The case ID to edit", new_reason="The new reason for the warning")
    async def editcase(self, interaction: discord.Interaction, case_id: str, new_reason: str):
        """Edits the reason for a specific warning"""
        # Load warnings
        warnings = self.load_warnings(interaction.guild.id)
        # Find and update the warning
        warning_found = False
        for user_id, user_warnings in warnings.items():
            for warning in user_warnings:
                if warning['case_id'] == case_id:
                    warning['reason'] = new_reason
                    warning['edited_by'] = interaction.user.id
                    warning['edited_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    warning_found = True
                    break
            if warning_found:
                break
        if not warning_found:
            return await interaction.response.send_message(
                f"❌ Warning with case ID `{case_id}` not found!",
                ephemeral=True
            )
        # Save warnings
        if not self.save_warnings(interaction.guild.id, warnings):
            return await interaction.response.send_message(
                "❌ Failed to update warning. Please try again.",
                ephemeral=True
            )
        # Create embed
        embed = discord.Embed(
            title="✅ Warning Updated",
            description=f"Updated reason for warning with case ID: `{case_id}`",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="New Reason", value=new_reason, inline=False)
        await interaction.response.send_message(embed=embed)
        logger.info(f"{interaction.user} edited case {case_id} in {interaction.guild}")

    @app_commands.command(name="nuke", description="Deletes all messages in the channel and recreates it")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(reason="Reason for nuking the channel")
    async def nuke(self, interaction: discord.Interaction, reason: str = "Channel reset"):
        """Deletes all messages in the channel and recreates it"""
        channel = interaction.channel
        guild = interaction.guild
        # Create confirmation view
        class ConfirmNuke(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.value = None
            @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.value = True
                self.stop()
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.value = False
                self.stop()
        # Send confirmation message
        embed = discord.Embed(
            title="⚠️ Channel Nuke Confirmation",
            description="This will delete ALL messages in this channel and recreate it!\n"
                        "This action cannot be undone. Are you sure you want to proceed?",
            color=discord.Color.orange()
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        view = ConfirmNuke()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        # Wait for user response
        await view.wait()
        if view.value is None:
            return await interaction.followup.send(
                "❌ Nuke cancelled: Timeout reached",
                ephemeral=True
            )
        if not view.value:
            return await interaction.followup.send(
                "❌ Nuke cancelled: User declined",
                ephemeral=True
            )
        # Defer response to avoid timeout
        await interaction.followup.send(
            "🔄 Nuking channel... Please wait...",
            ephemeral=True
        )
        try:
            # Get channel position and category
            position = channel.position
            category = channel.category
            # Get channel permissions
            overwrites = channel.overwrites
            # Create new channel
            new_channel = await guild.create_text_channel(
                name=channel.name,
                topic=channel.topic,
                category=category,
                position=position,
                overwrites=overwrites,
                reason=reason
            )
            # Copy channel permissions
            await new_channel.edit(
                nsfw=channel.nsfw,
                slowmode_delay=channel.slowmode_delay
            )
            # Delete old channel
            await channel.delete(reason=reason)
            # Send success message in new channel
            success_embed = discord.Embed(
                title="💥 Channel Nuked!",
                description=f"This channel has been reset!\n"
                            f"**Reason:** {reason}\n"
                            f"**Moderator:** {interaction.user.mention}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await new_channel.send(embed=success_embed)
            logger.info(f"{interaction.user} nuked channel {channel} in {guild} for: {reason}")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to manage channels!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error nuking channel: {e}")
            await interaction.followup.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="fg", description="Toggles file and GIF sending permissions for a channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(channel="The channel to toggle permissions for (defaults to current channel)")
    async def fg(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        """Toggles file and GIF sending permissions for a channel"""
        target_channel = channel or interaction.channel
        # Get current permissions
        current_value = target_channel.permissions_for(interaction.guild.default_role).attach_files
        try:
            # Toggle permissions
            await target_channel.set_permissions(
                interaction.guild.default_role,
                attach_files=not current_value,
                external_emojis=not current_value
            )
            # Create embed
            status = "enabled" if not current_value else "disabled"
            embed = discord.Embed(
                title="✅ File & GIF Permissions Updated",
                description=f"File and GIF sending has been **{status}** for {target_channel.mention}!",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} toggled file/GIF permissions for {target_channel} in {interaction.guild} (Now: {status})")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to manage channel permissions!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error toggling FG permissions: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    # --- Existing commands from the original file ---
    @app_commands.command(name="unban", description="Unbans a user from the server")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(user_id="User ID to unban", reason="Reason for the unban")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "Not specified"):
        """Unbans a user from the server"""
        try:
            user = await self.bot.fetch_user(int(user_id))
        except (discord.NotFound, ValueError):
            return await interaction.response.send_message(
                "❌ User not found!",
                ephemeral=True
            )
        try:
            await interaction.guild.unban(user, reason=reason)
            embed = discord.Embed(
                title="🔓 User Unbanned",
                description=f"**User:** {user.mention}\n"
                            f"**Reason:** {reason}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} unbanned {user} from {interaction.guild} for: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to unban this user!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="softban", description="Bans and immediately unbans a user to delete their messages")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The user to softban", delete_days="Days of messages to delete (1-7)", reason="Reason for the softban")
    async def softban(self, interaction: discord.Interaction, member: discord.Member, delete_days: int = 1, reason: str = "Not specified"):
        """Bans and immediately unbans a user to delete their messages"""
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't softban users with equal or higher role!",
                ephemeral=True
            )
        if interaction.guild.me.top_role.position <= member.top_role.position:
            return await interaction.response.send_message(
                "❌ I don't have permissions to softban this user!",
                ephemeral=True
            )
        # Validate delete_days (must be between 1-7)
        if not 1 <= delete_days <= 7:
            return await interaction.response.send_message(
                "❌ Delete days must be between 1 and 7!",
                ephemeral=True
            )
        try:
            # Ban with delete_days parameter
            await interaction.guild.ban(
                member,
                reason=reason,
                delete_message_days=delete_days
            )
            # Immediately unban
            await interaction.guild.unban(member)
            embed = discord.Embed(
                title="🧹 User Softbanned",
                description=f"{member.mention} was softbanned!\n"
                            f"**Reason:** {reason}\n"
                            f"**Messages deleted:** {delete_days} day(s)",
                color=discord.Color.dark_gold(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} softbanned {member} from {interaction.guild} for: {reason} (Deleted {delete_days} days of messages)")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to softban this user!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error softbanning user: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="purge", description="Deletes a specified number of messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(amount="Number of messages to delete (1-100)", user="Only delete messages from this user")
    async def purge(self, interaction: discord.Interaction, amount: int, user: Optional[discord.Member] = None):
        """Deletes a specified number of messages"""
        if amount < 1 or amount > 100:
            return await interaction.response.send_message(
                "❌ You can only delete between 1 and 100 messages at once!",
                ephemeral=True
            )
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if user:
                def check(message):
                    return message.author == user
                deleted = await interaction.channel.purge(limit=amount, check=check)
            else:
                deleted = await interaction.channel.purge(limit=amount)
            embed = discord.Embed(
                title="🧹 Messages Purged",
                description=f"Deleted **{len(deleted)}** message{'s' if len(deleted) != 1 else ''}!",
                color=discord.Color.dark_purple(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.followup.send(embed=embed)
            logger.info(f"{interaction.user} purged {len(deleted)} messages in {interaction.channel} (Server: {interaction.guild})")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to delete messages in this channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error purging messages: {e}")
            await interaction.followup.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="lock", description="Locks the channel to prevent sending messages")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(reason="Reason for locking the channel")
    async def lock(self, interaction: discord.Interaction, reason: str = "Not specified"):
        """Locks the channel to prevent sending messages"""
        try:
            # Update permissions for @everyone role
            await interaction.channel.set_permissions(
                interaction.guild.default_role,
                send_messages=False
            )
            embed = discord.Embed(
                title="🔒 Channel Locked",
                description=f"This channel has been locked!\n"
                            f"**Reason:** {reason}",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} locked {interaction.channel} for: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to lock this channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error locking channel: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="unlock", description="Unlocks a previously locked channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(reason="Reason for unlocking the channel")
    async def unlock(self, interaction: discord.Interaction, reason: str = "Not specified"):
        """Unlocks a previously locked channel"""
        try:
            # Update permissions for @everyone role
            await interaction.channel.set_permissions(
                interaction.guild.default_role,
                send_messages=True
            )
            embed = discord.Embed(
                title="🔓 Channel Unlocked",
                description=f"This channel has been unlocked!\n"
                            f"**Reason:** {reason}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} unlocked {interaction.channel} for: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to unlock this channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error unlocking channel: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="slowmode", description="Sets slowmode for the channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(seconds="Slowmode delay in seconds (0-21600)")
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        """Sets slowmode for the channel"""
        if seconds < 0:
            return await interaction.response.send_message(
                "❌ Slowmode time can't be negative!",
                ephemeral=True
            )
        if seconds > 21600:  # Discord's max slowmode is 6 hours
            return await interaction.response.send_message(
                "❌ Slowmode time can't exceed 21600 seconds (6 hours)!",
                ephemeral=True
            )
        try:
            await interaction.channel.edit(slowmode_delay=seconds)
            # Format the time for display
            if seconds == 0:
                time_display = "disabled"
            elif seconds < 60:
                time_display = f"{seconds} second{'s' if seconds != 1 else ''}"
            elif seconds < 3600:
                time_display = f"{seconds // 60} minute{'s' if seconds // 60 != 1 else ''}"
            elif seconds < 86400:
                time_display = f"{seconds // 3600} hour{'s' if seconds // 3600 != 1 else ''}"
            else:
                time_display = f"{seconds // 86400} day{'s' if seconds // 86400 != 1 else ''}"
            embed = discord.Embed(
                title="🐌 Slowmode Updated",
                description=f"Slowmode set to **{time_display}**!",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} set slowmode to {seconds} seconds in {interaction.channel}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to set slowmode for this channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting slowmode: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="nick", description="Changes a user's nickname")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.describe(member="The user to change nickname for", nickname="New nickname (leave empty to reset)")
    async def nick(self, interaction: discord.Interaction, member: discord.Member, nickname: Optional[str] = None):
        """Changes a user's nickname"""
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't change nickname of a user with equal or higher role!",
                ephemeral=True
            )
        if interaction.guild.me.top_role.position <= member.top_role.position:
            return await interaction.response.send_message(
                "❌ I don't have permissions to change this user's nickname!",
                ephemeral=True
            )
        try:
            await member.edit(nick=nickname)
            if nickname:
                embed = discord.Embed(
                    title="✏️ Nickname Changed",
                    description=f"Changed {member.mention}'s nickname to `{nickname}`!",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
            else:
                embed = discord.Embed(
                    title="✏️ Nickname Reset",
                    description=f"Reset {member.mention}'s nickname!",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} changed {member}'s nickname to {nickname or 'default'}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to change this user's nickname!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error changing nickname: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="prune", description="Removes inactive members from the server")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(days="Number of days of inactivity (1-90)", role="Only prune members without this role")
    async def prune(self, interaction: discord.Interaction, days: int, role: Optional[discord.Role] = None):
        """Removes inactive members from the server"""
        if days < 1 or days > 90:
            return await interaction.response.send_message(
                "❌ Inactive days must be between 1 and 90!",
                ephemeral=True
            )
        await interaction.response.defer(thinking=True)
        # Get members to prune
        try:
            count = await interaction.guild.prune_members(
                days=days,
                compute_prune_count=True,
                roles=[role] if role else None
            )
            if count == 0:
                return await interaction.followup.send(
                    "❌ No inactive members found to prune!"
                )
            embed = discord.Embed(
                title="🧹 Members Pruned",
                description=f"Removed **{count}** inactive member{'s' if count != 1 else ''} "
                            f"who haven't been active for {days} day{'s' if days != 1 else ''}!",
                color=discord.Color.dark_red(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.followup.send(embed=embed)
            logger.info(f"{interaction.user} pruned {count} inactive members (inactive for {days} days) from {interaction.guild}")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to prune members!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error pruning members: {e}")
            await interaction.followup.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="clearinvites", description="Clears all server invites")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(reason="Reason for clearing invites")
    async def clearinvites(self, interaction: discord.Interaction, reason: str = "Not specified"):
        """Clears all server invites"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            # Get all invites
            invites = await interaction.guild.invites()
            # Delete each invite
            deleted_count = 0
            for invite in invites:
                await invite.delete(reason=reason)
                deleted_count += 1
            embed = discord.Embed(
                title="🧹 Invites Cleared",
                description=f"Deleted **{deleted_count}** server invite{'s' if deleted_count != 1 else ''}!",
                color=discord.Color.dark_purple(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.followup.send(embed=embed)
            logger.info(f"{interaction.user} cleared {deleted_count} invites from {interaction.guild} for: {reason}")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to manage server invites!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error clearing invites: {e}")
            await interaction.followup.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="audit", description="Shows recent audit log entries")
    @app_commands.checks.has_permissions(view_audit_log=True)
    @app_commands.describe(limit="Number of entries to show (1-100)")
    async def audit(self, interaction: discord.Interaction, limit: int = 5):
        """Shows recent audit log entries"""
        if limit < 1:
            limit = 1
        elif limit > 100:
            limit = 100
        try:
            # Fetch audit log entries
            audit_log = []
            async for entry in interaction.guild.audit_logs(limit=limit):
                audit_log.append(entry)
            if not audit_log:
                return await interaction.response.send_message(
                    "❌ No audit log entries found!",
                    ephemeral=True
                )
            # Create embed
            embed = discord.Embed(
                title="📜 Audit Log",
                description=f"Showing the last {len(audit_log)} entries:",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            # Add entries to embed
            for entry in audit_log:
                target = entry.target
                target_str = str(target) if target else "N/A"
                # Format the entry
                entry_str = f"**Action:** {entry.action.name}\n" \
                            f"**Moderator:** {entry.user.mention}\n" \
                            f"**Target:** {target_str}\n" \
                            f"**Reason:** {entry.reason or 'Not specified'}\n" \
                            f"**When:** {discord.utils.format_dt(entry.created_at, 'R')}"
                embed.add_field(
                    name=f"Entry #{entry.id}",
                    value=entry_str,
                    inline=False
                )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} viewed audit log ({limit} entries) for {interaction.guild}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to view the audit log!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error fetching audit log: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="voicekick", description="Kicks a user from voice channel")
    @app_commands.checks.has_permissions(move_members=True)
    @app_commands.describe(member="The user to kick from voice channel", reason="Reason for the voice kick")
    async def voicekick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Not specified"):
        """Kicks a user from voice channel"""
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't voice kick users with equal or higher role!",
                ephemeral=True
            )
        if not member.voice:
            return await interaction.response.send_message(
                f"❌ {member.mention} is not in a voice channel!",
                ephemeral=True
            )
        try:
            await member.move_to(None)
            embed = discord.Embed(
                title="🔊 Voice Kicked",
                description=f"{member.mention} was kicked from voice channel!\n"
                            f"**Reason:** {reason}",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} voice kicked {member} from {interaction.guild} for: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to move this user!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error voice kicking user: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="voiceban", description="Prevents a user from joining voice channels")
    @app_commands.checks.has_permissions(mute_members=True)
    @app_commands.describe(member="The user to voice ban", reason="Reason for the voice ban")
    async def voiceban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Not specified"):
        """Prevents a user from joining voice channels"""
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't voice ban users with equal or higher role!",
                ephemeral=True
            )
        try:
            # Deny voice permissions for all voice channels
            for channel in interaction.guild.voice_channels:
                await channel.set_permissions(
                    member,
                    connect=False,
                    speak=False,
                    reason=reason
                )
            embed = discord.Embed(
                title="🔇 Voice Banned",
                description=f"{member.mention} can no longer join voice channels!\n"
                            f"**Reason:** {reason}",
                color=discord.Color.dark_red(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} voice banned {member} from {interaction.guild} for: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to set voice permissions!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error voice banning user: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="voiceunban", description="Allows a user to join voice channels again")
    @app_commands.checks.has_permissions(mute_members=True)
    @app_commands.describe(member="The user to voice unban", reason="Reason for the voice unban")
    async def voiceunban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Not specified"):
        """Allows a user to join voice channels again"""
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't voice unban users with equal or higher role!",
                ephemeral=True
            )
        try:
            # Reset voice permissions for all voice channels
            for channel in interaction.guild.voice_channels:
                # Check if there's an override for this member
                overwrite = channel.overwrites_for(member)
                if overwrite.connect is False or overwrite.speak is False:
                    await channel.set_permissions(
                        member,
                        overwrite=None,
                        reason=reason
                    )
            embed = discord.Embed(
                title="🔊 Voice Unbanned",
                description=f"{member.mention} can now join voice channels!\n"
                            f"**Reason:** {reason}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} voice unbanned {member} from {interaction.guild} for: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to set voice permissions!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error voice unbanning user: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="massban", description="Bans multiple users at once")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(user_ids="Space-separated list of user IDs to ban", reason="Reason for the bans")
    async def massban(self, interaction: discord.Interaction, user_ids: str, reason: str = "Not specified"):
        """Bans multiple users at once"""
        # Split the user IDs and validate
        ids = [id.strip() for id in user_ids.split() if id.strip()]
        if not ids:
            return await interaction.response.send_message(
                "❌ Please provide at least one valid user ID!",
                ephemeral=True
            )
        # Validate all IDs are numeric
        for user_id in ids:
            if not user_id.isdigit():
                return await interaction.response.send_message(
                    f"❌ Invalid user ID: {user_id}",
                    ephemeral=True
                )
        await interaction.response.defer(ephemeral=True, thinking=True)
        success_count = 0
        error_messages = []
        for user_id in ids:
            try:
                user = await self.bot.fetch_user(int(user_id))
                # Check if user is already banned
                try:
                    await interaction.guild.fetch_ban(user)
                    error_messages.append(f"⚠️ {user} is already banned")
                    continue
                except discord.NotFound:
                    pass
                await interaction.guild.ban(user, reason=reason)
                success_count += 1
            except discord.NotFound:
                error_messages.append(f"❌ User with ID {user_id} not found")
            except discord.Forbidden:
                error_messages.append(f"❌ Missing permissions to ban {user_id}")
            except Exception as e:
                error_messages.append(f"❌ Error banning {user_id}: {str(e)}")
        # Prepare response
        embed = discord.Embed(
            title="🔨 Mass Ban Results",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(
            name="Summary",
            value=f"Successfully banned: **{success_count}** user{'s' if success_count != 1 else ''}\n"
                  f"Failed: **{len(ids) - success_count}**",
            inline=False
        )
        if error_messages:
            error_text = "\n".join(error_messages[:5])  # Show up to 5 errors
            if len(error_messages) > 5:
                error_text += f"\nAnd {len(error_messages) - 5} more errors..."
            embed.add_field(
                name="Errors",
                value=error_text,
                inline=False
            )
        await interaction.followup.send(embed=embed)
        logger.info(f"{interaction.user} massbanned {success_count} users from {interaction.guild} (total attempted: {len(ids)})")

    @app_commands.command(name="kick", description="Kicks a user from the server")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The user to kick", reason="Reason for the kick")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Not specified"):
        """Kicks a user from the server"""
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't kick users with equal or higher role!",
                ephemeral=True
            )
        if interaction.guild.me.top_role.position <= member.top_role.position:
            return await interaction.response.send_message(
                "❌ I don't have permissions to kick this user!",
                ephemeral=True
            )
        try:
            await member.kick(reason=reason)
            # Create embed for response
            embed = discord.Embed(
                title="👢 User Kicked",
                description=f"{member.mention} was kicked!\n"
                            f"**Reason:** {reason}",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            # Log the action
            logger.info(f"{interaction.user} kicked {member} from {interaction.guild} for: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to kick this user!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error kicking user: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="ban", description="Bans a user from the server")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The user to ban", reason="Reason for the ban")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Not specified"):
        """Bans a user from the server"""
        # Check role hierarchy
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't ban users with equal or higher role!",
                ephemeral=True
            )
        # Check bot's permissions relative to the target user
        if interaction.guild.me.top_role.position <= member.top_role.position:
            return await interaction.response.send_message(
                "❌ I don't have permissions to ban this user!",
                ephemeral=True
            )

        try:
            # --- THE CRITICAL FIX: Actually ban the user ---
            await member.ban(reason=reason, delete_message_days=0) # You can adjust delete_message_days (0-7) if needed

            # Create embed for response
            embed = discord.Embed(
                title="🔨 User Banned",
                description=f"**User:** {member.mention}\n"
                            f"**Reason:** {reason}",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            # Log the action
            logger.info(f"{interaction.user} banned {member} from {interaction.guild} for: {reason}")

        except discord.Forbidden:
            # This handles cases where the bot *itself* lacks permission, even if the user has the right perms
            await interaction.response.send_message(
                "❌ I don't have permission to ban this user!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error banning user {member} (ID: {member.id}): {e}")
            await interaction.response.send_message(
                f"❌ An error occurred while trying to ban {member.mention}. Please try again.",
                ephemeral=True
            )

    @app_commands.command(name="mute", description="Mutes a user for a specified time")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="The user to mute", duration="Duration (e.g., 30m, 2h)", reason="Reason for the mute")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str = "30m", reason: str = "Not specified"):
        """Mutes a user for a specified time"""
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't mute users with equal or higher role!",
                ephemeral=True
            )
        if interaction.guild.me.top_role.position <= member.top_role.position:
            return await interaction.response.send_message(
                "❌ I don't have permissions to mute this user!",
                ephemeral=True
            )
        try:
            # Handle duration
            if duration.lower() == "perm":
                timeout = None
                mute_duration = "Permanent mute"
            else:
                try:
                    time_value = int(duration[:-1])
                    time_unit = duration[-1].lower()
                    if time_unit == 'm':
                        timeout = datetime.timedelta(minutes=time_value)
                        mute_duration = f"{time_value} minute(s)"
                    elif time_unit == 'h':
                        timeout = datetime.timedelta(hours=time_value)
                        mute_duration = f"{time_value} hour(s)"
                    elif time_unit == 'd':
                        timeout = datetime.timedelta(days=time_value)
                        mute_duration = f"{time_value} day(s)"
                    else:
                        return await interaction.response.send_message(
                            "❌ Invalid time format! Use m (minutes), h (hours), or d (days).",
                            ephemeral=True
                        )
                except (ValueError, IndexError):
                    return await interaction.response.send_message(
                        "❌ Invalid time format!",
                        ephemeral=True
                    )
            await member.timeout(timeout, reason=reason)
            embed = discord.Embed(
                title="🔇 User Muted",
                description=f"{member.mention} has been muted for **{mute_duration}**\n"
                            f"**Reason:** {reason}",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} muted {member} for {mute_duration} in {interaction.guild} for: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to mute this user!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error muting user: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="unmute", description="Unmutes a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="The user to unmute")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        """Unmutes a user"""
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't unmute users with equal or higher role!",
                ephemeral=True
            )
        try:
            await member.timeout(None, reason="Unmuted by command")
            embed = discord.Embed(
                title="🔊 User Unmuted",
                description=f"{member.mention} has been unmuted.",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} unmuted {member} in {interaction.guild}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to unmute this user!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error unmuting user: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="hierarchy", description="Shows server power hierarchy")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def hierarchy(self, interaction: discord.Interaction):
        """Shows server power hierarchy"""
        members = sorted(
            [m for m in interaction.guild.members if not m.bot],
            key=lambda m: (-m.top_role.position, m.joined_at)
        )[:10]
        embed = discord.Embed(
            title="👑 Server Power Hierarchy",
            description="Ranked by role position and join date:",
            color=0xFFD700,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
        for i, member in enumerate(members):
            embed.add_field(
                name=f"{medals[i]} {member.display_name}",
                value=f"Role: {member.top_role.mention}\n"
                      f"Joined: {discord.utils.format_dt(member.joined_at, 'R')}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    # --- Error Handler for Permission Checks ---
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """Handles errors for app commands within this cog."""
        # Handle Missing Permissions
        if isinstance(error, app_commands.MissingPermissions):
            # Map permission names to user-friendly descriptions
            missing_perms = error.missing_permissions
            perm_descriptions = {
                "kick_members": "Kick Members",
                "ban_members": "Ban Members",
                "manage_channels": "Manage Channels",
                "manage_messages": "Manage Messages",
                "manage_nicknames": "Manage Nicknames",
                "manage_roles": "Manage Roles",
                "moderate_members": "Moderate Members", # For timeout/mute
                "view_audit_log": "View Audit Log",
                "move_members": "Move Members", # For voice kick
                "mute_members": "Mute Members", # For voice ban/unban
                "manage_guild": "Manage Server", # For clearinvites
                "manage_webhooks": "Manage Webhooks", # If you add commands needing this
                # Add more mappings if you use other specific permissions
            }

            # Create a list of user-friendly permission names
            friendly_perms = [perm_descriptions.get(perm, perm.replace('_', ' ').title()) for perm in missing_perms]

            embed = discord.Embed(
                title="❌ Insufficient Permissions",
                description=f"You are missing the following permissions to use this command:\n"
                            f"{', '.join(f'`{perm}`' for perm in friendly_perms)}",
                color=discord.Color.red()
            )
            # Try to send an ephemeral message if the interaction hasn't been responded to yet
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    # If the interaction was already responded to (e.g., deferred), send a followup
                     await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                 # Fallback if sending the embed also fails
                 pass # Or log the error if needed
            return # Stop further error handling for this specific error type

        # Handle other specific errors if needed (e.g., CheckFailure for custom checks like has_higher_role)
        # You can add elif blocks for other error types here

        # --- Optional: Log unhandled errors ---
        # This is useful for debugging unexpected issues
        # logger.error(f"Unhandled app command error in {interaction.command.name} for {interaction.user} in {interaction.guild}: {error}", exc_info=True)
        # --- Optional End ---

        # For any other unhandled errors, you might choose to let the default Discord behavior happen
        # or send a generic error message. The following lines handle sending a generic message.
        generic_error_msg = "❌ An unexpected error occurred while processing your command."
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(generic_error_msg, ephemeral=True)
            else:
                 await interaction.followup.send(generic_error_msg, ephemeral=True)
        except:
            pass # Silent fail if we can't even send the generic error


# --- FIXED SETUP FUNCTION ---
# This is the key fix: Remove the problematic line
async def setup(bot):
    await bot.add_cog(AdvancedModerationCog(bot))
# --- END FIXED SETUP FUNCTION ---
