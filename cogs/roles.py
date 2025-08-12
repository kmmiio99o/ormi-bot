# cogs/roles.py

import discord
from discord import app_commands
from discord.ext import commands
import re
from typing import Optional
# Make sure this import path is correct for your project
# from utils.permissions import has_higher_role

# --- Placeholder for has_higher_role if you don't have it ---
# You should ideally use your existing utility function.
# This is a basic version for demonstration if needed.
def has_higher_role(user: discord.Member, target: discord.Member) -> bool:
    # Administrator permission overrides role hierarchy
    if user.guild_permissions.administrator:
        return True
    # User cannot moderate someone with higher or equal role
    return user.top_role > target.top_role

class RolesCog(commands.Cog):
    """Cog for role management commands."""

    def __init__(self, bot):
        self.bot = bot

    # --- Add Role Command ---
    @app_commands.command(name="addrole", description="Adds a role to a user.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        member="The user to add the role to.",
        role="The role to add."
    )
    async def addrole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        """Adds a role to a user."""
        # Permission and hierarchy checks
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't add roles to users with equal or higher role!",
                ephemeral=True
            )
        if interaction.guild.me.top_role.position <= role.position:
            return await interaction.response.send_message(
                "❌ My role is too low to add this role!",
                ephemeral=True
            )
        if role in member.roles:
            return await interaction.response.send_message(
                f"❌ {member.mention} already has the role {role.mention}!",
                ephemeral=True
            )

        try:
            await member.add_roles(role, reason=f"Role added by {interaction.user} (ID: {interaction.user.id})")
            embed = discord.Embed(
                title="✅ Role Added",
                description=f"Successfully added {role.mention} to {member.mention}!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to add this role! Please check my role position and permissions.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while adding the role: {e}",
                ephemeral=True
            )

    # --- Remove Role Command ---
    @app_commands.command(name="rmrole", description="Removes a role from a user.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        member="The user to remove the role from.",
        role="The role to remove."
    )
    async def rmrole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        """Removes a role from a user."""
         # Permission and hierarchy checks
        if not has_higher_role(interaction.user, member):
            return await interaction.response.send_message(
                "❌ You can't remove roles from users with equal or higher role!",
                ephemeral=True
            )
        if interaction.guild.me.top_role.position <= role.position:
            return await interaction.response.send_message(
                "❌ My role is too low to remove this role!",
                ephemeral=True
            )
        if role not in member.roles:
            return await interaction.response.send_message(
                f"❌ {member.mention} doesn't have the role {role.mention}!",
                ephemeral=True
            )

        try:
            await member.remove_roles(role, reason=f"Role removed by {interaction.user} (ID: {interaction.user.id})")
            embed = discord.Embed(
                title="✅ Role Removed",
                description=f"Successfully removed {role.mention} from {member.mention}!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to remove this role! Please check my role position and permissions.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while removing the role: {e}",
                ephemeral=True
            )

    # --- Create Role Command ---
    @app_commands.command(name="createrole", description="Creates a new role.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        name="The name of the new role.",
        color="The HEX color code for the role (e.g., #FF5733)."
    )
    async def createrole(self, interaction: discord.Interaction, name: str, color: Optional[str] = None):
        """Creates a new role."""
        # Validate role name length (Discord limit is 100 characters)
        if len(name) > 100:
             return await interaction.response.send_message(
                "❌ Role name must be 100 characters or less.",
                ephemeral=True
            )

        # Parse color if provided
        role_color = discord.Color.default() # Default color
        if color:
            # Remove # if present
            color_hex = color.lstrip('#')
            # Validate HEX format (should be 3 or 6 characters of 0-9, A-F)
            if not re.fullmatch(r'[0-9A-Fa-f]{3,6}', color_hex):
                 return await interaction.response.send_message(
                    "❌ Invalid HEX color code. Please use a format like `#FF5733`.",
                    ephemeral=True
                )
            # Standardize to 6-digit HEX
            if len(color_hex) == 3:
                color_hex = ''.join([c*2 for c in color_hex])
            try:
                role_color = discord.Color(int(color_hex, 16))
            except ValueError:
                 return await interaction.response.send_message(
                    "❌ Invalid HEX color code.",
                    ephemeral=True
                )

        try:
            new_role = await interaction.guild.create_role(
                name=name,
                color=role_color,
                reason=f"Role created by {interaction.user} (ID: {interaction.user.id})"
            )
            embed = discord.Embed(
                title="✅ Role Created",
                description=f"Successfully created role {new_role.mention}!",
                color=new_role.color
            )
            # Add a field showing the color if it was specified
            if color:
                embed.add_field(name="Color", value=f"`#{color_hex}`", inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to create roles! Please check my permissions.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while creating the role: {e}",
                ephemeral=True
            )

    # --- Delete Role Command ---
    @app_commands.command(name="delrole", description="Deletes a role.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(role="The role to delete.")
    async def delrole(self, interaction: discord.Interaction, role: discord.Role):
        """Deletes a role."""
        # Prevent deletion of @everyone
        if role.is_default():
            return await interaction.response.send_message(
                "❌ You cannot delete the `@everyone` role.",
                ephemeral=True
            )
        # Check role hierarchy
        if interaction.guild.me.top_role.position <= role.position:
            return await interaction.response.send_message(
                "❌ My role is too low to delete this role!",
                ephemeral=True
            )
        if interaction.user.top_role.position <= role.position and not interaction.user.guild_permissions.administrator:
             return await interaction.response.send_message(
                "❌ You cannot delete a role higher than or equal to your highest role!",
                ephemeral=True
            )

        role_name = role.name
        role_mention = role.mention
        try:
            await role.delete(reason=f"Role deleted by {interaction.user} (ID: {interaction.user.id})")
            embed = discord.Embed(
                title="✅ Role Deleted",
                description=f"Successfully deleted role {role_mention} (`{role_name}`).",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to delete this role! Please check my role position and permissions.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while deleting the role: {e}",
                ephemeral=True
            )

    # --- Edit Role Command ---
    @app_commands.command(name="editrole", description="Edits a role's name, color, and icon.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        role="The role to edit.",
        new_name="The new name for the role.",
        color="The new HEX color code for the role (e.g., #FF5733).",
        icon="The new icon for the role (upload an image file). Requires Server Boost Level 2+."
    )
    async def editrole(self, interaction: discord.Interaction, role: discord.Role, new_name: str, color: Optional[str] = None, icon: Optional[discord.Attachment] = None):
        """Edits a role's name, color, and icon."""
        # Prevent editing of @everyone
        if role.is_default():
            return await interaction.response.send_message(
                "❌ You cannot edit the `@everyone` role.",
                ephemeral=True
            )
        # Check role hierarchy
        if interaction.guild.me.top_role.position <= role.position:
            return await interaction.response.send_message(
                "❌ My role is too low to edit this role!",
                ephemeral=True
            )
        if interaction.user.top_role.position <= role.position and not interaction.user.guild_permissions.administrator:
             return await interaction.response.send_message(
                "❌ You cannot edit a role higher than or equal to your highest role!",
                ephemeral=True
            )

        # Validate new name length
        if len(new_name) > 100:
             return await interaction.response.send_message(
                "❌ Role name must be 100 characters or less.",
                ephemeral=True
            )

        # Prepare edit parameters
        edit_kwargs = {
            'name': new_name,
            'reason': f"Role edited by {interaction.user} (ID: {interaction.user.id})"
        }

        # Parse color if provided
        if color:
            # Remove # if present
            color_hex = color.lstrip('#')
            # Validate HEX format
            if not re.fullmatch(r'[0-9A-Fa-f]{3,6}', color_hex):
                 return await interaction.response.send_message(
                    "❌ Invalid HEX color code. Please use a format like `#FF5733`.",
                    ephemeral=True
                )
            # Standardize to 6-digit HEX
            if len(color_hex) == 3:
                color_hex = ''.join([c*2 for c in color_hex])
            try:
                edit_kwargs['color'] = discord.Color(int(color_hex, 16))
            except ValueError:
                 return await interaction.response.send_message(
                    "❌ Invalid HEX color code.",
                    ephemeral=True
                )

        # Handle icon if provided
        if icon:
            # Check if the guild has access to role icons (Boost Level 2+)
            if interaction.guild.premium_tier < 2:
                return await interaction.response.send_message(
                    "❌ This server needs to be boosted to Level 2 or higher to use role icons.",
                    ephemeral=True
                )
            # Validate attachment type
            if not icon.content_type or not icon.content_type.startswith('image/'):
                return await interaction.response.send_message(
                    "❌ Please upload a valid image file for the role icon.",
                    ephemeral=True
                )
            # Discord.py requires reading the image data for role icons
            try:
                icon_data = await icon.read()
                # Discord has size limits for role icons
                if len(icon_data) > 256 * 1024: # 256 KB limit
                    return await interaction.response.send_message(
                        "❌ Role icon image is too large. Please use an image under 256 KB.",
                        ephemeral=True
                    )
                edit_kwargs['display_icon'] = icon_data
            except Exception as e:
                 return await interaction.response.send_message(
                    f"❌ Failed to read the uploaded icon image: {e}",
                    ephemeral=True
                )

        # Perform the edit
        try:
            old_name = role.name
            old_color = role.color
            # Store old icon hash if needed for detailed logging, but it's complex to display
            edited_role = await role.edit(**edit_kwargs)

            embed = discord.Embed(
                title="✅ Role Edited",
                description=f"Successfully edited role {edited_role.mention}!",
                color=edited_role.color
            )
            embed.add_field(name="Old Name", value=old_name, inline=True)
            embed.add_field(name="New Name", value=edited_role.name, inline=True)
            # Show color change if applicable
            if 'color' in edit_kwargs:
                old_color_hex = f"#{old_color.value:06X}" if old_color.value else "Default"
                new_color_hex = f"#{edited_role.color.value:06X}" if edited_role.color.value else "Default"
                embed.add_field(name="Old Color", value=old_color_hex, inline=True)
                embed.add_field(name="New Color", value=new_color_hex, inline=True)
            # Indicate icon change if applicable
            if icon:
                embed.add_field(name="Icon", value="Updated (see role list)", inline=False)

            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to edit this role! Please check my role position and permissions.",
                ephemeral=True
            )
        except ValueError as ve: # Catch specific errors like invalid icon data
             await interaction.response.send_message(
                f"❌ Invalid value provided for role edit: {ve}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while editing the role: {e}",
                ephemeral=True
            )

    # --- Error Handler for Permission Checks ---
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """Handles errors for app commands within this cog, specifically for missing permissions."""
        # Handle Missing Permissions
        if isinstance(error, app_commands.MissingPermissions):
            # Map permission names to user-friendly descriptions
            missing_perms = error.missing_permissions
            perm_descriptions = {
                "manage_roles": "Manage Roles",
                "manage_channels": "Manage Channels", # Might be needed for some edge cases
                # Add more mappings if you use other specific permissions in this cog
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

        # --- Optional: Handle other common errors ---
        # Example: CheckFailure (e.g., from custom checks like has_higher_role)
        # elif isinstance(error, app_commands.CheckFailure):
        #     # The checks within the commands (like has_higher_role) send their own messages.
        #     # This would catch any *other* check failures not handled by the command itself.
        #     # You can customize this if needed.
        #     if not interaction.response.is_done():
        #          await interaction.response.send_message("❌ You are not allowed to use this command.", ephemeral=True)
        #     else:
        #          await interaction.followup.send("❌ You are not allowed to use this command.", ephemeral=True)
        #     return

        # --- Generic Error Handling ---
        # This part is optional but useful for debugging unexpected errors.
        # You might want to log them and send a generic message.

        # Example logging (uncomment if you have a logger set up for this cog):
        # import logging
        # logger = logging.getLogger(__name__)
        # logger.error(f"Unhandled app command error in '{interaction.command.name}' for {interaction.user} in {interaction.guild.id}: {error}", exc_info=True)

        # Send a generic error message to the user
        generic_error_msg = "❌ An unexpected error occurred while processing your command. You might be missing required permissions or there was an internal issue."
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(generic_error_msg, ephemeral=True)
            else:
                 await interaction.followup.send(generic_error_msg, ephemeral=True)
        except:
            pass # Silent fail if we can't even send the generic error


# The setup function to load the cog
async def setup(bot):
    """Setup function for the roles cog."""
    await bot.add_cog(RolesCog(bot))
