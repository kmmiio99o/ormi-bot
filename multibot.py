import discord
from discord.ext import commands
from discord.utils import get
import requests
import asyncio
import datetime
import json
import random
from datetime import UTC
import pylast
import time
import os
import aiohttp
import io
from pathlib import Path
import pyfiglet

# Configuration
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

TOKEN = config['token']
PREFIX = config.get('prefix', ';')
MOD_ROLE = config.get('mod_role', 'Moderator')
ADMIN_ROLE = config.get('admin_role', 'admin')
LOG_CHANNEL_ID = config.get('log_channel_id')
DELETED_LOG_CHANNEL_ID = config.get('deleted_log_channel_id')
WELCOME_CHANNEL_ID = config.get('welcome_channel_id')
WELCOME_MESSAGE = config.get('welcome_message', "Welcome on the server, {member.display_name}!")

intents = discord.Intents.default()
intents.presences = False
intents.members = True
intents.message_content = True

def get_prefix(bot, message):
    guild_id = message.guild.id if message.guild else None
    config = load_guild_config(guild_id)
    return config.get("prefix", ";")  # Default to ";" if not configured

bot = commands.Bot(command_prefix=get_prefix, intents=intents, case_insensitive=True, help_command=None)

# Global collection for tracking channels on which purge operates
purging_channels = set()

# Global dictionary for tracking active giveaways
active_giveaways = {}

# Global dictionary for tracking users' latest messages
message_cache = {}

# Configuration Last.fm
LASTFM_API_KEY = ""
LASTFM_API_SECRET = ""
LASTFM_USERNAME = ""

# Tracks user cooldowns (15s delay between commands)
user_cooldowns = {}

lastfm_network = pylast.LastFMNetwork(api_key=LASTFM_API_KEY, api_secret=LASTFM_API_SECRET)

# Tracks active voice connections
voice_clients = {}

# Tracks AFK users and their statuses
afk_users = {}

# Path to the file with reactions
REACTION_ROLES_FILE = "reaction_roles.json"

# Ładowanie reakcji przy starcie
if os.path.exists(REACTION_ROLES_FILE):
    with open(REACTION_ROLES_FILE, 'r') as f:
        bot.reaction_roles = json.load(f)
else:
    bot.reaction_roles = {}

def save_reaction_roles():
    with open(REACTION_ROLES_FILE, 'w') as f:
        json.dump(bot.reaction_roles, f, indent=4)

# Helper function to check role hierarchy
def has_higher_role(moderator: discord.Member, target: discord.Member):
    # Server owner can always moderate
    if moderator == moderator.guild.owner:
        return True
    # Check if moderator's top role is higher than target's top role
    return moderator.top_role.position > target.top_role.position

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="🚫 Permission Denied",
            description="You don't have the required permissions to use this command!",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Required Permissions",
            value="\n".join([f"• {perm.replace('_', ' ').title()}" for perm in error.missing_permissions]),
            inline=False
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, discord.Forbidden):
        if error.code == 50001:  # Missing Access
            embed = discord.Embed(
                title="🔒 Missing Bot Access",
                description="I don't have the necessary permissions to perform this action!",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Common Solutions",
                value=(
                    "1. Check if my role has **Administrator** permission\n"
                    "2. Move my role **higher** in the role hierarchy\n"
                    "3. Verify channel-specific permissions\n"
                    "4. Check if the target user has higher permissions"
                ),
                inline=False
            )
            embed.set_footer(text=f"Error: {error.text}")
        else:
            embed = discord.Embed(
                title="🔒 Forbidden Action",
                description="I'm not allowed to perform this action",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Error Details",
                value=f"Code: {error.code}\nReason: {error.text}",
                inline=False
            )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title="❌ Unknown Command",
            description=f"Command `{ctx.invoked_with}` doesn't exist. Use `{PREFIX}help` for available commands.",
            color=0xFF0000
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="⚠️ Missing Argument",
            description=f"> Correct usage: `{PREFIX}{ctx.command.name} {ctx.command.signature}`\n> Example: `{PREFIX}{ctx.command.name} {ctx.command.usage if hasattr(ctx.command, 'usage') else 'value'}`",
            color=0xFFA500
        )
        await ctx.send(embed=embed)
    
    else:
        print(f"Unhandled error: {error}")
        embed = discord.Embed(
            title="❌ Unexpected Error",
            description="An unexpected error occurred while processing your command",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Details",
            value=f"```{str(error)[:1000]}```",
            inline=False
        )
        await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return await bot.process_commands(message)

    # Check if the author of the message was AFK
    if message.author.id in afk_users:
        afk_data = afk_users.pop(message.author.id)
        duration = datetime.datetime.now(UTC) - afk_data["timestamp"]
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Restore the original AFK message (if any)
        if afk_data["message_id"]:
            try:
                afk_message = await message.channel.fetch_message(afk_data["message_id"])
                await afk_message.delete()
            except discord.NotFound:
                pass
        
        embed = discord.Embed(
            title="⏯️ Welcome Back!",
            description=f"{message.author.mention} is no longer AFK!\n"
                      f"**You were AFK for:** {int(hours)}h {int(minutes)}m {int(seconds)}s\n"
                      f"**Reason:** {afk_data['reason']}",
            color=discord.Color.green()
        )
        await message.channel.send(embed=embed)

    # Check if someone has been tagged and is AFK
    for mention in message.mentions:
        if mention.id in afk_users:
            afk_data = afk_users[mention.id]
            duration = datetime.datetime.now(UTC) - afk_data["timestamp"]
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            embed = discord.Embed(
                title="⏸️ User is AFK",
                description=f"{mention.mention} has been AFK for {int(hours)}h {int(minutes)}m {int(seconds)}s!\n"
                          f"**Reason:** {afk_data['reason']}",
                color=discord.Color.blue()
            )
            await message.channel.send(embed=embed)

    # Save message in cache
    message_cache[message.id] = {
        "author": message.author,
        "content": message.content,
        "attachments": message.attachments,
        "channel": message.channel,
        "timestamp": datetime.datetime.now(UTC)
    }

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    # Ignore messages from bots
    if message.author.bot:
        return

    # Ignore messages from channels that are currently being purged by purge
    if message.channel.id in purging_channels:
        return

    # Save only deleted messages in the cache
    message_cache[message.id] = {
        "author": message.author,
        "content": message.content,
        "attachments": message.attachments,
        "channel": message.channel,
        "timestamp": datetime.datetime.now(UTC),
        "deleted": True
    }

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    # Check if the reaction is related to an active giveaway.
    if reaction.message.id in active_giveaways and str(reaction.emoji) == "🎉":
        giveaway = active_giveaways[reaction.message.id]
        giveaway["participants"].add(user.id)

@bot.event
async def on_member_join(member):
    # Załaduj konfigurację serwera
    config = load_guild_config(member.guild.id)
    if not config:
        return  # Brak konfiguracji, pomiń
    
    welcome_channel_id = config.get('welcome_channel_id')
    if welcome_channel_id:
        welcome_channel = member.guild.get_channel(welcome_channel_id)
        if welcome_channel:
            welcome_message = config.get('welcome_message', "Welcome on the server, {member.mention}!")
            await welcome_channel.send(welcome_message.format(member=member))
    
    if "autorole" in config:
        role = member.guild.get_role(config["autorole"])
        if role and role not in member.roles:
            await member.add_roles(role)

# Helper functions
async def log_action(action, moderator, target, reason=None, duration=None):
    guild_id = moderator.guild.id if moderator else (target.guild.id if target else None)
    if not guild_id:
        print("BŁĄD: Nie można określić ID serwera dla logowania.")
        return

    config = load_guild_config(guild_id)  # Loading configuration for the given server
    log_channel_id = config.get('log_channel_id')
    
    if not log_channel_id:
        print(f"Ostrzeżenie: ID kanału logów nie jest ustawione dla serwera {guild_id}. Logowanie pominięte.")
        return

    log_channel = bot.get_channel(int(log_channel_id))
    if not log_channel:
        print(f"Ostrzeżenie: Nie znaleziono kanału logów o ID {log_channel_id} dla serwera {guild_id}.")
        return

    # Additional protection against NoneType for the moderator
    if not moderator:
        print(f"BŁĄD KRYTYCZNY w log_action: Obiekt 'moderator' jest None podczas logowania akcji '{action}'. Logowanie pominięte.")
        return

    # Setting the color depending on the action
    if action.lower() in ['ban', 'kick']:
        color = discord.Color.red()
    elif action.lower() == 'mute':
        color = discord.Color.orange()
    elif action.lower() in ['message deleted', 'unban']:
        color = discord.Color.blue()
    else:
        color = discord.Color.orange()

    embed = discord.Embed(
        title=f"Moderation action: {action}",
        color=color,
        timestamp=datetime.datetime.now(UTC)
    )
    embed.add_field(name="Moderator", value=moderator.mention, inline=True)
    embed.add_field(name="User", value=target.mention if target else "N/A", inline=True)
    
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)
    if duration:
        embed.add_field(name="Duration", value=duration, inline=True)

    try:
        await log_channel.send(embed=embed)
    except discord.Forbidden:
        print(f"Warning: Brak uprawnień do wysyłania wiadomości na kanale logów {log_channel_id}.")
    except Exception as e:
        print(f"Error podczas logowania: {e}")

def is_mod(ctx):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    mod_role_id = config.get('mod_role')
    admin_role_id = config.get('admin_role')
    
    # Check if the user has a moderator or administrator role
    if mod_role_id and any(role.id == int(mod_role_id) for role in ctx.author.roles):
        return True
    if admin_role_id and any(role.id == int(admin_role_id) for role in ctx.author.roles):
        return True
    return False

def is_admin(ctx):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    admin_role_id = config.get('admin_role')
    
    # Check if the user has an administrator role
    if admin_role_id and any(role.id == int(admin_role_id) for role in ctx.author.roles):
        return True
    return False

def generate_case_id():
    """Generates a numeric case ID with max 8 digits"""
    timestamp = int(datetime.datetime.now(UTC).strftime('%m%d%H%M'))
    random_suffix = random.randint(10, 99)
    return f"{timestamp}{random_suffix}"

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user.name}')
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{PREFIX}help"
        )
    )

# Moderation commands
@bot.command(name='kick', 
             help='Kicks a user from the server', 
             usage="<user_id> [reason]",
             description="Example: ;kick 123456789 Spamming")
@commands.has_permissions(kick_members=True)
async def kick(ctx, user_id: int, *, reason="Not specified"):
    try:
        member = await commands.MemberConverter().convert(ctx, str(user_id))
    except commands.MemberNotFound:
        return await ctx.send(f"❌ User with ID {user_id} not found in this server!")

    if member == ctx.author:
        return await ctx.send("❌ You can't kick yourself!")
    if not has_higher_role(ctx.author, member):
        return await ctx.send("❌ You can't kick a user with equal or higher role!")
    if ctx.guild.me.top_role.position <= member.top_role.position:
        return await ctx.send("❌ My role is too low to kick this user!")

    await member.kick(reason=reason)
    await ctx.send(embed=discord.Embed(
        title="👢 Bye-bye!",
        description=f"{member.mention} was kicked!\n**Reason:** {reason}\n*~flying kick~*",
        color=discord.Color.orange()
    ))
    await log_action("Kick", ctx.author, member, reason)

@bot.command(name='ban', 
             help='Bans a user from the server', 
             usage="<user_id> [duration] [reason]",
             description="Examples:\n;ban 123456789\n;ban 123456789 7d Harassment")
@commands.has_permissions(ban_members=True)
async def ban(ctx, user_id: int, *args):
    duration = "perm"
    reason = "Not specified"
    
    if len(args) > 0:
        if args[0][-1] in ('m', 'h', 'd') and args[0][:-1].isdigit():
            duration = args[0]
            reason = " ".join(args[1:]) if len(args) > 1 else "Not specified"
        else:
            reason = " ".join(args)
    
    try:
        user = await bot.fetch_user(user_id)
        
        if duration.lower() == "perm":
            ban_duration = "Permanent ban"
        else:
            try:
                time_value = int(duration[:-1])
                time_unit = duration[-1].lower()
                if time_unit == 'm':
                    ban_duration = f"{time_value} minute(s)"
                elif time_unit == 'h':
                    ban_duration = f"{time_value} hour(s)"
                elif time_unit == 'd':
                    ban_duration = f"{time_value} day(s)"
                else:
                    return await ctx.send("❌ Invalid time unit. Use m (minutes), h (hours), or d (days)")
            except (ValueError, IndexError):
                return await ctx.send("❌ Invalid duration format. Example: 30m, 2h, 1d")
        
        # Embed dla DM
        dm_embed = discord.Embed(
            title="🔨 You've been banned",
            description=f"You have been banned from {ctx.guild.name}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(UTC)
        )
        dm_embed.set_footer(text=f"Server: {ctx.guild.name}")
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        dm_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        dm_embed.add_field(name="Duration", value=ban_duration, inline=True)
        
        # DM Appeal
        owner = ctx.guild.owner
        contact_info = f"If you believe this is a mistake, please contact the server owner: {owner.mention}."
        dm_embed.add_field(name="Appeal", value=contact_info, inline=False)
        
        # Embed for server
        server_embed = discord.Embed(
            title="🔨 User Banned",
            description=f"**User:** <@{user_id}>\n**Reason:** {reason}\n**Duration:** {ban_duration}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(UTC)
        )
        server_embed.set_footer(text=f"Moderator: {ctx.author.display_name}")
        
        # Send DM
        try:
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass
        
        # Ban the user and send the embed to the server
        await ctx.guild.ban(discord.Object(id=user_id), reason=f"{reason} | Duration: {ban_duration}")
        await ctx.send(embed=server_embed)
        await log_action("Ban", ctx.author, f"<@{user_id}>", f"{reason} | Duration: {ban_duration}")
    except discord.NotFound:
        await ctx.send("❌ User not found.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban this user.")
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {e}")

