import discord
from discord import app_commands
from discord.ext import commands
from config.config_manager import load_guild_config, save_guild_config

class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="prefix", description="Changes the bot prefix for this server")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(new_prefix="The new prefix for the server")
    async def prefix(self, interaction: discord.Interaction, new_prefix: str):
        """Changes the bot prefix for this server"""
        guild_id = interaction.guild.id
        config = load_guild_config(guild_id)
        config["prefix"] = new_prefix
        save_guild_config(guild_id, config)

        await interaction.response.send_message(
            f"✅ Prefix changed to `{new_prefix}`!",
            ephemeral=True
        )

    @app_commands.command(name="swc", description="Sets welcome channel")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="The channel to set as welcome channel")
    async def set_welcome_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Sets welcome channel"""
        guild_id = interaction.guild.id
        config = load_guild_config(guild_id)
        config['welcome_channel_id'] = str(channel.id)
        save_guild_config(guild_id, config)

        await interaction.response.send_message(
            f"✅ Welcome channel set to {channel.mention}",
            ephemeral=True
        )

    @app_commands.command(name="swm", description="Sets welcome message")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(message="The welcome message to use")
    async def set_welcome_message(self, interaction: discord.Interaction, message: str):
        """Sets welcome message"""
        guild_id = interaction.guild.id
        config = load_guild_config(guild_id)
        config['welcome_message'] = message
        save_guild_config(guild_id, config)

        await interaction.response.send_message(
            f"✅ Welcome message set to:\n`{message}`",
            ephemeral=True
        )

    @app_commands.command(name="autorole", description="Sets a role to be assigned automatically to new members")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(role="The role to assign to new members")
    async def autorole(self, interaction: discord.Interaction, role: discord.Role):
        """Sets a role to be assigned automatically to new members"""
        guild_id = interaction.guild.id
        config = load_guild_config(guild_id)
        config["autorole"] = role.id
        save_guild_config(guild_id, config)

        await interaction.response.send_message(
            f"✅ Role `{role.name}` will now be assigned to new members!",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
