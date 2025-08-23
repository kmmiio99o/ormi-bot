import discord
from discord import app_commands
from discord.ext import commands
from config.config_manager import load_guild_config, save_guild_config
import logging

logger = logging.getLogger(__name__)

class DeletedLogsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sdlc", description="Sets the deleted messages log channel")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="The channel to set as deleted messages log channel")
    async def set_deleted_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Sets the deleted messages log channel in the server's config file"""
        # Get the guild ID where the command was executed
        guild_id = interaction.guild.id

        # Load the server-specific configuration
        config = load_guild_config(guild_id)

        # Update the deleted log channel ID in the config
        config['deleted_messages_channel_id'] = str(channel.id)

        # Save the updated configuration back to the server-specific file
        save_guild_config(guild_id, config)

        # Create confirmation embed
        embed = discord.Embed(
            title="✅ Deleted Messages Log Channel Set",
            description=f"Deleted messages log channel has been set to {channel.mention}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="What now?",
            value="All deleted and edited messages will be logged in this channel.",
            inline=False
        )
        embed.set_footer(text="Configuration Updated")

        # Send confirmation message
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"{interaction.user} set deleted messages log channel to {channel.id} in {interaction.guild.name}")

        # Send a test message to verify the channel works
        try:
            test_embed = discord.Embed(
                title="🗑️ Deleted Messages Log Channel Active",
                description="This channel has been set as the deleted messages log channel.\nAll deleted and edited messages will be logged here.",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            test_embed.set_footer(text="Configuration Test")
            await channel.send(embed=test_embed)
        except discord.Forbidden:
            # If we can't send messages, inform the user
            await interaction.followup.send(
                "⚠️ Note: I don't have permission to send messages in that channel. "
                "Please make sure I have the proper permissions to log events there.",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        # Ignore messages from bots to prevent self-logging or logging other bots
        if message.author.bot:
            return

        # Ensure the message has a guild and a channel
        if not message.guild or not message.channel:
            return

        guild_id = message.guild.id
        config = load_guild_config(guild_id)
        log_channel_id = config.get('deleted_messages_channel_id')

        if log_channel_id:
            log_channel = self.bot.get_channel(int(log_channel_id))
            if log_channel:
                embed = discord.Embed(
                    title="🗑️ Message Deleted",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Author", value=message.author.mention, inline=True)
                embed.add_field(name="Channel", value=message.channel.mention, inline=True)

                # Truncate content if it's too long for an embed field
                message_content = message.content
                if message_content:
                    # Max characters for field value is 1024. ```\\n{content}\\n``` adds 7 characters.
                    # So content can be max 1017 chars. Truncate if original is longer.
                    if len(message_content) > 1017:
                        message_content = message_content[:1014] + "..." # 1014 chars + "..." = 1017 chars
                    embed.add_field(name="Content", value=f"```\\n{message_content}\\n```", inline=False)
                else:
                    embed.add_field(name="Content", value="*(No text content)*", inline=False)

                embed.set_footer(text=f"Author ID: {message.author.id} | Message ID: {message.id}")
                embed.set_thumbnail(url=message.author.display_avatar.url)

                try:
                    await log_channel.send(embed=embed)
                    logger.info(f"Logged deleted message from {message.author} in {message.guild.name}/{message.channel.name}")
                except discord.Forbidden:
                    logger.warning(f"Bot does not have permissions to send messages in log channel {log_channel_id} for guild {guild_id}.")
                except Exception as e:
                    logger.error(f"Error sending deleted message log: {e}", exc_info=True)
            else:
                logger.warning(f"Deleted messages log channel with ID {log_channel_id} not found for guild {guild_id}.")
        else:
            logger.debug(f"No deleted messages log channel set for guild {guild_id}.")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild or before.content == after.content:
            return

        guild_id = before.guild.id
        config = load_guild_config(guild_id)
        log_channel_id = config.get('deleted_messages_channel_id')

        if log_channel_id:
            log_channel = self.bot.get_channel(int(log_channel_id))
            if log_channel:
                embed = discord.Embed(
                    title="✍️ Message Edited",
                    color=discord.Color.light_grey(),
                    url=after.jump_url,  # Link to the message
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Author", value=after.author.mention, inline=True)
                embed.add_field(name="Channel", value=after.channel.mention, inline=True)

                # Original Content
                before_content = before.content
                if before_content:
                    if len(before_content) > 500:
                        before_content = before_content[:497] + "..."
                    embed.add_field(name="Original Content", value=f"```{before_content}```", inline=False)
                else:
                    embed.add_field(name="Original Content", value="*(No text content)*", inline=False)

                # New Content
                after_content = after.content
                if after_content:
                    if len(after_content) > 500:
                        after_content = after_content[:497] + "..."
                    embed.add_field(name="New Content", value=f"```{after_content}```", inline=False)
                else:
                    embed.add_field(name="New Content", value="*(No text content)*", inline=False)

                embed.set_footer(text=f"Message ID: {after.id}")
                embed.set_thumbnail(url=after.author.display_avatar.url)

                try:
                    await log_channel.send(embed=embed)
                    logger.info(f"Logged edited message from {after.author} in {after.guild.name}/{after.channel.name}")
                except discord.Forbidden:
                    logger.warning(f"Bot does not have permissions to send messages in log channel {log_channel_id} for guild {guild_id}.")
                except Exception as e:
                    logger.error(f"Error sending edited message log: {e}", exc_info=True)


async def setup(bot):
    await bot.add_cog(DeletedLogsCog(bot))