@bot.command(name='unban', 
             help='Unbans a user', 
             usage="<user_id>",
             description="Example: ;unban 123456789")
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        user = await bot.fetch_user(user_id)
    except discord.NotFound:
        return await ctx.send("❌ User not found!")
    
    await ctx.guild.unban(user)
    embed = discord.Embed(
        title="🔓 User Unbanned",
        description=f"**User:** {user.mention}",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(UTC)
    )
    await ctx.send(embed=embed)
    await log_action("Unban", ctx.author, user)

@bot.command(name='mute', help='Mutes a user for a specified time (e.g., 30m, 2h) or permanently (use "perm")')
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: str = "30m", *, reason="Not specified"):
    try:
        if duration.lower() == "perm":
            mute_duration = "Permanent mute"
            timeout = None
        else:
            try:
                time_value = int(duration[:-1])
                time_unit = duration[-1].lower()
                if time_unit == 'm':
                    mute_duration = f"{time_value} minute(s)"
                    timeout = datetime.timedelta(minutes=time_value)
                elif time_unit == 'h':
                    mute_duration = f"{time_value} hour(s)"
                    timeout = datetime.timedelta(hours=time_value)
                elif time_unit == 'd':
                    mute_duration = f"{time_value} day(s)"
                    timeout = datetime.timedelta(days=time_value)
                else:
                    return await ctx.send("❌ Invalid time unit. Use m (minutes), h (hours), or d (days)")
            except (ValueError, IndexError):
                return await ctx.send("❌ Invalid duration format. Example: 30m, 2h, 1d")
        
        # Embed dla DM
        dm_embed = discord.Embed(
            title="🔇 You've been muted",
            description=f"You have been muted on {ctx.guild.name}",
            color=discord.Color.dark_grey(),
            timestamp=datetime.datetime.now(UTC)
        )
        dm_embed.set_footer(text=f"Server: {ctx.guild.name}")
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        dm_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        dm_embed.add_field(name="Duration", value=mute_duration, inline=True)
        
        owner = ctx.guild.owner
        contact_info = f"If you believe this is a mistake, please contact the server owner: {owner.mention}."
        dm_embed.add_field(name="Appeal", value=contact_info, inline=False)
        
        # Embed for server
        server_embed = discord.Embed(
            title="🔇 User Muted",
            description=f"**User:** {member.mention}\n**Reason:** {reason}\n**Duration:** {mute_duration}",
            color=discord.Color.dark_grey(),
            timestamp=datetime.datetime.now(UTC)
        )
        server_embed.set_footer(text=f"Moderator: {ctx.author.display_name}")
        
        try:
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass
        
        await member.timeout(timeout, reason=reason)
        await ctx.send(embed=server_embed)
        await log_action("Mute", ctx.author, member, f"{reason} | Duration: {mute_duration}")
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {e}")

@bot.command(name='unmute', help='Unmutes a user')
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    try:
        await member.timeout(None, reason="Unmuted by command")
        embed = discord.Embed(
            title="🔊 User Unmuted",
            description=f"{member.mention} has been unmuted.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to unmute this user.")
    except discord.HTTPException:
        await ctx.send("❌ Failed to unmute the user. Please try again.")

@bot.command(name='warn', 
             help='Gives a warning to a user', 
             usage="<user_id> [reason]",
             description="Example: ;warn 123456789 Spamming")
@commands.has_permissions(kick_members=True)
async def warn(ctx, user_id: int, *, reason="Not specified"):
    try:
        user = await bot.fetch_user(user_id)
        
        dm_embed = discord.Embed(
            title="⚠️ You've been warned",
            description=f"You have received a warning on {ctx.guild.name}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(UTC)
        )
        dm_embed.set_footer(text=f"Server: {ctx.guild.name}")
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        dm_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        
        owner = ctx.guild.owner
        contact_info = f"If you believe this is a mistake, please contact the server owner: {owner.mention}."
        dm_embed.add_field(name="Appeal", value=contact_info, inline=False)
        
        server_embed = discord.Embed(
            title="⚠️ User Warned",
            description=f"**User:** <@{user_id}>\n**Reason:** {reason}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(UTC)
        )
        server_embed.set_footer(text=f"Moderator: {ctx.author.display_name}")
        
        try:
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass
        
        await ctx.send(embed=server_embed)
        await log_action("Warn", ctx.author, f"<@{user_id}>", reason)
    except discord.NotFound:
        await ctx.send("❌ User not found.")
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {e}")

@bot.command(name='warnings', help='Shows user warnings')
@commands.has_permissions(kick_members=True)
async def warnings(ctx, member: discord.Member):
    try:
        # Load warnings
        guild_warnings = load_guild_warnings(ctx.guild.id)
        user_warnings = guild_warnings.get(str(member.id), [])

        # Create embed
        embed = discord.Embed(
            title=f"Warnings for {member.display_name}",
            color=discord.Color.orange()
        )

        if not user_warnings:
            embed.description = "ℹ️ No warnings found."
        else:
            embed.description = f"Total warnings: {len(user_warnings)}"
            for warn in user_warnings:
                try:
                    mod = await bot.fetch_user(warn['moderator'])
                    embed.add_field(
                        name=f"Case {warn['case_id']}",
                        value=f"Moderator: {mod.mention}\nReason: {warn['reason']}\nDate: {warn['timestamp']}",
                        inline=False
                    )
                except Exception as e:
                    print(f"Error processing warning {warn['case_id']}: {e}")
                    continue

        # Send single embed
        await ctx.send(embed=embed)

    except FileNotFoundError:
        await ctx.send("ℹ️ No warnings file found.")
    except Exception as e:
        print(f"Error: {e}")
        await ctx.send("❌ An error occurred while loading warnings.")

@bot.command(name='clearwarns', help='Clears a user\'s warnings')
@commands.has_permissions(kick_members=True)
async def clearwarns(ctx, member: discord.Member):
    if not has_higher_role(ctx.author, member):
        return await ctx.send("❌ You can't clear warnings for a user with equal or higher role!")

    guild_id = ctx.guild.id
    warnings = load_guild_warnings(guild_id)
    if str(member.id) in warnings:
        del warnings[str(member.id)]
    save_guild_warnings(guild_id, warnings)

    await ctx.send(f"✅ Cleared warnings for {member.mention}!")
    await log_action("Clear Warnings", ctx.author, member)

