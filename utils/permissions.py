def has_higher_role(moderator, target):
    """
    Check if moderator has a higher role than target
    Returns True if moderator's top role is higher than target's top role
    """
    return moderator.top_role.position > target.top_role.position

def is_owner():
    """Check if user is bot owner"""
    async def predicate(interaction):
        return interaction.user.id in interaction.client.config.get('owners', [])
    return app_commands.check(predicate)

def is_admin():
    """Check if user has administrator permission"""
    async def predicate(interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)
