import discord
from discord import app_commands
from discord.ext import commands
from config.config_manager import load_guild_config, save_guild_config
import logging
import asyncio
import datetime

logger = logging.getLogger(__name__)

class SLCLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="slc", description="Sets the server log channel")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="The channel to set as the server log channel")
    async def set_server_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Sets the server-wide activity log channel in the server's config file"""
        guild_id = interaction.guild.id
        config = load_guild_config(guild_id)

        config['log_channel_id'] = str(channel.id)
        save_guild_config(guild_id, config)

        embed = discord.Embed(
            title="✅ Server Log Channel Set",
            description=f"Server activity log channel has been set to {channel.mention}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="What now?",
            value="All server activities, including audit log events, will be logged in this channel.",
            inline=False
        )
        embed.set_footer(text="Configuration Updated")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"{interaction.user} set server log channel to {channel.id} in {interaction.guild.name}")

        try:
            test_embed = discord.Embed(
                title="📝 Server Log Channel Active",
                description="This channel has been set as the server log channel.\nAll major server activities will be logged here.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            test_embed.set_footer(text="Configuration Test")
            await channel.send(embed=test_embed)
        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ Note: I don't have permission to send messages in that channel. "
                "Please make sure I have the proper permissions to log events there.",
                ephemeral=True
            )

    async def send_log_embed(self, guild_id: int, embed: discord.Embed):
        """Helper to send embeds to the configured log channel."""
        config = load_guild_config(guild_id)
        log_channel_id = config.get('log_channel_id')

        if log_channel_id:
            log_channel = self.bot.get_channel(int(log_channel_id))
            if log_channel:
                try:
                    await log_channel.send(embed=embed)
                except discord.Forbidden:
                    logger.warning(f"Bot does not have permissions to send messages in log channel {log_channel_id} for guild {guild_id}.")
                except Exception as e:
                    logger.error(f"Error sending log embed: {e}", exc_info=True)
            else:
                logger.warning(f"Server log channel with ID {log_channel_id} not found for guild {guild_id}.")

    async def _get_audit_log_entry(self, guild: discord.Guild, action_type: discord.AuditLogAction, target_id: int = None, entries_limit=5):
        """
        Helper to fetch a recent audit log entry for a specific action and target.
        Adds a small delay to allow audit logs to propagate.
        """
        await asyncio.sleep(0.5) # Give audit log a moment to update

        try:
            async for entry in guild.audit_logs(limit=entries_limit, action=action_type):
                # Check if the entry is recent enough (within a few seconds)
                # Discord audit logs can sometimes be slightly delayed
                if (discord.utils.utcnow() - entry.created_at).total_seconds() < 10: # Adjust timeout as needed
                    # If a target_id is provided, check if the entry's target matches
                    if target_id is not None:
                        if entry.target and entry.target.id == target_id:
                            return entry
                    else:
                        # If no target_id, return the first recent entry of this action type
                        return entry
            return None
        except discord.Forbidden:
            logger.warning(f"Bot does not have permissions to read audit logs in guild {guild.name} ({guild.id}).")
            return None
        except Exception as e:
            logger.error(f"Error fetching audit log entry for action {action_type} in guild {guild.id}: {e}", exc_info=True)
            return None

    # --- Audit Log Event Listeners ---

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot or not member.guild:
            return

        embed = discord.Embed(
            title="📥 Member Joined",
            description=f"{member.mention} has joined the server.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Member ID", value=member.id, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member: {member.name}#{member.discriminator}")
        await self.send_log_embed(member.guild.id, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot or not member.guild:
            return

        embed = discord.Embed(
            title="📤 Member Left",
            description=f"{member.mention} has left the server.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Member ID", value=member.id, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)

        actor_info = "Self-removed or unknown"
        footer_info = f"Member: {member.name}#{member.discriminator} | ID: {member.id}"

        kick_entry = await self._get_audit_log_entry(member.guild, discord.AuditLogAction.kick, member.id)
        ban_entry = await self._get_audit_log_entry(member.guild, discord.AuditLogAction.ban, member.id)

        if kick_entry and kick_entry.user:
            actor_info = f"{kick_entry.user.mention} (`{kick_entry.user.id}`)"
            embed.description = f"{member.mention} was **kicked** from the server."
            embed.color = discord.Color.orange()
            if kick_entry.reason:
                embed.add_field(name="Reason", value=kick_entry.reason, inline=False)
            footer_info += f" | Kicked By: {kick_entry.user} | ID: {kick_entry.user.id}"
        elif ban_entry and ban_entry.user:
            actor_info = f"{ban_entry.user.mention} (`{ban_entry.user.id}`)"
            embed.description = f"{member.mention} was **banned** from the server."
            embed.color = discord.Color.dark_red()
            if ban_entry.reason:
                embed.add_field(name="Reason", value=ban_entry.reason, inline=False)
            footer_info += f" | Banned By: {ban_entry.user} | ID: {ban_entry.user.id}"

        embed.add_field(name="Performed By", value=actor_info, inline=True)
        embed.set_footer(text=footer_info)
        await self.send_log_embed(member.guild.id, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.bot or not before.guild:
            return

        guild_id = before.guild.id
        embed = discord.Embed(
            title="👥 Member Updated",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Member ID: {after.id}")

        changes = []
        actor_info = ""
        performed_by = ""

        # Nickname Change
        if before.nick != after.nick:
            changes.append(f"**Nickname**: `{before.nick}` -> `{after.nick}`")
            entry = await self._get_audit_log_entry(after.guild, discord.AuditLogAction.member_update, after.id)
            if entry and entry.user:
                performed_by = f"\nPerformed by: {entry.user.mention} (`{entry.user.id}`)"

        # Role Changes
        if before.roles != after.roles:
            added_roles = set(after.roles) - set(before.roles)
            removed_roles = set(before.roles) - set(after.roles)

            if added_roles:
                changes.append(f"**Roles Added**: {', '.join([r.mention for r in added_roles])}")
            if removed_roles:
                changes.append(f"**Roles Removed**: {', '.join([r.mention for r in removed_roles])}")

            # Try to find who changed the roles (member_role_update)
            entry = await self._get_audit_log_entry(after.guild, discord.AuditLogAction.member_role_update, after.id)
            if entry and entry.user:
                performed_by = f"\nPerformed by: {entry.user.mention} (`{entry.user.id}`)"

        if changes:
            embed.description = f"Changes for {after.mention}:\n" + "\n".join(changes) + performed_by
            await self.send_log_embed(guild_id, embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)) or not channel.guild:
            return

        embed = discord.Embed(
            title="➕ Channel Created",
            description=f"Channel {channel.mention} has been created.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Name", value=channel.name, inline=True)
        embed.add_field(name="Type", value=str(channel.type).replace('channel_type.','').replace('_', ' ').title(), inline=True)
        if channel.category:
            embed.add_field(name="Category", value=channel.category.name, inline=True)
        embed.add_field(name="Channel ID", value=channel.id, inline=True)

        actor_info = "Unknown"
        entry = await self._get_audit_log_entry(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        if entry and entry.user:
            actor_info = f"\nPerformed By: {entry.user.mention} (`{entry.user.id}`)"
            if entry.reason:
                embed.add_field(name="Reason", value=entry.reason, inline=False)

        embed.description = f"{embed.description}{actor_info}"
        await self.send_log_embed(channel.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)) or not channel.guild:
            return

        embed = discord.Embed(
            title="➖ Channel Deleted",
            description=f"Channel `#{channel.name}` has been deleted.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Name", value=channel.name, inline=True)
        embed.add_field(name="Type", value=str(channel.type).replace('channel_type.','').replace('_', ' ').title(), inline=True)
        if channel.category:
            embed.add_field(name="Category", value=channel.category.name, inline=True)
        embed.add_field(name="Channel ID", value=channel.id, inline=True)

        actor_info = "Unknown"
        # For channel delete, the target in audit log is the channel itself
        entry = await self._get_audit_log_entry(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        if entry and entry.user:
            actor_info = f"\nPerformed By: {entry.user.mention} (`{entry.user.id}`)"
            if entry.reason:
                embed.add_field(name="Reason", value=entry.reason, inline=False)

        embed.description = f"{embed.description}{actor_info}"
        await self.send_log_embed(channel.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if not isinstance(before, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)) or not before.guild:
            return

        guild_id = before.guild.id
        embed = discord.Embed(
            title="✏️ Channel Updated",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Channel ID", value=after.id, inline=True)

        changes = []
        actor_info = ""
        performed_by = ""

        if before.name != after.name:
            changes.append(f"**Name**: `#{before.name}` -> `#{after.name}`")
        if before.topic != after.topic and isinstance(before, discord.TextChannel):
            changes.append(f"**Topic**: Changed")
        if before.category != after.category:
            changes.append(f"**Category**: `{before.category.name if before.category else 'None'}` -> `{after.category.name if after.category else 'None'}`")

        # Permissions overwrites (this can be very verbose, so a simplified log)
        if before.overwrites != after.overwrites:
            changes.append("**Permissions**: Updated")

        if changes:
            entry = await self._get_audit_log_entry(after.guild, discord.AuditLogAction.channel_update, after.id)
            if entry and entry.user:
                performed_by = f"\nPerformed by: {entry.user.mention} (`{entry.user.id}`)"
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason, inline=False)
            embed.description = f"Changes for {after.mention}:\n" + "\n".join(changes) + performed_by
            await self.send_log_embed(guild_id, embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if not role.guild:
            return

        embed = discord.Embed(
            title="➕ Role Created",
            description=f"Role {role.mention} has been created.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Name", value=role.name, inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
        embed.add_field(name="Role ID", value=role.id, inline=True)

        actor_info = "Unknown"
        entry = await self._get_audit_log_entry(role.guild, discord.AuditLogAction.role_create, role.id)
        if entry and entry.user:
            actor_info = f"\nPerformed By: {entry.user.mention} (`{entry.user.id}`)"
            if entry.reason:
                embed.add_field(name="Reason", value=entry.reason, inline=False)

        embed.description = f"{embed.description}{actor_info}"
        await self.send_log_embed(role.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if not role.guild:
            return

        embed = discord.Embed(
            title="➖ Role Deleted",
            description=f"Role `{role.name}` has been deleted.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Name", value=role.name, inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Role ID", value=role.id, inline=True)

        actor_info = "Unknown"
        entry = await self._get_audit_log_entry(role.guild, discord.AuditLogAction.role_delete, role.id)
        if entry and entry.user:
            actor_info = f"\nPerformed By: {entry.user.mention} (`{entry.user.id}`)"
            if entry.reason:
                embed.add_field(name="Reason", value=entry.reason, inline=False)

        embed.description = f"{embed.description}{actor_info}"
        await self.send_log_embed(role.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if not before.guild:
            return

        guild_id = before.guild.id
        embed = discord.Embed(
            title="✏️ Role Updated",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Role ID", value=after.id, inline=True)

        changes = []
        actor_info = ""
        performed_by = ""

        if before.name != after.name:
            changes.append(f"**Name**: `{before.name}` -> `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Color**: `{before.color}` -> `{after.color}`")
        if before.permissions != after.permissions:
            changes.append(f"**Permissions**: Updated")
        if before.mentionable != after.mentionable:
            changes.append(f"**Mentionable**: `{before.mentionable}` -> `{after.mentionable}`")
        if before.hoist != after.hoist:
            changes.append(f"**Display Separately**: `{before.hoist}` -> `{after.hoist}`")

        if changes:
            entry = await self._get_audit_log_entry(after.guild, discord.AuditLogAction.role_update, after.id)
            if entry and entry.user:
                performed_by = f"\nPerformed by: {entry.user.mention} (`{entry.user.id}`)"
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason, inline=False)
            embed.description = f"Changes for {after.mention}:\n" + "\n".join(changes) + performed_by
            await self.send_log_embed(guild_id, embed)

async def setup(bot):
    await bot.add_cog(SLCLogCog(bot))
