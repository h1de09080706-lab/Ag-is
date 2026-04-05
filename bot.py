# ================= IMPORT =================
import discord
from discord.ext import commands
from discord import app_commands
import json, os, asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ================= SETUP =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

DATA = Path("data")
DATA.mkdir(exist_ok=True)

def load(name):
    path = DATA / f"{name}.json"
    if path.exists():
        return json.load(open(path))
    return {}

def save(name, data):
    json.dump(data, open(DATA / f"{name}.json", "w"), indent=2)

ticket_configs = load("tickets")
raid_config = load("raid")
backups = load("backups")

# ================= READY =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.add_view(TicketView())
    print(f"Connecté : {bot.user}")

# ================= PANEL =================
class TicketView(discord.ui.View):
    def __init__(self, panel_id=None):
        super().__init__(timeout=None)
        self.panel_id = panel_id

    @discord.ui.button(label="🎫 Ouvrir", style=discord.ButtonStyle.green, custom_id="ticket")
    async def ticket(self, interaction: discord.Interaction, _):
        gid = str(interaction.guild.id)
        config = ticket_configs[gid][self.panel_id]

        category = discord.utils.get(interaction.guild.categories, name="Tickets") or await interaction.guild.create_category("Tickets")

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True)
        }

        if config.get("support"):
            role = interaction.guild.get_role(config["support"])
            overwrites[role] = discord.PermissionOverwrite(view_channel=True)

        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        msg = config.get("message", "Bienvenue {user}")
        msg = msg.replace("{user}", interaction.user.mention)

        mention = ""
        if config.get("mention"):
            role = interaction.guild.get_role(config["mention"])
            mention = role.mention

        await channel.send(content=mention + "\n" + msg)

        await interaction.response.send_message(f"Ticket créé : {channel.mention}", ephemeral=True)

# ================= COMMAND PANEL =================
@bot.tree.command(name="panel_create")
async def panel_create(interaction: discord.Interaction, nom: str, texte: str):
    gid = str(interaction.guild.id)

    if gid not in ticket_configs:
        ticket_configs[gid] = {}

    ticket_configs[gid][nom] = {
        "message": texte
    }

    save("tickets", ticket_configs)

    embed = discord.Embed(title="Support", description=texte)
    await interaction.channel.send(embed=embed, view=TicketView(nom))
    await interaction.response.send_message("Panel créé", ephemeral=True)

# ================= BACKUP =================
@bot.tree.command(name="backup")
async def backup(interaction: discord.Interaction):
    await interaction.response.defer()
    g = interaction.guild

    data = {
        "channels": [(c.name, type(c).__name__) for c in g.channels]
    }

    backups[str(g.id)] = data
    save("backups", backups)

    await interaction.followup.send("Backup créé")

# ================= RESTORE =================
@bot.tree.command(name="restore")
async def restore(interaction: discord.Interaction):
    await interaction.response.defer()
    g = interaction.guild

    data = backups.get(str(g.id))
    if not data:
        return await interaction.followup.send("Aucun backup")

    for c in g.channels:
        await c.delete()

    for name, typ in data["channels"]:
        if "Text" in typ:
            await g.create_text_channel(name)
        else:
            await g.create_voice_channel(name)

    await interaction.followup.send("Serveur restauré")

# ================= ANTI RAID =================
@bot.event
async def on_guild_channel_create(channel):
    gid = str(channel.guild.id)
    conf = raid_config.get(gid, {"enabled": True})

    if not conf.get("enabled"):
        return

    async for log in channel.guild.audit_logs(limit=1):
        if log.action == discord.AuditLogAction.channel_create:
            if log.user.bot and log.user.id != bot.user.id:
                try:
                    await log.user.ban(reason="Raid bot")
                except:
                    pass

                await channel.delete()

                # restore auto
                if gid in backups:
                    data = backups[gid]
                    for c in data["channels"]:
                        if "Text" in c[1]:
                            await channel.guild.create_text_channel(c[0])

# ================= RAID CONFIG =================
@bot.tree.command(name="antiraid")
async def antiraid(interaction: discord.Interaction, actif: bool):
    raid_config[str(interaction.guild.id)] = {"enabled": actif}
    save("raid", raid_config)
    await interaction.response.send_message("Anti-raid mis à jour")

# ================= RAID RESTORE =================
@bot.tree.command(name="raidrestore")
async def raidrestore(interaction: discord.Interaction):
    await interaction.response.defer()
    gid = str(interaction.guild.id)

    if gid not in backups:
        return await interaction.followup.send("Pas de backup")

    data = backups[gid]

    for c in interaction.guild.channels:
        await c.delete()

    for name, typ in data["channels"]:
        if "Text" in typ:
            await interaction.guild.create_text_channel(name)

    await interaction.followup.send("Raid nettoyé + serveur restauré")

# ================= SETUP =================
@bot.tree.command(name="setup")
async def setup(interaction: discord.Interaction):
    g = interaction.guild

    cat = await g.create_category("IMPORTANT")
    await g.create_text_channel("reglement", category=cat)
    await g.create_text_channel("annonces", category=cat)

    await g.create_category("Tickets")

    await interaction.response.send_message("Setup terminé")

# ================= RUN =================
bot.run("TON_TOKEN")
