import discord
from discord import app_commands
from discord.ext import commands, tasks
import re
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
import random
from pathlib import Path
import logging

# Set up logging
logger = logging.getLogger(__name__)

class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Create minimal storage directory
        self.data_dir = Path('data/giveaways')
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Store active giveaways (message_id|channel_id|end_time|winners)
        self.active_giveaways = []
        # Store ended giveaways that need cleanup (message_id|end_time|cleanup_time)
        self.ended_giveaways = []

        self.load_giveaways()
        self.check_giveaways.start()
        self.cleanup_ended_giveaways.start()

        # Temporary cache for participants (resets on bot restart)
        self.participants_cache = {}

    def cog_unload(self):
        self.check_giveaways.cancel()
        self.cleanup_ended_giveaways.cancel()

    def load_giveaways(self):
        """Load active and ended giveaways from minimal storage files"""
        try:
            with open(self.data_dir / 'active.json', 'r') as f:
                self.active_giveaways = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.active_giveaways = []

        try:
            with open(self.data_dir / 'ended.json', 'r') as f:
                self.ended_giveaways = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.ended_giveaways = []

    def save_active_giveaways(self):
        """Save active giveaways (tiny file)"""
        with open(self.data_dir / 'active.json', 'w') as f:
            json.dump(self.active_giveaways, f)

    def save_ended_giveaways(self):
        """Save ended giveaways for cleanup (tiny file)"""
        with open(self.data_dir / 'ended.json', 'w') as f:
            json.dump(self.ended_giveaways, f)

    def parse_duration(self, duration_str):
        """Parse duration string into seconds with flexible format"""
        # Convert to lowercase for case insensitivity
        duration_str = duration_str.lower()

        # Handle simple numeric values (assumed seconds)
        if duration_str.isdigit():
            return int(duration_str)

        # Pattern to match numbers followed by time units
        pattern = r'(\d+)\s*([smhdw])'
        matches = re.findall(pattern, duration_str)

        if not matches:
            return None

        total_seconds = 0
        for value, unit in matches:
            value = int(value)
            if unit == 's':
                total_seconds += value
            elif unit == 'm':
                total_seconds += value * 60
            elif unit == 'h':
                total_seconds += value * 3600
            elif unit == 'd':
                total_seconds += value * 86400
            elif unit == 'w':
                total_seconds += value * 604800

        return total_seconds

    def format_duration(self, seconds):
        """Format seconds into a human-readable duration"""
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"

        time_str = []
        weeks, remainder = divmod(seconds, 604800)
        days, remainder = divmod(remainder, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        if weeks > 0:
            time_str.append(f"{weeks}w")
        if days > 0:
            time_str.append(f"{days}d")
        if hours > 0:
            time_str.append(f"{hours}h")
        if minutes > 0:
            time_str.append(f"{minutes}m")
        if seconds > 0 or not time_str:  # Include seconds if no other units or if it's the only unit
            time_str.append(f"{seconds}s")

        return " ".join(time_str)

    @tasks.loop(seconds=10)
    async def check_giveaways(self):
        """Check if any giveaways have ended (runs in background)"""
        current_time = datetime.now(timezone.utc)
        to_remove = []

        for giveaway_str in self.active_giveaways[:]:  # Copy the list for safe iteration
            try:
                # Parse giveaway data
                parts = giveaway_str.split('|')
                message_id = int(parts[0])
                channel_id = int(parts[1])
                end_time = datetime.fromisoformat(parts[2])
                winners = int(parts[3]) if len(parts) > 3 else 1

                if current_time >= end_time:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        try:
                            message = await channel.fetch_message(message_id)
                            await self.end_giveaway(message, winners)

                            # Add to ended giveaways for cleanup
                            cleanup_time = (end_time + timedelta(seconds=5)).isoformat()
                            self.ended_giveaways.append(f"{message_id}|{end_time.isoformat()}|{cleanup_time}")
                            self.save_ended_giveaways()

                            to_remove.append(giveaway_str)
                        except discord.NotFound:
                            # Message was deleted, remove from active giveaways
                            to_remove.append(giveaway_str)
            except (ValueError, discord.DiscordException) as e:
                logger.error(f"Error checking giveaway: {e}")
                to_remove.append(giveaway_str)

        # Remove ended giveaways from active list
        for giveaway_str in to_remove:
            if giveaway_str in self.active_giveaways:
                self.active_giveaways.remove(giveaway_str)

        if to_remove:
            self.save_active_giveaways()

    @tasks.loop(seconds=5)
    async def cleanup_ended_giveaways(self):
        """Clean up ended giveaways after 5 seconds"""
        current_time = datetime.now(timezone.utc)
        to_remove = []

        for giveaway_str in self.ended_giveaways[:]:
            try:
                parts = giveaway_str.split('|')
                message_id = int(parts[0])
                cleanup_time = datetime.fromisoformat(parts[2])

                if current_time >= cleanup_time:
                    # Remove from cache if exists
                    if message_id in self.participants_cache:
                        del self.participants_cache[message_id]
                    to_remove.append(giveaway_str)
            except (ValueError, Exception) as e:
                logger.error(f"Error cleaning up giveaway: {e}")
                to_remove.append(giveaway_str)

        # Remove from ended list
        for giveaway_str in to_remove:
            if giveaway_str in self.ended_giveaways:
                self.ended_giveaways.remove(giveaway_str)

        if to_remove:
            self.save_ended_giveaways()

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()

    @cleanup_ended_giveaways.before_loop
    async def before_cleanup_ended_giveaways(self):
        await self.bot.wait_until_ready()

    async def end_giveaway(self, message, winners=1):
        """End a giveaway and pick winners using button participants"""
        logger.info(f"Ending giveaway with message ID: {message.id}, winners: {winners}")
        try:
            # Get participants from cache
            participants = self.participants_cache.get(message.id, [])

            if not participants:
                embed = discord.Embed(
                    title="🎉 Giveaway Ended 🎉",
                    description="No one participated in this giveaway. 😢",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                await message.channel.send(embed=embed)

                # Update the giveaway message
                embed = message.embeds[0]
                embed.title = "🎉 Giveaway Ended 🎉"
                embed.color = discord.Color.red()
                embed.description = embed.description.replace("Ends:", "Ended:") + "\n\nNo participants found."
                await message.edit(embed=embed, view=None)  # Remove the button
                return

            # Pick random winners (no duplicates)
            actual_winners = min(winners, len(participants))
            selected_winners = random.sample(participants, actual_winners)

            # Format winners list
            winners_list = "\n".join([f"{i+1}. {winner.mention}" for i, winner in enumerate(selected_winners)])

            # Update the giveaway message
            embed = message.embeds[0]
            embed.title = "🎉 Giveaway Ended 🎉"
            embed.color = discord.Color.green()
            original_description = embed.description.replace("Ends:", "Ended:")

            if actual_winners == 1:
                embed.description = f"{original_description}\n\n**Winner: {selected_winners[0].mention}**"
            else:
                embed.description = f"{original_description}\n\n**Winners ({actual_winners}/{winners}):**\n{winners_list}"

            await message.edit(embed=embed, view=None)  # Remove the button

            # Announce the winners
            if actual_winners == 1:
                winner_text = f"Winner: {selected_winners[0].mention}"
            else:
                winner_text = f"Winners ({actual_winners}/{winners}):\n{winners_list}"

            embed = discord.Embed(
                title="🎉 Giveaway Ended 🎉",
                description=f"**{embed.fields[0].value}**\n\n{winner_text}\nCongratulations! 🎊",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            await message.channel.send(embed=embed)

        except Exception as e:
            logger.exception(f"Error ending giveaway with message ID {message.id}: {e}")
            try:
                await message.channel.send("❌ An error occurred while ending the giveaway.")
            except:
                pass
        logger.info(f"Finished ending giveaway with message ID: {message.id}")

    @app_commands.command(name="giveaway", description="Creates a new giveaway")
    @app_commands.describe(winners="Number of winners (default: 1)", duration="Duration (e.g., 30s, 5m, 1h, 2d)", prize="Prize for the giveaway")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def create_giveaway(self, interaction: discord.Interaction, duration: str, prize: str, winners: int = 1):
        """Create a new giveaway with button-based entry (toggle like reactions)"""
        # Parse duration
        seconds = self.parse_duration(duration)
        if seconds is None or seconds < 5:  # Minimum 5 seconds
            embed = discord.Embed(
                title="❌ Error",
                description="Invalid duration format! Use examples: `30s`, `5m`, `1h`, `2d`.",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Parse winners (must be at least 1)
        if winners < 1:
            embed = discord.Embed(
                title="❌ Error",
                description="Number of winners must be at least 1!",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Create button view
        class GiveawayView(discord.ui.View):
            def __init__(self, cog, message_id):
                super().__init__(timeout=None)  # Persistent view
                self.cog = cog
                self.message_id = message_id

                # Create the button
                self.participate_button = discord.ui.Button(
                    label="Participate (0)",
                    style=discord.ButtonStyle.green,
                    emoji="🎉"
                )
                self.participate_button.callback = self.participate
                self.add_item(self.participate_button)

                # Update the button label with current participant count
                participant_count = len(self.cog.participants_cache.get(message_id, []))
                self.participate_button.label = f"Participate ({participant_count})"

            async def participate(self, interaction: discord.Interaction):
                # Initialize participant list if needed
                if self.message_id not in self.cog.participants_cache:
                    self.cog.participants_cache[self.message_id] = []

                # Check if user is already participating
                is_participating = any(p.id == interaction.user.id for p in self.cog.participants_cache[self.message_id])

                if is_participating:
                    # Remove participant
                    self.cog.participants_cache[self.message_id] = [
                        p for p in self.cog.participants_cache[self.message_id]
                        if p.id != interaction.user.id
                    ]
                    action = "left"
                    button_style = discord.ButtonStyle.green
                else:
                    # Add participant
                    self.cog.participants_cache[self.message_id].append(interaction.user)
                    action = "joined"
                    button_style = discord.ButtonStyle.blurple

                # Update button label and style
                participant_count = len(self.cog.participants_cache[self.message_id])
                self.participate_button.label = f"Participate ({participant_count})"
                self.participate_button.style = button_style

                await interaction.response.edit_message(view=self)

                # Send confirmation
                await interaction.followup.send(
                    f"✅ You have {action} the giveaway!",
                    ephemeral=True
                )

        # Create embed
        end_time = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        embed = discord.Embed(
            title=f"🎉 Giveaway: {prize} 🎉",
            description=f"Click the button below to participate!\nEnds: <t:{int(end_time.timestamp())}:R>",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Hosted by", value=interaction.user.mention, inline=False)
        embed.add_field(name="Winners", value=str(winners), inline=False)

        # Send message with button
        view = GiveawayView(self, 0)  # Placeholder ID
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()

        # Update view with actual message ID
        view.message_id = message.id
        # Update the button label with actual participant count
        participant_count = len(self.participants_cache.get(message.id, []))
        view.participate_button.label = f"Participate ({participant_count})"
        await message.edit(view=view)

        # Store minimal giveaway info (message_id|channel_id|end_time|winners)
        message_id = f"{message.id}|{interaction.channel.id}|{end_time.isoformat()}|{winners}"
        self.active_giveaways.append(message_id)
        self.save_active_giveaways()

        # Initialize participants cache
        self.participants_cache[message.id] = []

        # Send confirmation
        duration_str = self.format_duration(seconds)
        embed = discord.Embed(
            title="🎉 Giveaway Created",
            description=f"Giveaway created for **{prize}**!\n"
                        f"• Duration: {duration_str}\n"
                        f"• Winners: {winners}\n"
                        f"• Click the button to participate",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="endgiveaway", description="Ends a giveaway early")
    @app_commands.describe(giveaway_id="Message ID of the giveaway", winners="Number of winners (optional, defaults to original)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def end_giveaway_command(self, interaction: discord.Interaction, giveaway_id: str, winners: int = None):
        """End a giveaway early with optional winner count"""
        logger.info(f"Ending giveaway command with giveaway ID: {giveaway_id}, winners: {winners}")
        try:
            message_id = int(giveaway_id)
        except ValueError:
            embed = discord.Embed(
                title="❌ Error",
                description="Giveaway ID must be a message ID (numbers only)!",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Find the giveaway
        giveaway = None
        for gid in self.active_giveaways:
            if int(gid.split('|')[0]) == message_id:
                giveaway = gid
                break

        if not giveaway:
            embed = discord.Embed(
                title="❌ Error",
                description="Could not find a giveaway with that message ID.",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            channel_id = int(giveaway.split('|')[1])
            channel = self.bot.get_channel(channel_id)
            message = await channel.fetch_message(message_id)

            # Check if this is actually a giveaway message
            if not message.embeds or "Giveaway" not in message.embeds[0].title:
                embed = discord.Embed(
                    title="❌ Error",
                    description="This doesn't appear to be a giveaway message.",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Get winners count from giveaway data or use provided value
            stored_winners = int(giveaway.split('|')[3]) if len(giveaway.split('|')) > 3 else 1
            actual_winners = winners if winners is not None and winners > 0 else stored_winners

            await self.end_giveaway(message, actual_winners)

            # Add to ended giveaways for cleanup
            end_time = datetime.now(timezone.utc)
            cleanup_time = (end_time + timedelta(seconds=5)).isoformat()
            self.ended_giveaways.append(f"{message_id}|{end_time.isoformat()}|{cleanup_time}")
            self.save_ended_giveaways()

            # Remove from active giveaways
            if giveaway in self.active_giveaways:
                self.active_giveaways.remove(giveaway)
                self.save_active_giveaways()

            embed = discord.Embed(
                title="✅ Success",
                description=f"Giveaway ended successfully with {actual_winners} winner{'s' if actual_winners > 1 else ''}.",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception(f"Error ending giveaway command with giveaway ID {giveaway_id}: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while ending the giveaway.",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Finished ending giveaway command with giveaway ID: {giveaway_id}")

    @app_commands.command(name="reroll", description="Rerolls a giveaway for new winners")
    @app_commands.describe(giveaway_id="Message ID of the giveaway", winners="Number of winners (optional, defaults to 1)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def reroll_giveaway(self, interaction: discord.Interaction, giveaway_id: str, winners: int = 1):
        """Reroll a giveaway for new winners"""
        logger.info(f"Rerolling giveaway with message ID: {giveaway_id}, winners: {winners}")
        try:
            message_id = int(giveaway_id)
        except ValueError:
            embed = discord.Embed(
                title="❌ Error",
                description="Giveaway ID must be a message ID (numbers only)!",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            message = await interaction.channel.fetch_message(message_id)

            # Check if this is a giveaway message
            if not message.embeds or "Giveaway" not in message.embeds[0].title:
                embed = discord.Embed(
                    title="❌ Error",
                    description="This doesn't appear to be a giveaway message.",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Get participants from cache
            participants = self.participants_cache.get(message_id, [])

            if not participants:
                embed = discord.Embed(
                    title="❌ Error",
                    description="No participants in this giveaway!",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Check if there are previous winners to exclude
            previous_winners = []
            if message.embeds[0].description:
                for line in message.embeds[0].description.split('\n'):
                    if "Winner:" in line or "Winners:" in line:
                        # Extract mentions from the line
                        matches = re.findall(r'<@!?(\d+)>', line)
                        previous_winners.extend([int(match) for match in matches])
                        break

            # Filter out previous winners
            participants = [user for user in participants if user.id not in previous_winners]

            if not participants:
                embed = discord.Embed(
                    title="❌ Error",
                    description="No other participants to reroll!",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Pick new winners
            actual_winners = min(winners, len(participants))
            new_winners = random.sample(participants, actual_winners)

            # Format winners list
            winners_list = "\n".join([f"{i+1}. {winner.mention}" for i, winner in enumerate(new_winners)])

            # Update the giveaway message
            embed = message.embeds[0]
            original_description = embed.description.replace("Ended:", "Rerolled:")

            if actual_winners == 1:
                embed.description = f"{original_description}\n\n**New Winner: {new_winners[0].mention}**"
            else:
                embed.description = f"{original_description}\n\n**New Winners ({actual_winners}/{winners}):**\n{winners_list}"

            await message.edit(embed=embed)

            # Announce the new winners
            if actual_winners == 1:
                winner_text = f"New Winner: {new_winners[0].mention}"
            else:
                winner_text = f"New Winners ({actual_winners}/{winners}):\n{winners_list}"

            embed = discord.Embed(
                title="🎉 Giveaway Rerolled 🎉",
                description=f"**{message.embeds[0].fields[0].value}**\n\n{winner_text}\nCongratulations! 🎊",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception(f"Error rerolling giveaway with message ID {giveaway_id}: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while rerolling the giveaway.",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Finished rerolling giveaway with message ID: {giveaway_id}")

async def setup(bot):
    await bot.add_cog(GiveawayCog(bot))
