# ===================== MODIF INIT =====================
# Remplace dans AegisBot.__init__
self.ticket_configs = {}  # {guild_id: {panel_id: config}}


# ===================== PANEL COMMAND =====================
@bot.tree.command(name="panel", description="Créer un panel de tickets avancé")
@app_commands.describe(
    nom="Nom unique du panel",
    titre="Titre",
    description="Description",
    bouton_texte="Texte bouton",
    bouton_emoji="Emoji",
    couleur="Couleur hex",
    role_mention="Rôle mentionné",
    role_support="Rôle support",
    logs_salon="Salon logs",
    message_bienvenue="Message ticket"
)
@app_commands.default_permissions(administrator=True)
async def panel(
    interaction: discord.Interaction,
    nom: str,
    titre: str,
    description: str,
    bouton_texte: str = "Ouvrir un ticket",
    bouton_emoji: str = "📩",
    couleur: str = "#5865F2",
    role_mention: discord.Role = None,
    role_support: discord.Role = None,
    logs_salon: discord.TextChannel = None,
    message_bienvenue: str = None
):
    guild_id = str(interaction.guild.id)

    if guild_id not in bot.ticket_configs:
        bot.ticket_configs[guild_id] = {}

    bot.ticket_configs[guild_id][nom] = {
        "title": titre,
        "description": description,
        "button_text": bouton_texte,
        "button_emoji": bouton_emoji,
        "color": couleur,
        "mention_role": role_mention.id if role_mention else None,
        "support_role": role_support.id if role_support else None,
        "logs_channel": logs_salon.id if logs_salon else None,
        "welcome_message": message_bienvenue or "Bienvenue {user}"
    }

    bot.save_data("ticket_configs", bot.ticket_configs)

    embed = discord.Embed(
        title=titre,
        description=description,
        color=discord.Color(int(couleur.replace("#", ""), 16))
    )

    await interaction.channel.send(embed=embed, view=TicketButtonView(panel_id=nom))
    await interaction.response.send_message(f"✅ Panel `{nom}` créé", ephemeral=True)


# ===================== TICKET VIEW =====================
class TicketButtonView(discord.ui.View):
    def __init__(self, panel_id=None):
        super().__init__(timeout=None)
        self.panel_id = panel_id

    @discord.ui.button(label="📩 Ouvrir un Ticket", style=discord.ButtonStyle.green, custom_id="open_ticket_v2")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild_id = str(interaction.guild.id)
        config = bot.ticket_configs.get(guild_id, {}).get(self.panel_id)

        if not config:
            return await interaction.response.send_message("❌ Panel invalide", ephemeral=True)

        existing = discord.utils.get(
            interaction.guild.text_channels,
            name=f"ticket-{interaction.user.name.lower()}"
        )

        if existing:
            return await interaction.response.send_message(f"Déjà ouvert: {existing.mention}", ephemeral=True)

        category = discord.utils.get(interaction.guild.categories, name="📩 Tickets") or await interaction.guild.create_category("📩 Tickets")

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True)
        }

        if config.get("support_role"):
            role = interaction.guild.get_role(config["support_role"])
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True)

        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name.lower()}",
            category=category,
            overwrites=overwrites
        )

        msg = config.get("welcome_message", "Bienvenue {user}")
        msg = msg.replace("{user}", interaction.user.mention)

        mention = ""
        if config.get("mention_role"):
            role = interaction.guild.get_role(config["mention_role"])
            if role:
                mention = role.mention

        await channel.send(
            content=mention,
            embed=discord.Embed(description=msg, color=discord.Color.green()),
            view=CloseTicketButton()
        )

        await interaction.response.send_message(f"✅ Ticket créé: {channel.mention}", ephemeral=True)


# ===================== ANTI RAID =====================
@bot.event
async def on_guild_channel_create(channel):
    guild_id = str(channel.guild.id)
    config = bot.raid_protection.get(guild_id, {})

    if not config.get("enabled", False):
        return

    await asyncio.sleep(1)

    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
        user = entry.user

        if user.bot and user.id != bot.user.id:

            try:
                await user.ban(reason="🛡️ Anti-raid: bot malveillant")
            except:
                pass

            try:
                await channel.delete(reason="🛡️ Suppression raid")
            except:
                pass

            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(minutes=5)

            async for log in channel.guild.audit_logs(limit=50, action=discord.AuditLogAction.channel_create):
                if log.created_at > cutoff and log.user.id == user.id:
                    ch = channel.guild.get_channel(log.target.id)
                    if ch:
                        try:
                            await ch.delete()
                        except:
                            pass

            if config.get("auto_restore"):
                if guild_id in bot.backups and bot.backups[guild_id]:
                    latest = max(bot.backups[guild_id].keys())
                    if channel.guild.system_channel:
                        await channel.guild.system_channel.send(
                            f"⚠️ Raid détecté → utilise /restore nom:{latest}"
                        )


# ===================== RAID RESTORE =====================
@bot.tree.command(name="raidrestore", description="Restore complet après raid")
@app_commands.default_permissions(administrator=True)
async def raidrestore(interaction: discord.Interaction):
    await interaction.response.defer()

    guild = interaction.guild
    guild_id = str(guild.id)

    if guild_id not in bot.backups or not bot.backups[guild_id]:
        return await interaction.followup.send("❌ Aucun backup")

    latest = max(bot.backups[guild_id].keys())

    for channel in guild.channels:
        try:
            await channel.delete()
        except:
            pass

    await restore.callback(interaction, nom=latest, supprimer_existant=False)

    await interaction.followup.send(f"✅ Serveur restauré depuis `{latest}`")


# ===================== SETUP AUTO =====================
# A ajouter à la FIN de ta commande /setup

logs_channel = discord.utils.get(g.text_channels, name="modération-logs")
if logs_channel:
    bot.logs_channels[str(g.id)] = logs_channel.id
    bot.save_data("logs_channels", bot.logs_channels)

if str(g.id) not in bot.ticket_configs:
    bot.ticket_configs[str(g.id)] = {}
    bot.save_data("ticket_configs", bot.ticket_configs)
