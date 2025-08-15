# main.py

import os
import discord
import asyncio
import threading
from discord.ext import commands
from discord import app_commands
import asyncio
import signal
from utils.logger import setup_logger
from config.config_manager import load_config

# Initialize logger
logger = setup_logger()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = False

# --- Permission Check Functions ---
# These should ideally be in a separate utils/permissions.py file
# and imported. Defining them here for self-containment.

def has_higher_role(moderator: discord.Member, target: discord.Member) -> bool:
    """
    Check if moderator has a higher role than target.
    Returns True if moderator's top role is higher than target's top role.
    Administrator permission overrides role hierarchy.
    """
    if moderator.guild_permissions.administrator:
        return True
    return moderator.top_role.position > target.top_role.position

def is_owner():
    """Check if user is bot owner"""
    async def predicate(interaction: discord.Interaction):
        # Ensure bot.config is accessible via interaction.client
        return interaction.user.id in interaction.client.config.get('owners', [])
    return app_commands.check(predicate)

def is_admin():
    """Check if user has administrator permission"""
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)

# You can define other specific permission checks similarly if needed
# e.g., has_kick_permission, has_ban_permission, etc.
# For brevity, let's assume they exist or are defined as needed.

# --- Bot Class ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.config = load_config()
        self.start_time = None
        self.restricted_guild_id = self.config.get('restricted_guild_id')
        self._last_result = None

    async def setup_hook(self):
        """Initialize the bot"""
        self.start_time = discord.utils.utcnow()

        # --- Load cogs ---
        logger.info("Loading cogs...")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                cog_name = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(cog_name)
                    logger.info(f'✅ Loaded cog: {filename[:-3]}')
                except Exception as e:
                    logger.error(f'❌ Failed to load cog {filename}: {e}', exc_info=True) # Added exc_info for debugging

        # --- Sync commands ---
        logger.info("Syncing commands...")
        try:
            if self.restricted_guild_id:
                guild = discord.Object(id=int(self.restricted_guild_id))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f'✅ Command tree synced ONLY to guild {self.restricted_guild_id}')
            else:
                await self.tree.sync()
                logger.info('✅ Command tree synced globally')
        except Exception as e:
            logger.error(f'❌ Failed to sync commands: {e}', exc_info=True)


    async def on_ready(self):
        """When bot is ready"""
        if self.restricted_guild_id:
            logger.info(f'Bot is ready as {self.user} (ID: {self.user.id}) - RESTRICTED MODE (Guild ID: {self.restricted_guild_id})')
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=f"/help"
            )
        else:
            logger.info(f'Bot is ready as {self.user} (ID: {self.user.id})')
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name="/help"
            )

        await self.change_presence(activity=activity)
        logger.info("Bot is fully online and ready!")

# --- Shutdown Handler ---
async def shutdown(sig, loop):
    """Cleanup tasks tied to the service's shutdown."""
    logger.info(f"Received exit signal {sig.name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    [task.cancel() for task in tasks]

    logger.info(f"Awaiting {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    try:
        loop.stop()
    finally:
        loop.close()
        logger.info("Loop closed.")

# --- Main Entry Point ---
async def main():
    """Main entry point"""
    bot = MyBot()

    # Add signal handlers for graceful shutdown
    loop = asyncio.get_running_loop() # Use get_running_loop inside the async function
    signals = (signal.SIGINT, signal.SIGTERM)
    for s in signals:
        loop.add_signal_handler(
            s, lambda sig=s: asyncio.create_task(shutdown(sig, loop))
        )

    try:
        async with bot:
            logger.info("Starting bot...")
            await bot.start(bot.config['token'])
    except asyncio.CancelledError:
        logger.info("Bot shutting down due to signal.")
    except Exception as e:
        logger.error(f"Bot failed to start or encountered an error: {e}", exc_info=True) # Added exc_info
    finally:
        logger.info("Bot is exiting.")

if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())