@bot.command(name='delwarn', help='Deletes a specific warning', usage="<case_id>")
@commands.has_permissions(kick_members=True)
async def delwarn(ctx, case_id: str):
    guild_id = ctx.guild.id
    warnings = load_guild_warnings(guild_id)
    
    # Find warning by case_id
    for user_id, user_warnings in warnings.items():
        for warning in user_warnings:
            if warning['case_id'] == case_id:
                user_warnings.remove(warning)
                save_guild_warnings(guild_id, warnings)
                embed = discord.Embed(
                    title="✅ Warning deleted",
                    description=f"Deleted warning with ID: `{case_id}`",
                    color=discord.Color.green()
                )
                return await ctx.send(embed=embed)
    
    # If not found
    embed = discord.Embed(
        title="❌ Error",
        description=f"Warning with ID `{case_id}` not found.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name='case', help='Shows details about a specific warning', usage="<case_id>")
@commands.has_permissions(kick_members=True)
async def case_info(ctx, case_id: str):
    guild_id = ctx.guild.id
    warnings = load_guild_warnings(guild_id)
    
    # Find warning by case_id
    for user_id, user_warnings in warnings.items():
        for warning in user_warnings:
            if warning['case_id'] == case_id:
                moderator = ctx.guild.get_member(warning['moderator'])
                target = ctx.guild.get_member(int(user_id))
                embed = discord.Embed(
                    title=f"📄 Warning details: {case_id}",
                    description=f"**User:** {target.mention if target else 'Unknown'}\n"
                              f"**Moderator:** {moderator.mention if moderator else 'Unknown'}\n"
                              f"**Reason:** {warning['reason']}\n"
                              f"**Date:** {warning['timestamp']}",
                    color=discord.Color.blue()
                )
                return await ctx.send(embed=embed)
    
    # If not found
    embed = discord.Embed(
        title="❌ Error",
        description=f"Warning with ID `{case_id}` not found.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name='editcase', help='Edits the reason for a specific warning', usage="<case_id> <new_reason>")
@commands.has_permissions(kick_members=True)
async def edit_case(ctx, case_id: str, *, new_reason):
    guild_id = ctx.guild.id
    warnings = load_guild_warnings(guild_id)
    
    # Find warning by case_id
    for user_id, user_warnings in warnings.items():
        for warning in user_warnings:
            if warning['case_id'] == case_id:
                warning['reason'] = new_reason
                save_guild_warnings(guild_id, warnings)
                embed = discord.Embed(
                    title="✅ Warning updated",
                    description=f"Updated reason for warning with ID: `{case_id}`",
                    color=discord.Color.green()
                )
                return await ctx.send(embed=embed)
    
    # If not found
    embed = discord.Embed(
        title="❌ Error",
        description=f"Warning with ID `{case_id}` not found.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name='purge', help='Deletes messages (default: 5)')
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int = 5):
    if amount > 100:
        embed = discord.Embed(
            title="❌ Error",
            description="You can't delete more than 100 messages at once!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    channel_id = ctx.channel.id
    purging_channels.add(channel_id)
    try:
        deleted_messages = await ctx.channel.purge(limit=amount + 1)
        num_deleted = len(deleted_messages) - 1
        if num_deleted < 0:
            num_deleted = 0
        embed = discord.Embed(
            title="✅ Success",
            description=f"Deleted {num_deleted} messages! UwU clean as a tear~ 🥺",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed, delete_after=5)
        await log_action("Purge", ctx.author, None, f"{num_deleted} messages in #{ctx.channel.name}")
    except discord.Forbidden:
        embed = discord.Embed(
            title="❌ Error",
            description="I don't have permission to delete messages in this channel.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred during purge: {e}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    finally:
        purging_channels.discard(channel_id)

@bot.command(name='slowmode', help='Sets slowmode (in seconds)')
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    if seconds < 0:
        return await ctx.send("❌ Slowmode time can't be negative!")
    if seconds > 21600:
        return await ctx.send("❌ Maximum slowmode time is 6 hours (21600 seconds)!")

    await ctx.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        await ctx.send("✅ Slowmode disabled!")
    else:
        await ctx.send(f"✅ Set slowmode to {seconds} seconds! Nyaaa~ ⏳")
    await log_action("Slowmode", ctx.author, None, f"Set to {seconds}s in #{ctx.channel.name}")

@bot.command(name='lock', help='Locks a channel')
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 Channel locked! UwU be nice~ 💖")

@bot.command(name='unlock', help='Unlocks a channel')
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 Channel unlocked! Yayy~ 🎈")

@bot.command(name='nick', help='Changes a user\'s nickname')
@commands.has_permissions(manage_nicknames=True)
async def nick(ctx, member: discord.Member, *, new_nick: str = None):
    if not has_higher_role(ctx.author, member):
        return await ctx.send("❌ You can't change nickname of a user with equal or higher role!")

    try:
        await member.edit(nick=new_nick)
        if new_nick:
            await ctx.send(f"✅ Changed {member.mention}'s nickname to `{new_nick}`!")
            await log_action("Nick Change", ctx.author, member, f"New nickname: {new_nick}")
        else:
            await ctx.send(f"✅ Reset {member.mention}'s nickname!")
            await log_action("Nick Reset", ctx.author, member)
    except discord.Forbidden:
        await ctx.send("❌ No permissions to change this user's nickname!")

# Informational commands
@bot.command(name='userinfo', help='Shows user information')
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author

    roles = [role.mention for role in member.roles if role.name != "@everyone"]

    embed = discord.Embed(
        title=f"Info about {member.display_name} UwU~",
        color=member.color,
        timestamp=datetime.datetime.now(UTC)
    ).set_thumbnail(url=member.avatar.url)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Nickname", value=member.display_name, inline=True)
    embed.add_field(name="Account created", value=member.created_at.strftime("%d/%m/%Y %H:%M:%S"), inline=True)
    embed.add_field(name="Joined", value=member.joined_at.strftime("%d/%m/%Y %H:%M:%S"), inline=True)
    embed.add_field(name="Highest role", value=member.top_role.mention, inline=True)
    embed.add_field(name="Roles", value=", ".join(roles) if roles else "No roles", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='serverinfo', help='Shows server information')
async def serverinfo(ctx):
    guild = ctx.guild

    # Handle cases where some attributes might be None
    created_at = guild.created_at.strftime("%d/%m/%Y %H:%M:%S") if guild.created_at else "Unknown"
    member_count = guild.member_count if hasattr(guild, 'member_count') else len(guild.members)
    region = str(guild.region).title() if hasattr(guild, 'region') else "Unknown"
    
    embed = discord.Embed(
        title=f"Information about {guild.name}",
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.now(UTC)
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.add_field(name="ID", value=guild.id, inline=True)
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Region", value=region, inline=True)
    embed.add_field(name="Created", value=created_at, inline=True)
    embed.add_field(name="Member count", value=member_count, inline=True)
    embed.add_field(name="Channel count", value=len(guild.channels), inline=True)
    embed.add_field(name="Role count", value=len(guild.roles), inline=True)
    embed.add_field(name="Emoji count", value=len(guild.emojis), inline=True)
    embed.add_field(name="Boost level", value=guild.premium_tier, inline=True)
    embed.add_field(name="Boosts", value=guild.premium_subscription_count, inline=True)

    await ctx.send(embed=embed)

@bot.command(name='avatar', help='Shows user\'s avatar')
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author

    embed = discord.Embed(
        title=f"{member.display_name}'s avatar",
        color=member.color
    )
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)

    await ctx.send(embed=embed)

@bot.command(name='roleinfo', help='Shows information about a role')
async def roleinfo(ctx, role: discord.Role):
    embed = discord.Embed(
        title=f"Role: {role.name}",
        color=role.color,
        timestamp=datetime.datetime.now(UTC)
    )
    embed.add_field(name="ID", value=role.id, inline=True)
    embed.add_field(name="Color", value=str(role.color), inline=True)
    embed.add_field(name="Position", value=role.position, inline=True)
    embed.add_field(name="Hoisted", value=role.hoist, inline=True)
    embed.add_field(name="Mentionable", value=role.mentionable, inline=True)
    embed.add_field(name="Created at", value=role.created_at.strftime("%d/%m/%Y %H:%M:%S"), inline=True)
    embed.add_field(name="Members", value=len(role.members), inline=True)
    embed.add_field(name="Permissions", value=", ".join([perm for perm, value in role.permissions if value]), inline=False)

    await ctx.send(embed=embed)

# Utility commands
@bot.command(name='help', help='Shows all available commands', usage="[command]")
async def help_command(ctx):
    # Check permissions
    is_owner = ctx.author == ctx.guild.owner
    is_admin = any(role.permissions.administrator for role in ctx.author.roles) or is_owner
    is_mod = any(role.name == MOD_ROLE for role in ctx.author.roles) or is_admin
    
    # Permission checks
    has_kick = ctx.author.guild_permissions.kick_members or is_mod
    has_ban = ctx.author.guild_permissions.ban_members or is_mod
    has_manage_roles = ctx.author.guild_permissions.manage_roles or is_mod
    has_manage_msgs = ctx.author.guild_permissions.manage_messages or is_mod
    has_manage_channels = ctx.author.guild_permissions.manage_channels or is_mod
    has_manage_nicks = ctx.author.guild_permissions.manage_nicknames or is_mod
    has_moderate_members = ctx.author.guild_permissions.moderate_members or is_mod

    # Define all categories
    categories = {
        'ℹ️ Information': {
            'emoji': 'ℹ️',
            'description': 'General information commands',
            'color': 0x3498db,
            'commands': [
                ('userinfo [member]', 'Shows user information'),
                ('serverinfo', 'Displays server statistics'),
                ('avatar [member]', 'Shows user avatar'),
                ('roleinfo <role>', 'Shows role information'),
                ('ping', 'Shows bot latency'),
                ('emojiinfo', 'Shows emoji information (ID, creation date)'),
                ('uptime', 'Shows how long the bot has been online'),
                ('recentjoins', 'Shows recently joined members (last 10)', is_admin),
                ('hierarchy', 'Shows server hierarchy', has_moderate_members)
            ]
        },
        '🎮 Fun': {
            'emoji': '🎮',
            'description': 'Fun and entertainment commands',
            'color': 0xe91e63,
            'commands': [
                ('ship <user1> <user2>', 'Ship two users together'),
                ('8ball <question>', 'Ask the magic 8-ball'),
                ('hug <member>', 'Send virtual hug'),
                ('rate <thing>', 'Rate something 1-10'),
                ('rps <choice>', 'Play rock-paper-scissors'),
                ('random [min] [max]', 'Random number generator'),
                ('slap <user>', 'Virtual slap action'),
                ('simprate <user>', 'Checks how much a user simps'),
                ('howgay <user>', 'Measures gay percentage')
            ]
        },
        '🛡️ Moderation': {
            'emoji': '🛡️',
            'description': 'Server moderation tools',
            'color': 0xf1c40f,
            'commands': [
                ('kick <user> [reason]', 'Kicks a user', has_kick),
                ('ban <user> [duration] [reason]', 'Bans a user', has_ban),
                ('unban <user_id>', 'Unbans a user', has_ban),
                ('mute <user> [duration] [reason]', 'Mutes a user', has_manage_roles),
                ('unmute <user>', 'Unmutes a user', has_manage_roles),
                ('warn <user> [reason]', 'Warns a user', has_kick),
                ('warnings <user>', 'Shows user warnings', has_kick),
                ('clearwarns <user>', 'Clears user warnings', has_kick),
                ('delwarn <case_id>', 'Deletes specific warning', has_kick),
                ('editcase', 'Edit existing case', has_kick),
                ('case <case_id>', 'get info about case', has_kick),
                ('purge [amount=5]', 'Deletes messages', has_manage_msgs),
                ('slowmode <seconds>', 'Sets slowmode', has_manage_channels),
                ('lock', 'Locks a channel', has_manage_channels),
                ('unlock', 'Unlocks a channel', has_manage_channels),
                ('nick <user> [new_nick]', 'Changes nickname', has_manage_nicks),
                ('nuke', 'Deletes all messages in channel', has_manage_channels),
                ('fg', 'Toggles file and GIF sending permissions for a channel', has_manage_channels),
            ],
            'required_permissions': ['kick_members', 'ban_members', 'manage_roles']
        },
        '⚙️ Utilities': {
            'emoji': '⚙️',
            'description': 'Useful utility commands',
            'color': 0x2ecc71,
            'commands': [
                ('afk [reason]', 'Sets AFK status'),
                ('snipe', 'Shows last deleted message'),
                ('invite', 'Generates invite link'),
                ('embed <title> | <desc> | <#color> | [image] | [channel]', 'Creates embed (admin only)', is_admin),
                ('vote <question>', 'Creates poll'),
                ('lastfm <username>', 'Shows user statistics from Last.fm'),
                ('snipe', 'Shows last deleted message'),
                ('afk [reason]', 'Sets AFK status'),
                ('rmdm <time> <message>', 'Sets a reminder'),
                ('qr <text>', 'Generates QR code from text'),
                ('ascii <text>', 'Converts text to ASCII art'),
                ('color <name>', 'Shows color sample from HEX/name')
            ]
        },
        '🔧 Configuration': {
            'emoji': '🔧',
            'description': 'Server configuration commands',
            'color': 0x7289da,
            'commands': [
                ('prefix <prefix>', 'Changes the bot prefix for this server', is_admin),
                ('slc <channel>', 'Sets log channel', is_admin),
                ('sdlc <channel>', 'Sets deleted messages log', is_admin),
                ('swc <channel>', 'Sets welcome channel', is_admin),
                ('swm <message>', 'Sets welcome message', is_admin),
                ('say <message>', 'Sends message as bot', is_owner),
                ('autorole <roleID/rolemention>', 'Sets a role to be assigned automatically to new members', is_admin)
            ],
            'required_role': ADMIN_ROLE
        },
        '🎭 Roles': {
            'emoji': '🎭',
            'description': 'Role management commands',
            'color': 0x9b59b6,
            'commands': [
                ('addrole <user> <role>', 'Adds role to user', has_manage_roles),
                ('rmrole <user> <role>', 'Removes role from user', has_manage_roles),
                ('createrole <name> [color]', 'Creates new role', has_manage_roles),
                ('delrole <role>', 'Deletes a role', has_manage_roles),
                ('editrole <role> <new_name> [color] [icon]', 'Edits role name, color and icon', has_manage_roles),
                ('rr', 'Creates reaction role panel', has_manage_roles)
            ],
            'required_permissions': ['manage_roles']
        },
        '🎉 Giveaway': {
            'emoji': '🎉',
            'description': 'Giveaway management commands',
            'color': 0xf1c40f,
            'commands': [
                ('giveaway <duration> <prize>', 'Creates a new giveaway', has_manage_msgs),
                ('endgiveaway <giveaway_id>', 'Ends a giveaway and picks winner', has_manage_msgs),
                ('greroll <giveaway_id>', 'Rerolls a giveaway winner', has_manage_msgs)
            ],
            'required_permissions': ['manage_messages']
        },
        '🎫 Tickets': {
            'description': 'Ticket management commands',
            'color': discord.Color.green(),
            'commands': [
                ('st <channel>', 'Sets ticket channel'),
                ('addstaff <role>', 'Adds staff role to tickets'),
                ('rmstaff <role>', 'Removes staff role from tickets'),
                ('tlog <channel>', 'Sets ticket log channel')
            ]
        }
    }

    # Filter visible categories based on permissions
    visible_categories = {
        name: data for name, data in categories.items()
        if not data.get('required_role') and not data.get('required_permissions') or
           (data.get('required_role') and (is_mod or is_admin)) or
           (data.get('required_permissions') and any(getattr(ctx.author.guild_permissions, perm) for perm in data['required_permissions']))  # Kategorie wymagające uprawnień
    }

    # Filter commands in each category based on permissions
    for cat_name, cat_data in visible_categories.items():
        cat_data['commands'] = [
            cmd[:2] if len(cmd) <= 2 or cmd[2] else cmd[:2]
            for cmd in cat_data['commands']
        ]

    # Create dropdown menu
    class CategorySelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(
                    label=name.split(' ')[1],
                    emoji=name.split(' ')[0],
                    value=name,
                    description=data['description'][:50]
                )
                for name, data in visible_categories.items()
                if name != '🎫 Tickets' or ctx.author.guild_permissions.administrator or ctx.author == ctx.guild.owner
            ]
            super().__init__(placeholder="Select a category...", options=options)

        async def callback(self, interaction: discord.Interaction):
            selected_category = visible_categories[self.values[0]]
            embed = discord.Embed(
                title=f"{self.values[0]} Commands",
                description=selected_category['description'],
                color=selected_category['color']
            )
            
            for cmd in selected_category['commands']:
                embed.add_field(
                    name=f"`{PREFIX}{cmd[0]}`",
                    value=cmd[1],
                    inline=False
                )
            
            await interaction.response.edit_message(embed=embed)

    # Create view with dropdown
    class HelpView(discord.ui.View):
        def __init__(self):
            super().__init__()
            self.add_item(CategorySelect())

    # Create initial help embed
    embed = discord.Embed(
        title="📚 Bot Command Help ✨ UwU~",
        description=f"Click the dropdown below to select a category nyaa~ 🐾\n"
                   f"Total categories: {len(visible_categories)} | "
                   f"Total commands: {sum(len(cat['commands']) for cat in visible_categories.values())}",
        color=discord.Color.blue()
    )
    embed.set_footer(
        text=f"Requested by cutie {ctx.author.display_name}~",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)

    await ctx.send(embed=embed, view=HelpView())

@bot.command(name='ping', help='Shows bot ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)  # Convert to milliseconds
    embed = discord.Embed(
        title="🏓 UwU Pong!",
        description=f"Latency: **{latency}ms**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='say', help='Sends message as bot (admin only)')
@commands.has_permissions(administrator=True)
async def say(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message + " UwU said it! 🐾")

@bot.command(name='embed', 
             help='Creates embed\nFormat: title | description | #hexcolor | image_url | [channel]\nExample: ;embed Hello | Description | #ff0000 | https://i.imgur.com/xyz.jpg | #general',
             usage="title | description | #color | image_url | [channel]")
@commands.has_permissions(administrator=True)
async def embed(ctx, *, args):
    # Split arguments by | and strip whitespace
    args = [arg.strip() for arg in args.split('|')]
    if len(args) < 4:
        embed = discord.Embed(
            title="❌ Format Error (╯°□°）╯︵ ┻━┻",
            description="Right format: `title | description | #hexcolor | image_url | [channel]`",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    title = args[0]
    description = args[1]
    color = args[2]
    image_url = args[3]
    channel = ctx.channel

    if len(args) >= 5:
        channel_mention = args[4].strip()
        try:
            channel = await commands.TextChannelConverter().convert(ctx, channel_mention)
        except commands.ChannelNotFound:
            embed = discord.Embed(
                title="❌ Nie znaleziono kanału (´；ω；`)",
                description=f"Nie można znaleźć kanału: {channel_mention}",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

    try:
        embed = discord.Embed(title=title, description=description, color=discord.Color.from_str(color))
        embed.set_image(url=image_url)
        await channel.send(embed=embed)
        await ctx.send(f"✅ Embed wysłany na kanał: {channel.mention}")
    except Exception as e:
        embed = discord.Embed(
            title="❌ Wystąpił błąd (╥﹏╥)",
            description=f"Nie udało się wysłać embeda: {e}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command(name='invite', help='Generates invite')
async def invite(ctx):
    invite_link = await ctx.channel.create_invite(max_age=86400)  # 24 hours
    embed = discord.Embed(
        title="🔗 Invite Link UwU~",
        description=f"Here's your invite: {invite_link}\nShare it with friends! 🥰",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)

@bot.command(name='vote', help='Creates yes/no poll with optional duration (e.g., 30s, 5m, 1h)')
async def vote(ctx, duration: str = None, *, question):
    # Parse duration (e.g., "30s", "5m", "1h")
    duration_seconds = 0
    if duration:
        try:
            if duration.endswith('s'):
                duration_seconds = int(duration[:-1])
            elif duration.endswith('m'):
                duration_seconds = int(duration[:-1]) * 60
            elif duration.endswith('h'):
                duration_seconds = int(duration[:-1]) * 3600
            else:
                await ctx.send("Invalid time format. Use e.g., `30s`, `5m`, `1h`.")
                return
        except ValueError:
            await ctx.send("Invalid time format. Use e.g., `30s`, `5m`, `1h`.")
            return

    embed = discord.Embed(
        title="📊 Poll",
        description=question,
        color=0x2ecc71
    )
    embed.set_footer(text=f"Poll created by {ctx.author.display_name}")
    message = await ctx.send(embed=embed)
    await message.add_reaction("✅")  # Yes vote
    await message.add_reaction("❌")  # No vote

    if duration:
        await asyncio.sleep(duration_seconds)
        message = await ctx.channel.fetch_message(message.id)  # Refresh message to get reactions
        yes_votes = 0
        no_votes = 0
        for reaction in message.reactions:
            if reaction.emoji == "✅":
                yes_votes = reaction.count - 1  # Subtract 1 to exclude the bot's reaction
            elif reaction.emoji == "❌":
                no_votes = reaction.count - 1

        result_embed = discord.Embed(
            title="📊 Poll Results",
            description=f"**Question:** {question}\n\n"
                       f"✅ **Yes:** {yes_votes}\n"
                       f"❌ **No:** {no_votes}\n\n"
                       f"**Winner:** {'✅ Yes' if yes_votes > no_votes else '❌ No' if no_votes > yes_votes else 'Tie!'}",
            color=0x2ecc71
        )
        result_embed.set_footer(text="Poll ended")
        await message.reply(embed=result_embed)
        await message.clear_reactions()

@bot.command(name='random', help='Generates random number')
async def random_number(ctx, min_val: int = 1, max_val: int = 100):
    if min_val > max_val:
        embed = discord.Embed(
            title="❌ Oopsie! (´• ω •`)ﾉ",
            description="Minimum value must be less than or equal to maximum value!",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)
    
    num = random.randint(min_val, max_val)
    embed = discord.Embed(
        title="🎲 Random Number Generator",
        description=f"Your random number between {min_val} and {max_val} is:\n**{num}**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='8ball', help='Ask magic 8-ball a question')
async def eight_ball(ctx, *, question):
    responses = [
        "It is certain. UwU",
        "It is decidedly so. Nyaa~",
        "Without a doubt. (•̀ᴗ•́)و",
        "Yes - definitely. 🥰",
        "You may rely on it. 💕",
        "As I see it, yes. 👀",
        "Most likely. (¬‿¬)",
        "Outlook good. ✨",
        "Yes. 👍",
        "Signs point to yes. 🔮",
        "Reply hazy, try again. 🌫️",
        "Ask again later. ⏳",
        "Better not tell you now. 🤫",
        "Cannot predict now. 🌀",
        "Concentrate and ask again. 🧘",
        "Don't count on it. 🙅",
        "My reply is no. ❌",
        "My sources say no. 📡",
        "Outlook not so good. ☁️",
        "Very doubtful. 🤔"
        "As I see it... yes! 🌟",
        "No doubt about it! 🔮",
        "Better not tell you now... 🎱",
        "Absolutely not! ❌"
    ]
    response = random.choice(responses)
    embed = discord.Embed(
        title="🎱 UwU Magic 8-Ball",
        description=f"**Question:** {question}\n**Answer:** {response}",
        color=discord.Color.dark_blue()
    )
    await ctx.send(embed=embed)

@bot.command(name='slc', aliases=['setlogchannel'], help='Sets log channel')
@commands.has_permissions(administrator=True)
async def set_log_channel(ctx, channel: discord.TextChannel):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    config['log_channel_id'] = str(channel.id)
    
    config_path = get_guild_config_path(guild_id)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    
    await ctx.send(f"✅ UwU Log channel set to {channel.mention}")

@bot.command(name='sdlc', aliases=['setdeletedlogchannel'], help='Sets deleted messages log channel')
@commands.has_permissions(administrator=True)
async def set_deleted_log_channel(ctx, channel: discord.TextChannel):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    config['deleted_log_channel_id'] = str(channel.id)
    
    config_path = get_guild_config_path(guild_id)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    
    await ctx.send(f"✅ Deleted messages log channel set to {channel.mention}")

@bot.command(name='swc', aliases=['setwelcomechannel'], help='Sets welcome channel')
@commands.has_permissions(administrator=True)
async def set_welcome_channel(ctx, channel: discord.TextChannel):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    config['welcome_channel_id'] = str(channel.id)
    
    config_path = get_guild_config_path(guild_id)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    
    await ctx.send(f"✅ Welcome channel set to {channel.mention}")

def save_guild_config(guild_id, config):
    try:
        config_path = f"config/guild_{guild_id}.json"
        print(f"🔧 Saving config to {config_path}: {config}")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        print("✅ Config saved successfully!")
    except Exception as e:
        print(f"❌ Error saving config: {e}")

@bot.command(name='swm', aliases=['setwelcomemessage'], help='Sets custom welcome message')
@commands.has_permissions(administrator=True)
async def set_welcome_message(ctx, *, message: str = None):
    # Get current config
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    
    # If no message provided, show current settings
    if not message:
        current_channel = f"<#{config.get('welcome_channel_id')}>" if config.get('welcome_channel_id') else "Not set"
        current_message = config.get('welcome_message', "Not set")
        
        embed = discord.Embed(
            title="🎉 Current Welcome Settings",
            description="Configure how new members are welcomed!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📌 Welcome Channel",
            value=current_channel,
            inline=True
        )
        embed.add_field(
            name="📜 Current Message",
            value=f"```{current_message}```",
            inline=False
        )
        embed.add_field(
            name="ℹ️ Usage",
            value=(
                f"`{PREFIX}swm <message>` - Set new welcome message\n"
                f"`{PREFIX}swm reset` - Reset to default message\n"
                f"`{PREFIX}swc <channel>` - Set welcome channel"
            ),
            inline=False
        )
        embed.set_footer(text="Variables: {member.mention}, {member.name}, {guild.name}")
        return await ctx.send(embed=embed)
    
    # Handle reset
    if message.lower() == 'reset':
        config['welcome_message'] = "Welcome {member.mention} to {guild.name}!"
        save_guild_config(guild_id, config)
        return await ctx.send("✅ Welcome message reset to default!")
    
    # Validate message length
    if len(message) > 1000:
        return await ctx.send("❌ Message too long! Max 1000 characters.")
    
    # Set new message
    config['welcome_message'] = message
    save_guild_config(guild_id, config)
    
    # Create preview
    preview = message.replace('{member.mention}', ctx.author.mention) \
                    .replace('{member.name}', ctx.author.name) \
                    .replace('{guild.name}', ctx.guild.name)
    
    embed = discord.Embed(
        title="✅ Welcome Message Updated",
        description="New members will now see this message when they join:",
        color=discord.Color.green()
    )
    embed.add_field(
        name="📝 Preview",
        value=preview,
        inline=False
    )
    embed.add_field(
        name="📜 Raw Message",
        value=f"```{message}```",
        inline=False
    )
    embed.set_footer(text=f"Use {PREFIX}swc to set a welcome channel if not already set.")
    
    await ctx.send(embed=embed)

@bot.command(name='lastfm', help='Shows user statistics from Last.fm', usage="<username>",
             description="Displays Last.fm statistics for the specified user")
async def lastfm(ctx, username: str):
    message = await ctx.send("Loading Last.fm statistics...")
    if not LASTFM_API_KEY or LASTFM_API_KEY == "your_api_key":
        embed = discord.Embed(
            title="❌ Configuration Error",
            description="Last.fm is not properly configured!",
            color=0xFF0000
        )
        return await ctx.send(embed=embed)

    start_time = time.time()
        
    try:
        user = pylast.User(username, lastfm_network)
        
        # First, check the currently playing track
        now_playing = user.get_now_playing()
        
        # Download recently played songs (in case nothing is playing)
        recent_tracks = user.get_recent_tracks(limit=1)
        
        playcount = user.get_playcount()

        embed = discord.Embed(
            title=f"🎵 Last.fm Stats - {username}",
            url=f"https://www.last.fm/user/{username}",
            color=0xFF0000
        )
        
        if now_playing:
            embed.add_field(
                name="🎧 Now Playing",
                value=f"[{now_playing.title}]({now_playing.get_url()}) • {now_playing.artist}",
                inline=False
            )
        elif recent_tracks:
            embed.add_field(
                name="🎧 Last Played",
                value=f"[{recent_tracks[0].track.title}]({recent_tracks[0].track.get_url()}) • {recent_tracks[0].track.artist}",
                inline=False
            )
        else:
            embed.add_field(
                name="🎧 No Data",
                value="No recent tracks found",
                inline=False
            )
        
        embed.add_field(
            name="📊 Statistics",
            value=f"• **Total Scrobbles:** {playcount}",
            inline=False
        )
        
        async with ctx.typing():
            try:
                top_artists = user.get_top_artists(limit=5)
                artists_text = "\n".join(
                    [f"`{i+1}.` [{artist.item.name}]({artist.item.get_url()})" 
                     for i, artist in enumerate(top_artists)]
                )
                embed.add_field(
                    name="🌟 Top Artists",
                    value=artists_text,
                    inline=False
                )
            except Exception as e:
                print(f"Error getting top artists: {e}")
                embed.add_field(
                    name="🌟 Top Artists",
                    value="Could not load artist data",
                    inline=False
                )

        elapsed_time = time.time() - start_time
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name} • Fetched in {elapsed_time:.1f}s",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )

        await ctx.send(embed=embed)

    except pylast.WSError as e:
        embed = discord.Embed(
            title="❌ Last.fm Error",
            description=str(e),
            color=0xFF0000
        )
        await ctx.send(embed=embed)
    except IndexError:
        embed = discord.Embed(
            title="❌ No Data Found",
            description=f"No Last.fm data found for user **{username}**",
            color=0xFF0000
        )
        await ctx.send(embed=embed)

    await asyncio.sleep(5)

@bot.command(name='nuke', help='Deletes all messages in the channel UwU~')
@commands.has_permissions(manage_messages=True)
async def nuke(ctx):
    # Check if the channel is required for Community
    if ctx.guild.rules_channel == ctx.channel or ctx.guild.public_updates_channel == ctx.channel:
        embed = discord.Embed(
            title="❌ Cannot nuke this channel!",
            description="This channel is required for Community servers and cannot be deleted.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    # Rest of the code remains unchanged
    confirm_embed = discord.Embed(
        title="⚠️ Confirm Channel Nuke >w<",
        description="Are you sure you want to nuke this channel? This will delete ALL messages!",
        color=discord.Color.orange()
    )
    confirm_embed.set_footer(text="This action cannot be undone! UwU~")

    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30.0)
            self.value = None

        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="💣")
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            self.value = True
            self.stop()

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            self.value = False
            self.stop()

    view = ConfirmView()
    confirm_msg = await ctx.send(embed=confirm_embed, view=view)
    await view.wait()

    if view.value is None:
        timeout_embed = discord.Embed(
            title="⏰ Nuke Timed Out",
            description="Nuke timed out! Please try again if you really want to nuke this channel >w<",
            color=discord.Color.red()
        )
        await confirm_msg.edit(embed=timeout_embed, view=None)
    elif view.value:
        # Save original channel properties
        original_position = ctx.channel.position
        original_category = ctx.channel.category
        original_name = ctx.channel.name
        original_nsfw = getattr(ctx.channel, 'nsfw', False)
        original_slowmode = getattr(ctx.channel, 'slowmode_delay', 0)
        original_permissions = ctx.channel.overwrites
        
        # Only save topic for text channels
        if isinstance(ctx.channel, discord.TextChannel):
            original_topic = ctx.channel.topic
        else:
            original_topic = None

        # Clone channel with same properties
        new_channel = await ctx.channel.clone()
        await ctx.channel.delete()

        # Prepare edit kwargs
        edit_kwargs = {
            'position': original_position,
            'category': original_category,
            'name': original_name,
            'nsfw': original_nsfw,
            'slowmode_delay': original_slowmode,
            'overwrites': original_permissions
        }
        
        # Add topic only for text channels
        if original_topic is not None:
            edit_kwargs['topic'] = original_topic

        # Restore original properties
        await new_channel.edit(**edit_kwargs)

        # Send success message (only for text channels)
        if isinstance(new_channel, discord.TextChannel):
            success_embed = discord.Embed(
                title="💥 Channel Nuked Successfully!",
                description=">w< All messages have been purged! So clean now~ ✨",
                color=discord.Color.green()
            )
            await new_channel.send(embed=success_embed)
        
        await log_action("Nuke", ctx.author, None, f"Channel #{original_name} nuked")
    else:
        cancel_embed = discord.Embed(
            title="❌ Nuke Cancelled",
            description="Nuke cancelled! UwU channel is safe~ 🥺",
            color=discord.Color.blue()
        )
        await confirm_msg.edit(embed=cancel_embed, view=None)

@bot.command(name='snipe', help='Shows the last deleted message nya~')
async def snipe(ctx):
    # Filter messages marked as deleted and from the same channel
    deleted_messages = [
        msg for msg in message_cache.values() 
        if msg.get("deleted", False) and msg["channel"].id == ctx.channel.id
    ]
    
    if not deleted_messages:
        embed = discord.Embed(
            title="🔍 No deleted messages found! (´• ω •`)ﾉ",
            description=">w< Couldn't find any recently deleted messages in this channel~ Try again later!",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    # Sort from newest to oldest
    deleted_messages.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Get the latest message
    latest_message = deleted_messages[0]
    author = latest_message["author"]
    content = latest_message["content"]
    timestamp = latest_message["timestamp"].strftime("%d/%m/%Y %H:%M:%S")

    # List of fun titles with emoji/kaomoji
    fun_titles = [
        "🔍 Oopsie! Someone deleted this! (╯°□°）╯︵ ┻━┻",
        "🐾 Nyaa~ Found a secret message! (≧◡≦)",
        "👀 Sneaky sneaky! (¬‿¬)",
        "💥 Boom! Deleted message exposed! (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
        "🕵️‍♂️ Detective bot on the case! (•̀ᴗ•́)و"
    ]

    embed = discord.Embed(
        title=random.choice(fun_titles),  # Random title from the list
        description=f"> **Author:** {author.mention}\n> **Time:** {timestamp}",
        color=discord.Color.green()
    )
    
    if content:
        embed.add_field(name="📜 Content", value=f"```\n{content[:1024]}\n```", inline=False)
    
    if latest_message["attachments"]:
        attachments_text = "\n".join([f"[{att.filename}]({att.url})" for att in latest_message["attachments"]])
        embed.add_field(name="📎 Attachments", value=attachments_text[:1024], inline=False)

    # Add reactions
    message = await ctx.send(embed=embed)
    await message.add_reaction("😂")
    await message.add_reaction("😱")
    await message.add_reaction("👀")
    await message.add_reaction('🌸')  # One extra reaction

@bot.command(name='afk', help='Sets AFK (Away From Keyboard) status')
async def afk(ctx, *, reason="No reason provided"):
    user_id = ctx.author.id
    afk_users[user_id] = {
        "reason": reason,
        "timestamp": datetime.datetime.now(UTC),
        "message_id": None  # Add AFK message ID
    }
    
    embed = discord.Embed(
        title="⏸️ AFK Status Set",
        description=f"{ctx.author.mention} is now AFK!\n**Reason:** {reason}",
        color=discord.Color.orange()
    )
    message = await ctx.send(embed=embed)
    afk_users[user_id]["message_id"] = message.id  # Save AFK message ID

@bot.command(name='ship', help='Ship two users together! UwU~', usage="<user1> <user2>")
async def ship(ctx, user1: discord.Member, user2: discord.Member):
    # Random compatibility percentage
    compatibility = random.randint(0, 100)
    
    # List of descriptions based on the result
    descriptions = [
        "💔 Total disaster! Maybe next time...",
        "😬 Not the best match, but who knows?",
        "🤔 Could work... or not?",
        "💕 Pretty good match! Cute~",
        "🔥 Perfect match! So adorable together! UwU",
        "💖 Soulmates! Absolutely meant to be! Nyaa~"
    ]
    
    # Choose description based on the result
    if compatibility < 20:
        description = descriptions[0]
    elif compatibility < 40:
        description = descriptions[1]
    elif compatibility < 60:
        description = descriptions[2]
    elif compatibility < 80:
        description = descriptions[3]
    elif compatibility < 95:
        description = descriptions[4]
    else:
        description = descriptions[5]
    
    # Generate ship name (e.g. "Brangelina")
    ship_name = f"{user1.display_name[:3]}{user2.display_name[-3:]}".capitalize()
    
    # Create embed
    embed = discord.Embed(
        title=f"💘 SHIPPING REPORT: {ship_name}",
        color=discord.Color.pink(),
        timestamp=datetime.datetime.now(UTC)
    )
    
    # Header with avatars
    embed.set_author(
        name=f"{user1.display_name} ❤️ {user2.display_name}",
        icon_url=user1.avatar.url if user1.avatar else user1.default_avatar.url
    )
    
    # Simpler and more readable compatibility meter
    hearts = "❤️" * (compatibility // 20)  # Full hearts every 20%
    empty_hearts = "🤍" * (5 - (compatibility // 20))  # Empty hearts
    embed.add_field(
        name="🔥 CHEMISTRY METER",
        value=(
            f"**{compatibility}% Match**\n"
            f"{hearts}{empty_hearts}\n"
            f"```\n"
            f"[{'█' * (compatibility // 5)}{' ' * (20 - (compatibility // 5))}]\n"
            f"```\n"
            f"**Verdict:** {description}"
        ),
        inline=False
    )
    
    # Extended list of fun facts
    date_ideas = [
        "Romantic candlelit dinner 🕯️",
        "Adventure in an amusement park 🎢",
        "Cozy movie night with popcorn 🍿",
        "Sunset walk on the beach 🌅",
        "Cooking class together 👩‍🍳",
        "Stargazing picnic ✨",
        "Exploring a new city 🏙️",
        "Board game marathon 🎲"
    ]
    
    songs = [
        "Love Story by Taylor Swift 🎤",
        "Perfect by Ed Sheeran 🎸",
        "All of Me by John Legend 🎹",
        "Just the Way You Are by Bruno Mars 🎶",
        "Thinking Out Loud by Ed Sheeran 💕",
        "A Thousand Years by Christina Perri 🎼",
        "Can't Help Falling in Love by Elvis Presley 🎧",
        "You Are the Reason by Calum Scott 🎵"
    ]
    
    kids = [
        "Adorable little geniuses 🧠",
        "Creative artists 🎨",
        "Energetic athletes 🏃",
        "Musical prodigies 🎻",
        "Little scientists 🔬",
        "Future astronauts 🚀",
        "Adventurous explorers 🗺️",
        "Kind-hearted helpers 🤗"
    ]
    
    # Add fun facts in a better format
    embed.add_field(
        name="💑 RELATIONSHIP POTENTIAL",
        value=(
            f"📅 **First Date:** {random.choice(date_ideas)}\n"
            f"🎵 **Their Song:** {random.choice(songs)}\n"
            f"👨‍👩‍👧‍👦 **Future Kids:** {random.choice(kids)}"
        ),
        inline=False
    )
    
    # Add footer
    embed.set_footer(
        text=f"💖 Shipped by {ctx.author.display_name} • {datetime.datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )
    
    await ctx.send(embed=embed)

def ensure_config_folder():
    """Creates the 'config' folder if it doesn't exist."""
    if not os.path.exists("config"):
        os.makedirs("config")

def get_guild_config_path(guild_id):
    """Returns the path to the config file for a given server."""
    return f"config/guild_{guild_id}.json"

def load_guild_config(guild_id):
    """Loads the config for a given server or creates a new one if the file doesn't exist."""
    ensure_config_folder()  # Ensure the folder exists
    config_path = f"config/guild_{guild_id}.json"
    default_config = {
        "token": TOKEN,
        "prefix": PREFIX,
        "log_channel_id": None,
        "deleted_log_channel_id": None,
        "welcome_channel_id": None,
        "welcome_message": "Welcome on the server, {member.mention}! 🎉",
    }

    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=4)
        return default_config
    else:
        with open(config_path, "r") as f:
            return json.load(f)

def ensure_warnings_folder():
    """Creates the 'warnings' folder if it doesn't exist."""
    if not os.path.exists("warnings"):
        os.makedirs("warnings")

def get_guild_warnings_path(guild_id):
    """Returns the path to the warnings file for a given server in the 'warnings' folder."""
    return f"warnings/guild_{guild_id}.json"

def load_guild_warnings(guild_id):
    """Loads the warnings for a given server or creates a new file if it doesn't exist."""
    ensure_warnings_folder()  # Ensure the folder exists
    warnings_path = get_guild_warnings_path(guild_id)
    default_warnings = {}

    if not os.path.exists(warnings_path):
        with open(warnings_path, "w") as f:
            json.dump(default_warnings, f, indent=4)
        return default_warnings
    else:
        with open(warnings_path, "r") as f:
            return json.load(f)

def save_guild_warnings(guild_id, warnings):
    """Saves the warnings for a given server."""
    ensure_warnings_folder()  # Ensure the folder exists
    warnings_path = get_guild_warnings_path(guild_id)
    with open(warnings_path, "w") as f:
        json.dump(warnings, f, indent=4)

@bot.command(name='rate', help='Rates something 1-10 with stars ✨', usage="<thing>")
async def rate(ctx, *, thing: str):
    rating = random.randint(1, 10)
    stars = "⭐" * rating + "☆" * (10 - rating)
    reactions = ["💖", "✨", "🌟", "😍", "🥰"]
    
    embed = discord.Embed(
        title=f"Rating for {thing}",
        description=f"I rate this **{rating}/10**!\n{stars}",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Rated by {ctx.author.display_name}")
    
    msg = await ctx.send(embed=embed)
    await msg.add_reaction(random.choice(reactions))

@bot.command(name='hug', help='Sends virtual hugs 💖', usage="<member>")
async def hug(ctx, member: discord.Member):
    # List of hugs with simple English descriptions
    hug_types = [
        {"url": "https://c.tenor.com/J7eGDvGeP9IAAAAd/tenor.gif", "description": "### Warm hug! (◕‿◕)"},
        {"url": "https://c.tenor.com/sJATVEhZ_VMAAAAd/tenor.gif", "description": "### Big strong hug! ⊂(◉‿◉)つ"},
        {"url": "https://c.tenor.com/wWFm70VeC7YAAAAd/tenor.gif", "description": "### Gentle embrace~"},
        {"url": "https://c.tenor.com/tbzuQSodu58AAAAd/tenor.gif", "description": "### Heartfelt hug 💕"},
        {"url": "https://c.tenor.com/7f9CqFtd4SsAAAAd/tenor.gif", "description": "### Goodnight hug 🌙"},
        {"url": "https://c.tenor.com/d0AdL1hRqcIAAAAC/tenor.gif", "description": "### Sweet cuddle (｡♡‿♡｡)"},
        {"url": "https://c.tenor.com/W9Z5NRF2DJ4AAAAC/tenor.gif", "description": "### Joyful squeeze!"},
        {"url": "https://c.tenor.com/cBcV5uqNYvYAAAAC/tenor.gif", "description": "### Comfy blanket hug 🧸"},
        {"url": "https://c.tenor.com/P-8xYwXoGX0AAAAC/tenor.gif", "description": "### Excited jump hug! (ﾉ^ヮ^)ﾉ"},
        {"url": "https://c.tenor.com/wUQH5CF2DJ4AAAAd/tenor.gif", "description": "### Surprise hug attack!"}
    ]
    
    selected_hug = random.choice(hug_types)
    
    embed = discord.Embed(
        title=f"{ctx.author.display_name} hugs {member.display_name}!",
        description=f"{selected_hug['description']}",
        color=discord.Color.pink()
    )
    embed.set_image(url=selected_hug["url"])
    embed.set_footer(text="Sent by your best bot! ✨")
    
    msg = await ctx.send(embed=embed)
    await msg.add_reaction('💕')

@bot.command(name='rps', help='Play rock-paper-scissors ✨', usage="<rock|paper|scissors>")
async def rps(ctx, choice: str):
    # Normalize player's choice
    choice = choice.lower()
    if choice not in ['rock', 'paper', 'scissors']:
        return await ctx.send("❌ Invalid choice! Use `rock`, `paper` or `scissors` UwU~")

    # Bot's choice
    bot_choice = random.choice(['rock', 'paper', 'scissors'])
    
    # Game logic
    if choice == bot_choice:
        result = "It's a tie! (◕‿◕)"
    elif (choice == 'rock' and bot_choice == 'scissors') or \
         (choice == 'paper' and bot_choice == 'rock') or \
         (choice == 'scissors' and bot_choice == 'paper'):
        result = "You win! Nyaa~ (≧◡≦)"
    else:
        result = "I win! UwU (¬‿¬)"

    # Emojis for choices
    emojis = {
        'rock': '🪨',
        'paper': '📄',
        'scissors': '✂️'
    }

    # Create embed
    embed = discord.Embed(
        title="🎮 Rock Paper Scissors",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="Your choice",
        value=f"{emojis[choice]} {choice.capitalize()}",
        inline=True
    )
    embed.add_field(
        name="Bot's choice",
        value=f"{emojis[bot_choice]} {bot_choice.capitalize()}",
        inline=True
    )
    embed.add_field(
        name="Result",
        value=f"**{result}**",
        inline=False
    )
    embed.set_footer(text=f"Played by {ctx.author.display_name}")

    await ctx.send(embed=embed)

@bot.command(name='addrole', help='Adds a role to a user', usage="<member> <role>")
@commands.has_permissions(manage_roles=True)
async def addrole(ctx, member: discord.Member, role: discord.Role):
    if not has_higher_role(ctx.author, member):
        embed = discord.Embed(
            title="❌ Oopsie! Permission Denied~",
            description="You can't add roles to users with equal or higher role! Nyaa~ 😿",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)
    if ctx.guild.me.top_role.position <= role.position:
        embed = discord.Embed(
            title="❌ Oh no! My role is too low~",
            description="I can't add this role because it's higher than mine! (╥﹏╥)",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    await member.add_roles(role)
    embed = discord.Embed(
        title="🎀 Role Added Successfully!",
        description=f"Added {role.mention} to {member.display_name}~ UwU so cute! 💕",
        color=discord.Color.pink()
    )
    embed.set_footer(text=f"Action by {ctx.author.display_name} • ≧◡≦")
    await ctx.send(embed=embed)
    await log_action("Add Role", ctx.author, member, f"Role: {role.name}")

@bot.command(name='rmrole', help='Removes a role from a user', usage="<member> <role>")
@commands.has_permissions(manage_roles=True)
async def rmrole(ctx, member: discord.Member, role: discord.Role):
    if not has_higher_role(ctx.author, member):
        embed = discord.Embed(
            title="❌ Nyaa~ Permission Denied!",
            description="You can't remove roles from users with equal or higher role! (´• ω •`)",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)
    if ctx.guild.me.top_role.position <= role.position:
        embed = discord.Embed(
            title="❌ Oh my! My role is too low~",
            description="I can't remove this role because it's higher than mine! (╯︵╰,)",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    await member.remove_roles(role)
    embed = discord.Embed(
        title="🌸 Role Removed Successfully!",
        description=f"Removed {role.mention} from {member.display_name}~ Bye-bye role! 👋💫",
        color=discord.Color.pink()
    )
    embed.set_footer(text=f"Action by {ctx.author.display_name} • (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧")
    await ctx.send(embed=embed)
    await log_action("Remove Role", ctx.author, member, f"Role: {role.name}")

@bot.command(name='createrole', help='Creates a new cute role~ UwU', usage="<name> [hex_color]")
@commands.has_permissions(manage_roles=True)
async def createrole(ctx, name: str, color: str = None):
    try:
        role_color = discord.Color.default()
        if color:
            if color.startswith('#'):
                role_color = discord.Color(int(color[1:], 16))
            else:
                embed = discord.Embed(
                    title="❌ Oopsie! Wrong color format~",
                    description="Please use a hex color like `#FFC0CB` for pink! (◕‿◕✿)",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)

        new_role = await ctx.guild.create_role(
            name=name,
            color=role_color,
            reason=f"Created by {ctx.author}"
        )
        
        embed = discord.Embed(
            title="🎀 New Role Created! Kawaii~",
            description=f"Yay! New role {new_role.mention} was born! (ﾉ´ヮ`)ﾉ*: ･ﾟ",
            color=role_color
        )
        embed.add_field(name="✨ Name", value=f"`{name}`", inline=True)
        if color:
            embed.add_field(name="🎨 Color", value=f"`{color}`", inline=True)
        embed.set_thumbnail(url="https://i.imgur.com/J7eGDvG.png")  # Cute emoji
        embed.set_footer(text=f"Created by {ctx.author.display_name} • So adorable~")
        
        await ctx.send(embed=embed)
        await log_action("Create Role", ctx.author, None, f"Role: {name}")

    except discord.Forbidden:
        embed = discord.Embed(
            title="🔒 Oh no! Missing Permissions~",
            description="I don't have permissions to create roles! (╥﹏╥)",
            color=discord.Color.red()
        )
        embed.add_field(
            name="How to fix it:",
            value=(
                "1. Give me **Manage Roles** permission\n"
                "2. Put my role higher up\n"
                "3. Make sure I can edit this channel\n"
                "4. Pretty please? 🥺"
            ),
            inline=False
        )
        await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="❌ Oh nyo! An error occurred~",
            description="Something went wrong while creating the role (´；ω；`)",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Details",
            value=f"```{str(e)[:1000]}```",
            inline=False
        )
        await ctx.send(embed=embed)

@bot.command(name='delrole', help='Deletes a role', usage="<role>")
@commands.has_permissions(manage_roles=True)
async def delrole(ctx, role: discord.Role):
    try:
        # Check permissions
        if not has_higher_role(ctx.author, ctx.guild.me):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="I can't delete roles higher than mine!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
            
        if ctx.guild.me.top_role.position <= role.position:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="My role is too low to delete this role!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Confirmation embed
        confirm_embed = discord.Embed(
            title="⚠️ Confirm Role Deletion",
            description=f"Are you sure you want to delete role {role.mention}?",
            color=discord.Color.orange()
        )
        confirm_embed.add_field(name="Role Name", value=role.name, inline=True)
        confirm_embed.add_field(name="Member Count", value=len(role.members), inline=True)
        confirm_embed.set_footer(text="This action cannot be undone!")

        # Buttons
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30.0)
                self.value = None

            @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.defer()
                self.value = True
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.defer()
                self.value = False
                self.stop()

        view = ConfirmView()
        confirm_msg = await ctx.send(embed=confirm_embed, view=view)
        
        # Wait for response
        await view.wait()
        
        if view.value is None:
            await confirm_msg.edit(embed=discord.Embed(
                title="⌛ Timeout",
                description="Role deletion cancelled due to no response.",
                color=discord.Color.light_grey()
            ), view=None)
        elif view.value:
            # Delete role
            await role.delete(reason=f"Deleted by {ctx.author}")
            
            success_embed = discord.Embed(
                title="✅ Role Deleted",
                description=f"Successfully deleted role **{role.name}**",
                color=discord.Color.green()
            )
            await confirm_msg.edit(embed=success_embed, view=None)
            await log_action("Delete Role", ctx.author, None, f"Role: {role.name}")
        else:
            await confirm_msg.edit(embed=discord.Embed(
                title="❌ Cancelled",
                description="Role deletion cancelled.",
                color=discord.Color.red()
            ), view=None)

    except discord.Forbidden:
        embed = discord.Embed(
            title="🔒 Missing Permissions",
            description="I don't have required permissions to delete roles!",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Required Permissions",
            value="• Manage Roles\n• Higher role position than target role",
            inline=False
        )
        await ctx.send(embed=embed)
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error Occurred",
            description=f"An error occurred while trying to delete the role:",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Details",
            value=f"```{str(e)[:1000]}```",
            inline=False
        )
        await ctx.send(embed=embed)

@bot.command(name='editrole', help='Edits a role (name, color, or icon)', usage="<role> [new_name] [new_color] [new_icon_url]")
@commands.has_permissions(manage_roles=True)
async def editrole(
    ctx, 
    role: discord.Role, 
    new_name: str = None, 
    new_color: str = None, 
    new_icon_url: str = None
):
    try:
        # Check if the bot can edit this role
        if ctx.guild.me.top_role.position <= role.position:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="My role is too low to edit this role!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Prepare changes
        changes = []
        kwargs = {}

        # Name change
        if new_name:
            kwargs["name"] = new_name
            changes.append(f"**Name:** `{role.name}` → `{new_name}`")

        # Color change
        if new_color:
            if new_color.startswith('#'):
                try:
                    kwargs["color"] = discord.Color(int(new_color[1:], 16))
                    changes.append(f"**Color:** `{role.color}` → `{new_color}`")
                except ValueError:
                    embed = discord.Embed(
                        title="❌ Invalid Color",
                        description="Please use a valid hex color (e.g., `#FF0000`).",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Invalid Color Format",
                    description="Please use a hex color (e.g., `#FF0000`).",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)

        # Icon change
        if new_icon_url:
            if new_icon_url.lower() == "none":
                kwargs["icon"] = None
                changes.append("**Icon:** Removed")
            elif new_icon_url.startswith(('http://', 'https://')):
                kwargs["icon"] = await get_icon_from_url(new_icon_url)
                changes.append("**Icon:** Updated")
            else:
                embed = discord.Embed(
                    title="❌ Invalid Icon URL",
                    description="Please provide a valid image URL or `none` to remove.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)

        # If no changes were requested
        if not changes:
            embed = discord.Embed(
                title="⚠️ No Changes Specified",
                description="Please provide at least one change (name, color, or icon).",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Usage",
                value=f"`{PREFIX}editrole <role> [new_name] [new_color] [new_icon_url]`",
                inline=False
            )
            return await ctx.send(embed=embed)

        # Apply changes
        await role.edit(**kwargs)

        # Create success embed
        embed = discord.Embed(
            title=f"✅ Role Updated: {role.name}",
            description="\n".join(changes),
            color=role.color
        )
        if new_icon_url and new_icon_url.lower() != "none":
            embed.set_thumbnail(url=new_icon_url)
        embed.set_footer(text=f"Edited by {ctx.author.display_name}")

        await ctx.send(embed=embed)
        await log_action("Edit Role", ctx.author, None, f"Role: {role.name}")

    except discord.Forbidden:
        embed = discord.Embed(
            title="🔒 Missing Permissions",
            description="I don't have permission to edit roles!",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Required Permissions",
            value="• Manage Roles\n• Higher role position than target role",
            inline=False
        )
        await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error Editing Role",
            description=f"An error occurred:",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Details",
            value=f"```{str(e)[:1000]}```",
            inline=False
        )
        await ctx.send(embed=embed)

async def get_icon_from_url(url):
    """Helper function to download role icon from URL"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
    return None

@bot.command(name='rr', help='Creates a reaction role panel', usage="[channel]")
@commands.has_permissions(manage_roles=True)
async def reaction_role(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel

    class SetupView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180.0)
            self.title = None
            self.description = None
            self.reactions = {}
            self.target_channel = channel
            self.add_item(SetupSelect())

    class SetupSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="Set Title", description="Set panel title", emoji="📝"),
                discord.SelectOption(label="Set Description", description="Set panel description", emoji="📄"),
                discord.SelectOption(label="Add Reaction", description="Add reaction-role pair", emoji="➕"),
                discord.SelectOption(label="Remove Reaction", description="Remove reaction-role pair", emoji="➖"),  # Nowa opcja
                discord.SelectOption(label="Set Channel", description="Select target channel", emoji="📌"),
                discord.SelectOption(label="Send Panel", description="Publish the panel", emoji="🚀")
            ]
            super().__init__(placeholder="Select an action...", options=options)

        async def callback(self, interaction: discord.Interaction):
            if self.values[0] == "Set Title":
                modal = discord.ui.Modal(title="Set Panel Title")
                title_input = discord.ui.TextInput(label="Title", placeholder="Enter title...")
                modal.add_item(title_input)
                
                async def on_submit(interaction: discord.Interaction):
                    self.view.title = title_input.value
                    await interaction.response.edit_message(embed=self.view.update_embed())
                
                modal.on_submit = on_submit
                await interaction.response.send_modal(modal)

            elif self.values[0] == "Set Description":
                modal = discord.ui.Modal(title="Set Description")
                desc_input = discord.ui.TextInput(label="Description", style=discord.TextStyle.long, required=False)
                modal.add_item(desc_input)
                
                async def on_submit(interaction: discord.Interaction):
                    self.view.description = desc_input.value
                    await interaction.response.edit_message(embed=self.view.update_embed())
                
                modal.on_submit = on_submit
                await interaction.response.send_modal(modal)

            elif self.values[0] == "Add Reaction":
                modal = discord.ui.Modal(title="Add Reaction-Role Pair")
                emoji_input = discord.ui.TextInput(label="Emoji")
                role_input = discord.ui.TextInput(label="Role (name or ID)")
                modal.add_item(emoji_input)
                modal.add_item(role_input)
                
                async def on_submit(interaction: discord.Interaction):
                    try:
                        role = await commands.RoleConverter().convert(interaction, role_input.value)
                        self.view.reactions[emoji_input.value] = role.id
                        await interaction.message.edit(embed=self.view.update_embed())
                        await interaction.response.send_message(
                            f"✅ Added reaction {emoji_input.value} for role {role.name}",
                            ephemeral=True
                        )
                    except Exception as e:
                        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
                
                modal.on_submit = on_submit
                await interaction.response.send_modal(modal)

            elif self.values[0] == "Remove Reaction":
                if not self.view.reactions:
                    return await interaction.response.send_message("❌ No reactions to remove!", ephemeral=True)

                class RemoveReactionView(discord.ui.View):
                    def __init__(self, parent_view):
                        super().__init__(timeout=60.0)
                        self.parent_view = parent_view
                        self.add_item(RemoveReactionSelect(self))

                class RemoveReactionSelect(discord.ui.Select):
                    def __init__(self, parent_view):
                        options = []
                        for emoji, role_id in parent_view.parent_view.reactions.items():
                            role = interaction.guild.get_role(role_id)
                            if role:
                                options.append(discord.SelectOption(
                                    label=f"{emoji} → {role.name}",
                                    value=emoji
                                ))
                        
                        super().__init__(
                            placeholder="Select reaction to remove...", 
                            options=options,
                            min_values=1,
                            max_values=1
                        )
                        self.parent_view = parent_view
                        self.original_message = interaction.message

                    async def callback(self, interaction: discord.Interaction):
                        try:
                            emoji = self.values[0]
                            if emoji not in self.parent_view.parent_view.reactions:
                                return await interaction.response.send_message("❌ Reaction not found!", ephemeral=True)
                                
                            role_id = self.parent_view.parent_view.reactions[emoji]
                            role = interaction.guild.get_role(role_id)
                            del self.parent_view.parent_view.reactions[emoji]
                            
                            try:
                                await self.original_message.edit(embed=self.parent_view.parent_view.update_embed())
                                
                                await interaction.response.edit_message(
                                    content=f"✅ Removed reaction {emoji} for role {role.name}",
                                    view=None
                                )
                            except discord.NotFound:
                                new_msg = await interaction.channel.send(
                                    embed=self.parent_view.parent_view.update_embed()
                                )
                                await interaction.response.edit_message(
                                    content=f"✅ Removed reaction {emoji} for role {role.name}\n"
                                            f"Original message was lost, created new panel: {new_msg.jump_url}",
                                    view=None
                                )
                            except Exception as e:
                                print(f"Error updating message: {e}")
                                await interaction.response.send_message(
                                    f"✅ Removed reaction {emoji} but failed to update panel: {str(e)}",
                                    ephemeral=True
                                )
                                
                        except Exception as e:
                            print(f"Error removing reaction: {e}")
                            await interaction.response.send_message(
                                f"❌ Failed to remove reaction: {str(e)}",
                                ephemeral=True
                            )

                view = RemoveReactionView(self.view)
                await interaction.response.send_message(
                    "Select reaction to remove:",
                    view=view,
                    ephemeral=True
                )

            elif self.values[0] == "Set Channel":
                class ChannelSelectView(discord.ui.View):
                    def __init__(self, parent_view):
                        super().__init__(timeout=60.0)
                        self.parent_view = parent_view
                        
                        # Dodajemy selektor kanałów
                        self.select = discord.ui.ChannelSelect(
                            placeholder="Wybierz kanał...",
                            channel_types=[discord.ChannelType.text],
                            custom_id=f"channel_select_{int(time.time())}"
                        )
                        self.add_item(self.select)

                    async def on_timeout(self):
                        if hasattr(self, 'message'):
                            await self.message.edit(content="⏰ Czas na wybór minął!", view=None)

                    async def interaction_check(self, interaction: discord.Interaction) -> bool:
                        try:
                            selected_channel = self.select.values[0]
                            channel = interaction.guild.get_channel(selected_channel.id)
                            
                            if not channel:
                                await interaction.response.send_message("❌ Nie znaleziono kanału!", ephemeral=True)
                                return False
                                
                            if not isinstance(channel, discord.TextChannel):
                                await interaction.response.send_message("❌ To nie jest kanał tekstowy!", ephemeral=True)
                                return False
                            
                            self.parent_view.target_channel = channel
                            
                            await interaction.response.edit_message(
                                content=f"✅ Wybrano kanał: {channel.mention}",
                                view=None
                            )
                            self.stop()
                            return True
                                
                        except Exception as e:
                            await interaction.response.send_message(f"❌ Błąd: {str(e)}", ephemeral=True)
                            return False

                view = ChannelSelectView(self.view)
                view.message = await interaction.response.send_message(
                    "Wybierz kanał dla panelu reakcji:",
                    view=view,
                    ephemeral=True
                )

            elif self.values[0] == "Send Panel":
                if not self.view.title:
                    return await interaction.response.send_message("❌ Title is required!", ephemeral=True)
                if not self.view.reactions:
                    return await interaction.response.send_message("❌ Add at least one reaction!", ephemeral=True)
                
                embed = discord.Embed(
                    title=self.view.title,
                    color=discord.Color.blurple()
                )
                
                if self.view.description:
                    embed.description = self.view.description
                
                embed.add_field(
                    name="Available Roles",
                    value="\n".join(f"{emoji} → <@&{role_id}>" for emoji, role_id in self.view.reactions.items()),
                    inline=False
                )
                
                try:
                    msg = await self.view.target_channel.send(embed=embed)
                    for emoji in self.view.reactions.keys():
                        await msg.add_reaction(emoji)
                    
                    guild_id = str(interaction.guild.id)
                    message_id = str(msg.id)
                    
                    if guild_id not in bot.reaction_roles:
                        bot.reaction_roles[guild_id] = {}
                    
                    bot.reaction_roles[guild_id][message_id] = self.view.reactions
                    save_reaction_roles()
                    
                    await interaction.response.send_message(f"✅ Panel sent to {self.view.target_channel.mention}!", ephemeral=True)
                    self.view.stop()
                except Exception as e:
                    await interaction.response.send_message(f"❌ Failed to send panel: {str(e)}", ephemeral=True)

    def update_embed(view):
        embed = discord.Embed(
            title="🎭 Reaction Role Setup",
            description="Use the dropdown below to configure the panel",
            color=discord.Color.blue()
        )
        if view.title:
            embed.add_field(name="Title", value=view.title, inline=False)
        if view.description:
            embed.add_field(name="Description", value=view.description, inline=False)
        if view.reactions:
            embed.add_field(
                name="Reaction Roles", 
                value="\n".join(f"{emoji} → <@&{role_id}>" for emoji, role_id in view.reactions.items()),
                inline=False
            )
        embed.add_field(
            name="Target Channel",
            value=view.target_channel.mention if view.target_channel else "Not set",
            inline=False
        )
        return embed

    view = SetupView()
    view.update_embed = lambda: update_embed(view)
    await ctx.send(embed=update_embed(view), view=view)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.member and payload.member.bot:
                    return
                    
    guild_id = str(payload.guild_id)
    message_id = str(payload.message_id)
    
    if guild_id not in bot.reaction_roles or message_id not in bot.reaction_roles[guild_id]:
        return

    emoji = str(payload.emoji)
    role_id = bot.reaction_roles[guild_id][message_id].get(emoji)

    if role_id:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(int(role_id))
        member = guild.get_member(payload.user_id)
        
        if role and guild.me.top_role.position > role.position:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                pass

@bot.event
async def on_raw_reaction_remove(payload):
    guild_id = str(payload.guild_id)
    message_id = str(payload.message_id)
    
    if guild_id not in bot.reaction_roles or message_id not in bot.reaction_roles[guild_id]:
        return

    emoji = str(payload.emoji)
    role_id = bot.reaction_roles[guild_id][message_id].get(emoji)

    if role_id:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(int(role_id))
        member = guild.get_member(payload.user_id)
        
        if role and guild.me.top_role.position > role.position:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                pass

GIVEAWAYS_FOLDER = "giveaways"
Path(GIVEAWAYS_FOLDER).mkdir(exist_ok=True)

def get_giveaway_path(giveaway_id: str) -> Path:
    return Path(GIVEAWAYS_FOLDER) / f"{giveaway_id}.json"

def save_giveaway_participants(giveaway_id: str, participants: list):
    with open(get_giveaway_path(giveaway_id), "w") as f:
        json.dump(participants, f)

def load_giveaway_participants(giveaway_id: str) -> list:
    try:
        with open(get_giveaway_path(giveaway_id), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def delete_giveaway_file(giveaway_id: str):
    try:
        get_giveaway_path(giveaway_id).unlink()
    except FileNotFoundError:
        pass

# Komenda do tworzenia giveawaya
@bot.command(name='giveaway', help='Creates a giveaway with buttons', usage="<duration> <prize>")
@commands.has_permissions(manage_messages=True)
async def giveaway(ctx, duration: str, *, prize: str):
    try:
        if duration.endswith('s'):
            seconds = int(duration[:-1])
        elif duration.endswith('m'):
            seconds = int(duration[:-1]) * 60
        elif duration.endswith('h'):
            seconds = int(duration[:-1]) * 3600
        elif duration.endswith('d'):
            seconds = int(duration[:-1]) * 86400
        else:
            seconds = int(duration)
    except ValueError:
        embed = discord.Embed(
            title="❌ Error",
            description="Invalid duration format! Use examples: `30s`, `5m`, `1h`, `2d`.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    giveaway_id = str(ctx.message.id)

    embed = discord.Embed(
        title=f"🎉 Giveaway: {prize} 🎉",
        description=f"Duration: {duration}\nClick the button below to participate!",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Giveaway ID: {giveaway_id}")

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Join Giveaway", style=discord.ButtonStyle.green, custom_id=f"join_{giveaway_id}"))

    await ctx.send(embed=embed, view=view)  # Usunięto `await message.pin()`

    await asyncio.sleep(seconds)
    await end_giveaway_automatically(ctx, giveaway_id, prize)

async def end_giveaway_automatically(ctx, giveaway_id: str, prize: str):
    participants = load_giveaway_participants(giveaway_id)
    if not participants:
        embed = discord.Embed(
            title="🎉 Giveaway Ended 🎉",
            description="No one participated in this giveaway. 😢",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        winner_id = random.choice(participants)
        winner = await ctx.guild.fetch_member(winner_id)

        embed = discord.Embed(
            title="🎉 Giveaway Ended 🎉",
            description=f"Winner: {winner.mention}\nPrize: **{prize}**\nCongratulations! 🎊",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    delete_giveaway_file(giveaway_id)  # Usuń plik po zakończeniu

# Handle the giveaway join button
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("join_"):
            giveaway_id = custom_id.split("_")[1]
            participants = load_giveaway_participants(giveaway_id)
            if interaction.user.id not in participants:
                participants.append(interaction.user.id)
                save_giveaway_participants(giveaway_id, participants)
                embed = discord.Embed(
                    title="✅ Success",
                    description="You have joined the giveaway!",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="You are already in this giveaway!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name='endgiveaway', help='Ends a giveaway and picks a winner', usage="<giveaway_id>")
@commands.has_permissions(manage_messages=True)
async def endgiveaway(ctx, giveaway_id: str):
    participants = load_giveaway_participants(giveaway_id)
    if not participants:
        embed = discord.Embed(
            title="❌ Error",
            description="No participants in this giveaway!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    winner_id = random.choice(participants)
    winner = await ctx.guild.fetch_member(winner_id)

    embed = discord.Embed(
        title="🎉 Giveaway Ended 🎉",
        description=f"Winner: {winner.mention}\nCongratulations! 🎊",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

    delete_giveaway_file(giveaway_id)

def ensure_reminders_folder():
    """Creates a folder for reminders if it doesn't exist."""
    folder = Path("data/reminders")
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def get_reminders_file_path(user_id: int) -> Path:
    """Returns the path to the reminders file for a given user."""
    return Path(f"data/reminders/{user_id}.json")

def save_reminder(user_id: int, reminder_data: dict):
    """Saves a reminder to a file."""
    ensure_reminders_folder()
    file_path = get_reminders_file_path(user_id)
    reminders = []
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            reminders = json.load(f)
    reminders.append(reminder_data)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=4)

def load_reminders(user_id: int) -> list:
    """Loads reminders for a given user."""
    file_path = get_reminders_file_path(user_id)
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def delete_reminder(user_id: int, reminder_index: int):
    """Deletes a reminder from the file."""
    reminders = load_reminders(user_id)
    if 0 <= reminder_index < len(reminders):
        reminders.pop(reminder_index)
        file_path = get_reminders_file_path(user_id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=4)

@bot.command(name='rmdm', help='Sets a cute reminder~ UwU', usage="<time_str> <message>")
async def remindme(ctx, time_str: str, *, message: str):
    try:
        if time_str.endswith('s'):
            seconds = int(time_str[:-1])
            time_display = f"{seconds} seconds ⏳"
        elif time_str.endswith('m'):
            seconds = int(time_str[:-1]) * 60
            time_display = f"{int(time_str[:-1])} minutes ⏰"
        elif time_str.endswith('h'):
            seconds = int(time_str[:-1]) * 3600
            time_display = f"{int(time_str[:-1])} hours 🕒"
        elif time_str.endswith('d'):
            seconds = int(time_str[:-1]) * 86400
            time_display = f"{int(time_str[:-1])} days 📅"
        else:
            seconds = int(time_str)
            time_display = f"{seconds} seconds ⏳"
    except ValueError:
        embed = discord.Embed(
            title="❌ Oopsie! Time format error~",
            description="Correct format is, e.g., `30s`, `5m`, `1h`, `2d` nya~",
            color=discord.Color.red()
        )
        embed.set_footer(text="Try again! 💖")
        return await ctx.send(embed=embed)

    # Save the reminder to a file
    reminder_data = {
        "user_id": ctx.author.id,
        "channel_id": ctx.channel.id,
        "time": time_str,
        "message": message,
        "trigger_time": int(time.time()) + seconds
    }
    save_reminder(ctx.author.id, reminder_data)

    # Message about setting the reminder
    embed = discord.Embed(
        title="⏰ Reminder set! UwU",
        description=f"I'll remind you in **{time_display}** about: \n\n✨ **{message}** ✨",
        color=discord.Color.pink()
    )
    embed.set_footer(text="Don't forget to check! 🥺")
    await ctx.send(embed=embed)

    await asyncio.sleep(seconds)
    
    # Delete the reminder from the file after sending
    reminders = load_reminders(ctx.author.id)
    for i, reminder in enumerate(reminders):
        if reminder["message"] == message and reminder["time"] == time_str:
            delete_reminder(ctx.author.id, i)
            break

    # Reminder message
    embed = discord.Embed(
        title="🔔 Time for your reminder! Nya~",
        description=f"**{ctx.author.mention}**, you asked me to remind you about:\n\n🌸 **{message}** 🌸",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Hope you didn't forget! 💕")
    await ctx.send(content=ctx.author.mention, embed=embed)

async def check_pending_reminders():
    """Checks and sends pending reminders after bot restart."""
    await bot.wait_until_ready()
    reminders_folder = Path("data/reminders")
    if not reminders_folder.exists():
        return

    for file in reminders_folder.glob("*.json"):
        user_id = int(file.stem)
        reminders = load_reminders(user_id)
        for reminder in reminders:
            current_time = int(time.time())
            if current_time >= reminder["trigger_time"]:
                channel = bot.get_channel(reminder["channel_id"])
                if channel:
                    embed = discord.Embed(
                        title="🔔 Time for your reminder! Nya~",
                        description=f"**<@{user_id}>**, you asked me to remind you about:\n\n🌸 **{reminder['message']}** 🌸",
                        color=discord.Color.gold()
                    )
                    embed.set_footer(text="Hope you didn't forget! 💕")
                    await channel.send(content=f"<@{user_id}>", embed=embed)
                delete_reminder(user_id, reminders.index(reminder))

# Add the setup_hook method to the bot
@bot.event
async def setup_hook():
    """Initializes the task for checking reminders after bot startup."""
    bot.loop.create_task(check_pending_reminders())

@bot.command(name='st', help='Sets the ticket channel UwU~ ✨', usage="<channel>")
@commands.has_permissions(administrator=True)
async def set_ticket_channel(ctx, channel: discord.TextChannel):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    config['ticket_channel_id'] = channel.id
    save_guild_config(guild_id, config)

    # Create the ticket panel embed
    embed = discord.Embed(
        title="🎫 Support Ticket Panel",
        description="Click the button below to open a new ticket! 💖",
        color=discord.Color.green()
    )

    # Create the "Create Ticket" button
    create_button = discord.ui.Button(
        label="Create Ticket",
        style=discord.ButtonStyle.green,
        custom_id="create_ticket",
        emoji="🎫"
    )

    view = discord.ui.View()
    view.add_item(create_button)

    # Send the panel to the specified channel
    await channel.send(embed=embed, view=view)

    # Confirm to the admin
    confirm_embed = discord.Embed(
        title="✅ Ticket Channel Set!",
        description=f"Ticket panel has been sent to {channel.mention} nya~ ✨",
        color=discord.Color.green()
    )
    await ctx.send(embed=confirm_embed)

# Handle button interaction
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data.get("custom_id") == "create_ticket":
            try:
                # Defer the interaction to avoid timeout
                await interaction.response.defer(ephemeral=True)

                # Check for existing tickets
                existing_tickets = [
                    channel for channel in interaction.guild.channels
                    if channel.name.startswith(f"ticket-{interaction.user.id}")
                ]

                if existing_tickets:
                    await interaction.followup.send(
                        "❌ You already have an open ticket! Please close it before creating a new one.",
                        ephemeral=True
                    )
                    return

                # Rest of the ticket creation logic...
                guild_id = interaction.guild.id
                config = load_guild_config(guild_id)
                ticket_channel_id = config.get('ticket_channel_id')
                staff_roles = config.get('staff_roles', [])

                if not ticket_channel_id:
                    await interaction.followup.send("❌ No ticket channel set. Use `;st <channel>`.", ephemeral=True)
                    return

                ticket_channel = interaction.guild.get_channel(ticket_channel_id)
                if not ticket_channel:
                    await interaction.followup.send("❌ Ticket channel not found. Check the configuration.", ephemeral=True)
                    return

                # Create a new channel
                overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                }

                for role_id in staff_roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

                new_channel = await interaction.guild.create_text_channel(
                    name=f"ticket-{interaction.user.id}",  # Use user ID for consistency
                    overwrites=overwrites,
                    category=ticket_channel.category
                )

                # Create an embed for the ticket
                embed = discord.Embed(
                    title="🎫 New Ticket",
                    description=f"Hello {interaction.user.mention}! Staff will assist you shortly.",
                    color=discord.Color.green()
                )

                # Create a button to close the ticket
                close_button = discord.ui.Button(
                    label="Close Ticket",
                    style=discord.ButtonStyle.red,
                    custom_id="close_ticket"
                )

                view = discord.ui.View()
                view.add_item(close_button)

                # Send the embed with the close button
                ticket_message = await new_channel.send(embed=embed, view=view)
                await ticket_message.pin()

                # Delete the pin notification (optional)
                async for pin_notification in new_channel.history(limit=1):
                    if pin_notification.type == discord.MessageType.pins_add:
                        await pin_notification.delete()

                await interaction.followup.send(
                    f"✅ Ticket created: {new_channel.mention}",
                    ephemeral=True
                )

            except Exception as e:
                print(f"Error creating ticket: {e}")
                await interaction.followup.send(
                    "❌ An error occurred while creating the ticket. Please try again.",
                    ephemeral=True
                )

        elif interaction.data.get("custom_id") == "close_ticket":
            try:
                await interaction.response.defer(ephemeral=True)
                guild_id = interaction.guild.id
                config = load_guild_config(guild_id)
                ticket_channel = interaction.channel

                if not ticket_channel.name.startswith("ticket-"):
                    await interaction.followup.send("❌ Not a ticket channel", ephemeral=True)
                    return

                # Get all messages from the ticket
                conversation = []
                async for message in ticket_channel.history(limit=None, oldest_first=True):
                    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    author = message.author.display_name
                    content = message.clean_content
                    
                    # Handle attachments
                    attachments = ""
                    if message.attachments:
                        attachments = " [Attachments: " + ", ".join(a.filename for a in message.attachments) + "]"
                    
                    conversation.append(f"[{timestamp}] {author}: {content}{attachments}")

                # Create the log file
                log_content = f"Ticket Log: {ticket_channel.name}\nCreated: {ticket_channel.created_at}\nClosed by: {interaction.user.display_name}\n\n"
                log_content += "\n".join(conversation)
                
                # Create a text file
                log_file = discord.File(
                    io.StringIO(log_content),
                    filename=f"{ticket_channel.name}-log.txt"
                )

                # Send to log channel if configured
                log_channel_id = config.get('ticket_log_channel_id')
                if log_channel_id:
                    log_channel = interaction.guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🎫 Ticket Closed",
                            description=f"Closed by {interaction.user.mention}",
                            color=discord.Color.red()
                        )
                        await log_channel.send(embed=embed, file=log_file)

                # Delete the channel
                await ticket_channel.delete()

            except Exception as e:
                print(f"Error closing ticket: {e}")
                try:
                    await interaction.followup.send(
                        "❌ Failed to close ticket. Please contact staff.",
                        ephemeral=True
                    )
                except:
                    pass

@bot.command(name='addstaff', help='Adds a cute staff role to tickets UwU~', usage="<role>")
@commands.has_permissions(administrator=True)
async def add_staff_role(ctx, role: discord.Role):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    if 'staff_roles' not in config:
        config['staff_roles'] = []
    
    if role.id not in config['staff_roles']:
        config['staff_roles'].append(role.id)
        save_guild_config(guild_id, config)
        embed = discord.Embed(
            title="✨ Role Added!",
            description=f"Role {role.mention} has been added to staff roles for tickets nya~ 💕",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="⚠️ Role Already Exists",
            description=f"Role {role.mention} is already a staff role for tickets >w<",
            color=discord.Color.orange()
        )
    await ctx.send(embed=embed)

@bot.command(name='rmstaff', help='Removes a staff role from tickets UwU~', usage="<role>")
@commands.has_permissions(administrator=True)
async def remove_staff_role(ctx, role: discord.Role):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    if 'staff_roles' not in config or role.id not in config['staff_roles']:
        embed = discord.Embed(
            title="❌ Role Not Found",
            description=f"Role {role.mention} is not a staff role for tickets nya~ 😿",
            color=discord.Color.red()
        )
    else:
        config['staff_roles'].remove(role.id)
        save_guild_config(guild_id, config)
        embed = discord.Embed(
            title="✨ Role Removed!",
            description=f"Role {role.mention} has been removed from staff roles for tickets UwU~ 💖",
            color=discord.Color.green()
        )
    await ctx.send(embed=embed)

@bot.command(name='tlog', help='Sets the channel for ticket logs UwU~', usage="<channel>")
@commands.has_permissions(administrator=True)
async def set_ticket_log_channel(ctx, channel: discord.TextChannel):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    config['ticket_log_channel_id'] = channel.id
    save_guild_config(guild_id, config)

    embed = discord.Embed(
        title="📝 Log Channel Set!",
        description=f"Ticket logs will now be sent to {channel.mention} nya~ ✨",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

async def log_ticket_messages(ticket_channel: discord.TextChannel, closer: discord.Member):
    guild_id = ticket_channel.guild.id
    config = load_guild_config(guild_id)
    log_channel_id = config.get('ticket_log_channel_id')

    if not log_channel_id:
        return  # No log channel set

    log_channel = ticket_channel.guild.get_channel(log_channel_id)
    if not log_channel:
        return  # Log channel not found

    # Create a temporary .txt file
    with open(f"ticket_{ticket_channel.name}.txt", "w", encoding="utf-8") as f:
        f.write(f"Ticket: #{ticket_channel.name}\n")
        f.write(f"Closed by: {closer.display_name} ({closer.id})\n")
        f.write(f"Closed at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("=== Messages ===\n")

        # Fetch and write messages
        async for message in ticket_channel.history(limit=None, oldest_first=True):
            f.write(f"{message.created_at.strftime('%Y-%m-%d %H:%M:%S')} | {message.author.display_name}: {message.content}\n")

    # Send the file
    with open(f"ticket_{ticket_channel.name}.txt", "rb") as f:
        await log_channel.send(
            f"📝 Ticket log: #{ticket_channel.name} (closed by {closer.mention})",
            file=discord.File(f, filename=f"ticket_{ticket_channel.name}.txt")
        )

    # Clean up the file
    os.remove(f"ticket_{ticket_channel.name}.txt")

@bot.command(name='fg', 
             help='Toggles file and GIF sending permissions for a channel', 
             usage="[channel]",
             description="Example:\n;fg #general")
@commands.has_permissions(manage_channels=True)
async def toggle_files_gifs(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    overwrites = channel.overwrites_for(ctx.guild.default_role)

    # Check current state
    current_state = overwrites.attach_files and overwrites.embed_links
    new_state = not current_state

    # Update permissions
    overwrites.attach_files = new_state
    overwrites.embed_links = new_state  # Required for GIFs

    # Send embed based on new state
    if new_state:
        embed = discord.Embed(
            title="✅ Permissions Updated",
            description=f"File and GIF sending is now **allowed** in {channel.mention}!",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="❌ Permissions Updated",
            description=f"File and GIF sending is now **disabled** in {channel.mention}!",
            color=discord.Color.red()
        )

    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrites)
    await ctx.send(embed=embed)

@bot.command(name='emojiinfo', help='Shows emoji information (ID, creation date)', usage="<emoji>")
async def emojiinfo(ctx, emoji: discord.Emoji):
    embed = discord.Embed(
        title="ℹ️ Emoji Info",
        description=f"**Name:** {emoji.name}\n**ID:** {emoji.id}\n**Created at:** {emoji.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=emoji.url)
    await ctx.send(embed=embed)

# Dodaj na początku pliku (np. po importach)
start_time = time.time()

@bot.command(name='uptime', help='Shows how long the bot has been online')
async def uptime(ctx):
    uptime_seconds = int(time.time() - start_time)
    uptime_string = f"{uptime_seconds // 86400}d {(uptime_seconds % 86400) // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
    embed = discord.Embed(
        title="⏱️ Bot Uptime",
        description=f"The bot has been online for **{uptime_string}**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='greroll', help='Rerolls a giveaway winner', usage="<id>")
@commands.has_permissions(manage_messages=True)
async def greroll(ctx, giveaway_id: str):
    participants = load_giveaway_participants(giveaway_id)
    if not participants:
        await ctx.send("❌ No participants in this giveaway!")
        return

    winner = random.choice(participants)
    await ctx.send(f"🎉 New winner: <@{winner}>!")

@bot.command(name='prefix', help='Changes the bot prefix for this server', usage="<new_prefix>")
@commands.has_permissions(administrator=True)
async def prefix(ctx, new_prefix: str):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    config["prefix"] = new_prefix
    save_guild_config(guild_id, config)
    await ctx.send(f"✅ Prefix changed to `{new_prefix}`!")

@bot.command(name='autorole', help='Sets a role to be assigned automatically to new members', usage="<role>")
@commands.has_permissions(administrator=True)
async def autorole(ctx, role: discord.Role):
    guild_id = ctx.guild.id
    config = load_guild_config(guild_id)
    config["autorole"] = role.id
    save_guild_config(guild_id, config)
    await ctx.send(f"✅ Role `{role.name}` will now be assigned to new members!")

@bot.command(name='ascii', help='Converts text to ASCII art', usage="<text>")
async def ascii_art(ctx, *, text: str):
    try:
        # Generate ASCII art with pyfiglet
        ascii_text = pyfiglet.figlet_format(text, font="standard")
        
        # Discord has a 2000 character limit, so we need to check
        if len(ascii_text) > 1990:
            await ctx.send("❌ Text too long for ASCII art conversion!")
            return
            
        await ctx.send(f"```\n{ascii_text}\n```")
    except Exception as e:
        await ctx.send(f"❌ Error generating ASCII art: {e}")

@bot.command(name='recentjoins', help='Shows recently joined members (last 10) - Admin only')
@commands.has_permissions(administrator=True)
async def recent_joins(ctx):
    try:
        # Get last 10 members sorted by join date
        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)[:10]
        
        # Create embed
        embed = discord.Embed(
            title="🆕 Newest Server Members",
            description="Here are the 10 most recent members who joined the server:",
            color=discord.Color.blurple()
        )
        
        # Add thumbnail with server icon
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        
        # Add fields for each member
        for i, member in enumerate(members, 1):
            join_date = discord.utils.format_dt(member.joined_at, 'D')
            join_relative = discord.utils.format_dt(member.joined_at, 'R')
            
            embed.add_field(
                name=f"{i}. {member.display_name}",
                value=f"• Account created: {discord.utils.format_dt(member.created_at, 'D')}\n"
                     f"• Joined: {join_date} ({join_relative})\n"
                     f"• ID: {member.id}",
                inline=False
            )
        
        # Add server info in footer
        embed.set_footer(
            text=f"Total members: {ctx.guild.member_count} • Requested by {ctx.author.display_name}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: {e}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)

@bot.command(name='slap', help='Virtual slap action', usage="<member>")
async def slap(ctx, member: discord.Member):
    slap_gifs = [
        "https://c.tenor.com/XiYuU9h44-AAAAAd/tenor.gif",
        "https://c.tenor.com/cpWuWnOU64MAAAAd/tenor.gif",
        "https://c.tenor.com/7xFcP1KWjY0AAAAd/tenor.gif",
        "https://c.tenor.com/Xwe3ku5WF-YAAAAd/tenor.gif",
        "https://c.tenor.com/Ws6Dm1ZW_vMAAAAd/tenor.gif",
        "https://c.tenor.com/CvBTA0GyrogAAAAd/tenor.gif",
        "https://c.tenor.com/EfhPfbG0hnMAAAAd/tenor.gif"
    ]
    embed = discord.Embed(
        title=f"{ctx.author.display_name} slaps {member.display_name}!",
        color=discord.Color.red()
    )
    embed.set_image(url=random.choice(slap_gifs))
    await ctx.send(embed=embed)

async def get_emoji(guild, emoji_name):
    return discord.utils.get(await guild.fetch_emojis(), name=emoji_name)

@bot.command(name='simprate', help='Checks how much a user simps')
async def simprate(ctx, user: discord.Member = None):
    user = user or ctx.author
    rate = random.randint(0, 100)
    
    # Determine simp level title
    if rate >= 90:
        title = "💝 ULTRA SIMP LORD"
        color = 0xFF1493
    elif rate >= 70:
        title = "💖 Hardcore Simp"
        color = 0xFF69B4
    elif rate >= 50:
        title = "💗 Moderate Simp"
        color = 0xFFB6C1
    else:
        title = "💘 Casual Simp"
        color = 0xD8BFD8
    
    # Animated progress bar
    progress = "🟪" * (rate // 10)
    empty = "⬜" * (10 - (rate // 10))
    
    # Random simp fact
    facts = [
        "Simping is just advanced appreciation!",
        "Your simp energy is off the charts!",
        "Professional simp material right here!",
        "This level of simp requires training!",
        "Simp detected! Initiating cuddle protocol!"
    ]
    
    embed = discord.Embed(
        title=f"🔍 {title}",
        description=f"**{user.display_name}** scored:",
        color=color
    )
    embed.add_field(
        name=f"**{rate}% SIMP**",
        value=f"{progress}{empty}\n\n*{random.choice(facts)}*",
        inline=False
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='howgay', help='Measures gay percentage (just for fun)')
async def howgay(ctx, user: discord.Member = None):
    user = user or ctx.author
    percentage = random.randint(0, 100)
    
    # Determine rainbow level
    if percentage >= 90:
        title = "🏳️‍⚧️ RAINBOW OVERLORD"
        color = 0x8A2BE2
    elif percentage >= 70:
        title = "🌈 Certified Gay™"
        color = 0x9932CC
    elif percentage >= 50:
        title = "💜 Bi-curious Explorer"
        color = 0x9370DB
    else:
        title = "💙 Straight-ish Ally"
        color = 0x4169E1
    
    # Animated rainbow meter
    gay_meter = "".join(
        ["🟥🟧🟨🟩🟦🟪"[(i % 6)] for i in range(percentage // 10)]
    )
    empty = "⬛" * (10 - (percentage // 10))
    
    # Fun responses
    responses = [
        "The gay agenda approves!",
        "Pride levels critical!",
        "Someone's fabulous today!",
        "Gaydar beeping intensively!",
        "The council of gays will decide your fate!"
    ]
    
    embed = discord.Embed(
        title=f"✨ {title}",
        description=f"Scanning **{user.display_name}**...",
        color=color
    )
    embed.add_field(
        name=f"**{percentage}% GAY**",
        value=f"{gay_meter}{empty}\n\n*{random.choice(responses)}*",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name='hierarchy', help='Shows server hierarchy (for fun)')
@commands.has_permissions(moderate_members=True)
async def hierarchy(ctx):
    if not (ctx.author.guild_permissions.moderate_members or ctx.author == ctx.guild.owner):
        await ctx.send("❌ You do not have permission to use this command!")
        return
    members = sorted(
        [m for m in ctx.guild.members if not m.bot],
        key=lambda m: (-m.top_role.position, m.joined_at)
    )[:10]
    
    embed = discord.Embed(
        title="👑 Server Power Hierarchy",
        description="Ranked by role position and join date:",
        color=0xFFD700
    )
    
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    for i, member in enumerate(members):
        embed.add_field(
            name=f"{medals[i]} {i+1}. {member.display_name}",
            value=f"Role: {member.top_role.mention}\nJoined: {member.joined_at.strftime('%Y-%m-%d')}",
            inline=False
        )
    
    # Dodaj thumbnail tylko jeśli serwer ma ikonę
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url) # Domyślna ikona
    
    embed.set_footer(text="Disclaimer: This is just for fun")
    await ctx.send(embed=embed)

@bot.command(name='color', help='Shows color sample from HEX/name')
async def color(ctx, color_input: str):
    try:
        # Try to parse as hex color
        if color_input.startswith('#'):
            color_int = int(color_input[1:], 16)
        else:
            color_int = int(color_input, 16)
        
        color_obj = discord.Color(color_int)
    except:
        # Try to get color by name
        try:
            color_obj = getattr(discord.Color, color_input.lower())()
        except:
            color_obj = discord.Color.default()
    
    embed = discord.Embed(
        title=f"Color: {str(color_obj)}",
        color=color_obj
    )
    embed.add_field(name="HEX", value=str(color_obj))
    embed.add_field(name="RGB", value=f"{color_obj.r}, {color_obj.g}, {color_obj.b}")
    embed.set_image(url=f"https://singlecolorimage.com/get/{str(color_obj)[1:]}/200x100")
    await ctx.send(embed=embed)

# Run the bot
bot.run(TOKEN)