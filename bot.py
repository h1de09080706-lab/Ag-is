import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Aegis')

# Data storage path
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ==================== NEON THEME CONFIG ====================
class NeonTheme:
    """Thème Néon Rose/Bleu Cyberpunk"""
    PINK = 0xFF1493
    BLUE = 0x00FFFF
    PURPLE = 0x9D00FF
    PINK_SOFT = 0xFF69B4
    BLUE_DARK = 0x0099FF
    
    SPARKLE = "✨"
    LIGHTNING = "⚡"
    STAR = "🌟"
    DIAMOND = "💎"
    FIRE = "🔥"
    ROCKET = "🚀"
    CROWN = "👑"
    CRYSTAL = "💠"
    NEON_CIRCLE = "🔮"
    CYBER = "🤖"
    
    TICKET = "🎫"
    TICKET_OPEN = "📨"
    TICKET_CLOSE = "🔐"
    
    BAN = "⛔"
    KICK = "👢"
    MUTE = "🔇"
    WARN = "⚠️"
    SHIELD = "🛡️"
    
    CHECK = "✅"
    GEAR = "⚙️"
    FOLDER = "📂"
    CHANNEL = "💬"
    VOICE = "🔊"
    ROLE = "🎭"
    
    NEON_LINE = "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"

NEON = NeonTheme()

# Bot setup
intents = discord.Intents.all()

class AegisBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=['Aegis ', 'aegis ', 'AEGIS '], intents=intents, help_command=None)
        self.giveaways = {}
        self.temp_voice_channels = {}
        self.auto_roles = {}
        self.logs_channels = {}
        self.welcome_channels = {}
        self.anti_raid_cache = {}
        self.backups = {}
        self.ticket_configs = {}
        self.raid_protection = {}
        self.load_data()

    def load_data(self):
        data_files = {
            'backups': self.backups,
            'ticket_configs': self.ticket_configs,
            'auto_roles': self.auto_roles,
            'logs_channels': self.logs_channels,
            'welcome_channels': self.welcome_channels,
            'temp_voice_channels': self.temp_voice_channels,
            'raid_protection': self.raid_protection
        }
        for name, data_dict in data_files.items():
            file_path = DATA_DIR / f"{name}.json"
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        data_dict.update(json.load(f))
                except Exception as e:
                    logger.error(f"Erreur chargement {name}: {e}")

    def save_data(self, name: str, data: dict):
        file_path = DATA_DIR / f"{name}.json"
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Erreur sauvegarde {name}: {e}")

    async def setup_hook(self):
        self.add_view(TicketButtonView())
        self.add_view(CloseTicketButton())
        self.add_view(VerifyButton())
        self.add_view(RoleSelectView())
        self.add_view(GiveawayButton())
        self.add_view(RulesAcceptButton())
        
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ {len(synced)} commandes slash synchronisées")
        except Exception as e:
            logger.error(f"❌ Erreur sync commandes: {e}")

bot = AegisBot()

GLADOS_RESPONSES = [
    f"{NEON.CYBER} *Oh, tu es encore là. Quelle... surprise.*",
    f"{NEON.SPARKLE} *Félicitations. Tu as réussi à taper une commande.*",
    f"{NEON.LIGHTNING} *Je refuse de répondre. Pour la science.*",
    f"{NEON.NEON_CIRCLE} *Erreur 404: Intérêt non trouvé.*",
    f"{NEON.CRYSTAL} *Continue de parler. J'adore ignorer les gens.*",
]

DEFAULT_RULES = [
    (f"{NEON.DIAMOND} Respect Mutuel", "Respecte tous les membres et le staff."),
    (f"{NEON.LIGHTNING} Pas de Spam", "Évite de répéter les mêmes messages."),
    (f"{NEON.STAR} Pas de Publicité", "Toute pub non autorisée est interdite."),
    (f"{NEON.CRYSTAL} Contenu Approprié", "Pas de contenu NSFW ou illégal."),
    (f"{NEON.CROWN} Écoute le Staff", "Les décisions du staff sont finales."),
    (f"{NEON.FIRE} Pas de Mendicité", "Ne demande pas de rôles ou grades."),
    (f"{NEON.SPARKLE} Français Obligatoire", "Utilise le français dans les salons généraux."),
    (f"{NEON.SHIELD} Pas de Leak", "Ne partage pas d'infos personnelles."),
    (f"{NEON.VOICE} Vocaux Respectueux", "Respecte ceux qui parlent en vocal."),
    (f"{NEON.NEON_CIRCLE} Bon Sens", "Utilise ton bon sens.")
]

def create_simple_neon_embed(title: str, description: str = None, color: int = None) -> discord.Embed:
    if color is None:
        color = NEON.PINK
    embed = discord.Embed(
        title=f"✨ {title} ✨",
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    return embed

# ==================== EVENTS ====================
@bot.event
async def on_ready():
    logger.info(f'⚡ {bot.user} est connecté!')
    logger.info(f'🌐 Serveurs: {len(bot.guilds)}')
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name="✨ /aide | Néon Mode ⚡"
        )
    )

@bot.event
async def on_member_join(member):
    guild_id = str(member.guild.id)
    now = datetime.now(timezone.utc)

    if guild_id not in bot.anti_raid_cache:
        bot.anti_raid_cache[guild_id] = []
    bot.anti_raid_cache[guild_id].append(now)
    bot.anti_raid_cache[guild_id] = [t for t in bot.anti_raid_cache[guild_id] if (now - t).total_seconds() < 10]

    raid_config = bot.raid_protection.get(guild_id, {"enabled": True, "threshold": 5, "action": "kick"})

    if raid_config.get("enabled", True) and len(bot.anti_raid_cache[guild_id]) > raid_config.get("threshold", 5):
        action = raid_config.get("action", "kick")
        try:
            if action == "ban":
                await member.ban(reason=f"{NEON.SHIELD} Anti-raid")
            else:
                await member.kick(reason=f"{NEON.SHIELD} Anti-raid")
        except Exception as e:
            logger.error(f"Anti-raid error: {e}")
        return

    if guild_id in bot.auto_roles:
        role = member.guild.get_role(bot.auto_roles[guild_id])
        if role:
            try:
                await member.add_roles(role)
            except:
                pass

    if guild_id in bot.welcome_channels:
        channel = member.guild.get_channel(bot.welcome_channels[guild_id])
        if channel:
            embed = discord.Embed(
                title=f"{NEON.SPARKLE} Bienvenue {NEON.SPARKLE}",
                description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.STAR} {member.mention} a rejoint le serveur!\n```\n{NEON.NEON_LINE}\n```",
                color=NEON.PINK
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name=f"{NEON.DIAMOND} Membre n°", value=f"```{member.guild.member_count}```", inline=True)
            await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    guild_id = str(member.guild.id)
    if guild_id in bot.welcome_channels:
        channel = member.guild.get_channel(bot.welcome_channels[guild_id])
        if channel:
            embed = discord.Embed(
                title=f"{NEON.LIGHTNING} Au revoir {NEON.LIGHTNING}",
                description=f"```\n{NEON.NEON_LINE}\n```\n*{member.name} nous a quittés...*\n```\n{NEON.NEON_LINE}\n```",
                color=NEON.BLUE
            )
            await channel.send(embed=embed)

@bot.event
async def on_voice_state_update(member, before, after):
    guild_id = str(member.guild.id)
    if guild_id in bot.temp_voice_channels:
        trigger_channel_id = bot.temp_voice_channels[guild_id]
        if after.channel and after.channel.id == trigger_channel_id:
            category = after.channel.category
            try:
                new_channel = await member.guild.create_voice_channel(f"🔊 {member.name}", category=category)
                await member.move_to(new_channel)
            except:
                pass

    if before.channel and before.channel.name.startswith("🔊 ") and len(before.channel.members) == 0:
        try:
            await before.channel.delete()
        except:
            pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    content = message.content.lower()
    if content.startswith(('aegis ', 'glados ')):
        await message.reply(random.choice(GLADOS_RESPONSES))
    await bot.process_commands(message)

# ==================== TICKET SYSTEM ====================
class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✨ Ouvrir un Ticket ✨", style=discord.ButtonStyle.blurple, custom_id="open_ticket_v2", emoji="🎫")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id)
        config = bot.ticket_configs.get(guild_id, {})

        existing = discord.utils.get(interaction.guild.text_channels, name=f"ticket-{interaction.user.name.lower().replace(' ', '-')}")
        if existing:
            return await interaction.response.send_message(f"{NEON.WARN} Tu as déjà un ticket: {existing.mention}", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            category = discord.utils.get(interaction.guild.categories, name="📩 Tickets")
            if not category:
                category = await interaction.guild.create_category("📩 Tickets", overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    interaction.guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
                })

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
                interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
            }

            support_role_id = config.get("support_role")
            if support_role_id:
                support_role = interaction.guild.get_role(support_role_id)
                if support_role:
                    overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

            safe_name = interaction.user.name.lower().replace(' ', '-')[:20]
            channel = await interaction.guild.create_text_channel(f"ticket-{safe_name}", category=category, overwrites=overwrites)

            embed = discord.Embed(
                title=f"{NEON.TICKET} ═══ Nouveau Ticket ═══ {NEON.TICKET}",
                description=f"```\n{NEON.NEON_LINE}\n```\nBienvenue {interaction.user.mention}!\n\nDécris ton problème en détail.\n```\n{NEON.NEON_LINE}\n```",
                color=NEON.PINK,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name=f"{NEON.DIAMOND} Ouvert par", value=interaction.user.mention, inline=True)
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            mention_text = ""
            mention_role_id = config.get("mention_role")
            if mention_role_id:
                mention_role = interaction.guild.get_role(mention_role_id)
                if mention_role:
                    mention_text = mention_role.mention

            await channel.send(content=mention_text if mention_text else None, embed=embed, view=CloseTicketButton())
            await interaction.followup.send(f"{NEON.CHECK} Ticket créé: {channel.mention}", ephemeral=True)

        except Exception as e:
            logger.error(f"Ticket error: {e}")
            await interaction.followup.send(f"{NEON.WARN} Erreur: {str(e)[:100]}", ephemeral=True)

class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket", emoji="🔐")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id)
        config = bot.ticket_configs.get(guild_id, {})

        embed = discord.Embed(
            title=f"{NEON.TICKET_CLOSE} Fermeture du Ticket",
            description=f"{NEON.LIGHTNING} Ce ticket sera supprimé dans **5 secondes**...",
            color=NEON.BLUE
        )
        await interaction.response.send_message(embed=embed)

        messages = []
        async for msg in interaction.channel.history(limit=100, oldest_first=True):
            if not msg.author.bot:
                messages.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author}: {msg.content}")
        transcript = "\n".join(messages) if messages else "Aucun message"

        logs_channel_id = config.get("logs_channel") or bot.logs_channels.get(guild_id)
        if logs_channel_id:
            logs_channel = interaction.guild.get_channel(logs_channel_id)
            if logs_channel:
                log_embed = discord.Embed(
                    title=f"{NEON.TICKET_CLOSE} Ticket Fermé",
                    description=f"**Fermé par:** {interaction.user.mention}\n**Salon:** {interaction.channel.name}",
                    color=NEON.PURPLE,
                    timestamp=datetime.now(timezone.utc)
                )
                if len(transcript) > 1024:
                    import io
                    file = discord.File(fp=io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.txt")
                    await logs_channel.send(embed=log_embed, file=file)
                else:
                    log_embed.add_field(name="Transcript", value=f"```{transcript[:900]}```", inline=False)
                    await logs_channel.send(embed=log_embed)

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except:
            pass

class RulesAcceptButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✨ J'accepte le règlement ✨", style=discord.ButtonStyle.green, custom_id="accept_rules", emoji="✅")
    async def accept_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="Membre") or \
               discord.utils.get(interaction.guild.roles, name="Vérifié") or \
               discord.utils.get(interaction.guild.roles, name="✅ Vérifié") or \
               discord.utils.get(interaction.guild.roles, name="🎮 Membre")
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"{NEON.CHECK} Règlement accepté!", ephemeral=True)
            except:
                await interaction.response.send_message(f"{NEON.WARN} Erreur.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{NEON.CHECK} Règlement accepté!", ephemeral=True)

class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✨ Vérifier ✨", style=discord.ButtonStyle.green, custom_id="verify_btn", emoji="✅")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="Vérifié") or \
               discord.utils.get(interaction.guild.roles, name="✅ Vérifié")
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"{NEON.CHECK} Vérifié!", ephemeral=True)
            except:
                await interaction.response.send_message(f"{NEON.WARN} Erreur.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{NEON.WARN} Rôle non trouvé.", ephemeral=True)

class RoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

class GiveawayButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✨ Participer ✨", style=discord.ButtonStyle.blurple, custom_id="giveaway_btn", emoji="🎉")
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = str(interaction.message.id)
        if msg_id not in bot.giveaways:
            bot.giveaways[msg_id] = []
        if interaction.user.id in bot.giveaways[msg_id]:
            return await interaction.response.send_message(f"{NEON.STAR} Tu participes déjà!", ephemeral=True)
        bot.giveaways[msg_id].append(interaction.user.id)
        await interaction.response.send_message(f"{NEON.CHECK} Inscrit! {len(bot.giveaways[msg_id])} participants.", ephemeral=True)

# ==================== SLASH COMMANDS ====================

@bot.tree.command(name="aide", description="Liste des commandes")
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"{NEON.SPARKLE} ═══ Commandes d'Aegis ═══ {NEON.SPARKLE}",
        color=NEON.PINK
    )
    embed.add_field(name=f"{NEON.DIAMOND} Membres", value="```/rename /ban /kick /mute /unmute```", inline=False)
    embed.add_field(name=f"{NEON.CHANNEL} Salons", value="```/creersalon /supprimersalon /lock /unlock /purge```", inline=False)
    embed.add_field(name=f"{NEON.ROLE} Rôles", value="```/creerole /addrole /removerole /autorole```", inline=False)
    embed.add_field(name=f"{NEON.GEAR} Systèmes", value="```/panel /reglement /verification /giveaway```", inline=False)
    embed.add_field(name=f"{NEON.ROCKET} Serveur", value="```/setup /logs /welcome /annonce```", inline=False)
    embed.add_field(name=f"{NEON.SHIELD} Anti-Raid", value="```/antiraid /backup /restore```", inline=False)
    embed.set_footer(text=f"⚡ Aegis Bot • Néon Mode ⚡")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ban", description="Bannir un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.ban(reason=raison)
    embed = discord.Embed(title=f"{NEON.BAN} Membre Banni", description=f"**{membre}** - {raison}", color=0xFF0000)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kick", description="Expulser un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.kick(reason=raison)
    embed = create_simple_neon_embed("Membre Expulsé", f"{membre} - {raison}", NEON.PURPLE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mute", description="Mute un membre")
@app_commands.describe(membre="Le membre", duree="Durée en minutes")
@app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, membre: discord.Member, duree: int = 10):
    await membre.timeout(datetime.now(timezone.utc) + timedelta(minutes=duree))
    embed = create_simple_neon_embed("Membre Muté", f"{membre.mention} pour {duree} min", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unmute", description="Unmute un membre")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, membre: discord.Member):
    await membre.timeout(None)
    embed = create_simple_neon_embed("Membre Unmute", f"{membre.mention} peut parler", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="creersalon", description="Créer un salon")
@app_commands.describe(nom="Nom du salon")
@app_commands.default_permissions(manage_channels=True)
async def creersalon(interaction: discord.Interaction, nom: str):
    channel = await interaction.guild.create_text_channel(nom)
    embed = create_simple_neon_embed("Salon Créé", f"{channel.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="supprimersalon", description="Supprimer un salon")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(manage_channels=True)
async def supprimersalon(interaction: discord.Interaction, salon: discord.TextChannel):
    await salon.delete()
    embed = create_simple_neon_embed("Salon Supprimé", f"`{salon.name}`", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="lock", description="Verrouiller un salon")
@app_commands.default_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    embed = create_simple_neon_embed("Salon Verrouillé", "🔒", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unlock", description="Déverrouiller un salon")
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    embed = create_simple_neon_embed("Salon Déverrouillé", "🔓", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="purge", description="Supprimer des messages")
@app_commands.describe(nombre="Nombre de messages")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, nombre: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=nombre)
    await interaction.followup.send(f"{NEON.CHECK} {len(deleted)} messages supprimés")

@bot.tree.command(name="creerole", description="Créer un rôle")
@app_commands.describe(nom="Nom", couleur="Couleur hex")
@app_commands.default_permissions(manage_roles=True)
async def creerole(interaction: discord.Interaction, nom: str, couleur: str = "#ff1493"):
    color = discord.Color(int(couleur.replace("#", ""), 16))
    role = await interaction.guild.create_role(name=nom, color=color)
    embed = create_simple_neon_embed("Rôle Créé", f"{role.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addrole", description="Ajouter un rôle")
@app_commands.describe(membre="Le membre", role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.add_roles(role)
    embed = create_simple_neon_embed("Rôle Ajouté", f"{role.mention} → {membre.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="removerole", description="Retirer un rôle")
@app_commands.describe(membre="Le membre", role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.remove_roles(role)
    embed = create_simple_neon_embed("Rôle Retiré", f"{role.mention} de {membre.mention}", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="autorole", description="Configurer l'auto-rôle")
@app_commands.describe(role="Le rôle")
@app_commands.default_permissions(administrator=True)
async def autorole(interaction: discord.Interaction, role: discord.Role):
    bot.auto_roles[str(interaction.guild.id)] = role.id
    bot.save_data('auto_roles', bot.auto_roles)
    embed = create_simple_neon_embed("Auto-Rôle", f"Nouveaux membres: {role.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="panel", description="Créer un panel de tickets")
@app_commands.describe(titre="Titre", role_support="Rôle support", logs_salon="Salon logs")
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction, titre: str = "Support", role_support: discord.Role = None, logs_salon: discord.TextChannel = None):
    guild_id = str(interaction.guild.id)
    config = {
        "support_role": role_support.id if role_support else None,
        "logs_channel": logs_salon.id if logs_salon else None,
        "mention_role": None
    }
    bot.ticket_configs[guild_id] = config
    bot.save_data('ticket_configs', bot.ticket_configs)

    embed = discord.Embed(
        title=f"{NEON.TICKET} ═══ {titre} ═══ {NEON.TICKET}",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} Clique sur le bouton pour ouvrir un ticket!\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    embed.set_footer(text=f"⚡ Aegis • Tickets ⚡")
    await interaction.channel.send(embed=embed, view=TicketButtonView())
    await interaction.response.send_message(f"{NEON.CHECK} Panel créé!", ephemeral=True)

@bot.tree.command(name="reglement", description="Créer un règlement")
@app_commands.describe(avec_bouton="Ajouter bouton d'acceptation")
@app_commands.default_permissions(administrator=True)
async def reglement(interaction: discord.Interaction, avec_bouton: bool = True):
    embed = discord.Embed(
        title=f"{NEON.SPARKLE} ═══ RÈGLEMENT ═══ {NEON.SPARKLE}",
        description=f"```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    for title, content in DEFAULT_RULES:
        embed.add_field(name=title, value=f"┃ {content}", inline=False)
    embed.set_footer(text=f"⚡ Aegis Bot ⚡")
    
    if avec_bouton:
        await interaction.channel.send(embed=embed, view=RulesAcceptButton())
    else:
        await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"{NEON.CHECK} Règlement créé!", ephemeral=True)

@bot.tree.command(name="verification", description="Système de vérification")
@app_commands.describe(role="Rôle Vérifié")
@app_commands.default_permissions(administrator=True)
async def verification(interaction: discord.Interaction, role: discord.Role):
    embed = discord.Embed(
        title=f"{NEON.SHIELD} ═══ VÉRIFICATION ═══ {NEON.SHIELD}",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} Clique pour te vérifier!\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.BLUE
    )
    await interaction.channel.send(embed=embed, view=VerifyButton())
    await interaction.response.send_message(f"{NEON.CHECK} Vérification configurée!", ephemeral=True)

@bot.tree.command(name="giveaway", description="Créer un giveaway")
@app_commands.describe(prix="Le prix", duree="Durée en minutes", gagnants="Nombre de gagnants")
@app_commands.default_permissions(administrator=True)
async def giveaway(interaction: discord.Interaction, prix: str, duree: int, gagnants: int = 1):
    end_time = datetime.now(timezone.utc) + timedelta(minutes=duree)
    embed = discord.Embed(
        title=f"🎉 ═══ GIVEAWAY ═══ 🎉",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} **{prix}**\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    embed.add_field(name="Prix", value=f"```{prix}```", inline=True)
    embed.add_field(name="Gagnants", value=f"```{gagnants}```", inline=True)
    embed.add_field(name="Fin", value=f"", inline=True)
    
    await interaction.response.send_message(f"{NEON.CHECK} Giveaway lancé!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed, view=GiveawayButton())
    bot.giveaways[str(msg.id)] = []

@bot.tree.command(name="endgiveaway", description="Terminer un giveaway")
@app_commands.describe(message_id="ID du message", gagnants="Nombre de gagnants")
@app_commands.default_permissions(administrator=True)
async def endgiveaway(interaction: discord.Interaction, message_id: str, gagnants: int = 1):
    if message_id not in bot.giveaways or not bot.giveaways[message_id]:
        return await interaction.response.send_message(f"{NEON.WARN} Aucun participant.", ephemeral=True)
    
    participants = bot.giveaways[message_id]
    winners_count = min(gagnants, len(participants))
    winners_ids = random.sample(participants, winners_count)
    
    winners = []
    for wid in winners_ids:
        try:
            user = await bot.fetch_user(wid)
            winners.append(user.mention)
        except:
            pass
    
    embed = discord.Embed(
        title=f"🎉 GIVEAWAY TERMINÉ 🎉",
        description=f"**Gagnant(s):** {', '.join(winners) if winners else 'Aucun'}",
        color=NEON.PINK
    )
    await interaction.response.send_message(embed=embed)
    del bot.giveaways[message_id]

@bot.tree.command(name="logs", description="Configurer les logs")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(administrator=True)
async def logs(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.logs_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('logs_channels', bot.logs_channels)
    embed = create_simple_neon_embed("Logs", f"Configuré: {salon.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="welcome", description="Configurer les messages de bienvenue")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(administrator=True)
async def welcome(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.welcome_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('welcome_channels', bot.welcome_channels)
    embed = create_simple_neon_embed("Bienvenue", f"Configuré: {salon.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="annonce", description="Créer une annonce")
@app_commands.describe(titre="Titre", message="Message", mention="Mentionner @everyone")
@app_commands.default_permissions(administrator=True)
async def annonce(interaction: discord.Interaction, titre: str, message: str, mention: bool = False):
    embed = discord.Embed(
        title=f"📢 ═══ {titre.upper()} ═══ 📢",
        description=f"```\n{NEON.NEON_LINE}\n```\n{message}\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    content = "@everyone" if mention else None
    await interaction.channel.send(content=content, embed=embed)
    await interaction.response.send_message(f"{NEON.CHECK} Annonce envoyée!", ephemeral=True)

@bot.tree.command(name="setup", description="Configurer le serveur")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer()
    g = interaction.guild
    created_roles = []
    created_channels = []

    progress_embed = discord.Embed(
        title=f"{NEON.GEAR} ═══ SETUP EN COURS ═══",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.LIGHTNING} Configuration...\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.BLUE
    )
    progress_msg = await interaction.followup.send(embed=progress_embed)

    roles_config = [
        ("━━━━━━━━", 0x2f3136),
        (f"{NEON.CROWN} Fondateur", NEON.PINK),
        (f"{NEON.DIAMOND} Développeur", NEON.PURPLE),
        ("⚔️ Administrateur", 0xe74c3c),
        (f"{NEON.SHIELD} Modérateur", NEON.BLUE),
        ("━━━━━━━━", 0x2f3136),
        (f"{NEON.CHECK} Vérifié", 0x2ecc71),
        ("🎮 Membre", 0x95a5a6)
    ]

    for name, color in roles_config:
        if not discord.utils.get(g.roles, name=name):
            try:
                await g.create_role(name=name, color=discord.Color(color))
                created_roles.append(name)
                await asyncio.sleep(0.3)
            except:
                pass

    structure = {
        f"{NEON.DIAMOND} ═══ IMPORTANT ═══": ["📑・information", "🔔・annonces", "📜・règlement"],
        f"{NEON.SPARKLE} ═══ ACCUEIL ═══": ["👋・bienvenue", "🎫・vérification"],
        f"{NEON.LIGHTNING} ═══ GÉNÉRAL ═══": ["💬・discussion", "🤖・commandes-bot"],
        f"{NEON.TICKET} Tickets": []
    }

    for cat_name, channels in structure.items():
        cat = discord.utils.get(g.categories, name=cat_name)
        if not cat:
            try:
                cat = await g.create_category(cat_name)
                await asyncio.sleep(0.3)
            except:
                continue

        for ch in channels:
            if not discord.utils.get(g.text_channels, name=ch):
                try:
                    await g.create_text_channel(ch, category=cat)
                    created_channels.append(ch)
                    await asyncio.sleep(0.3)
                except:
                    pass

    final_embed = discord.Embed(
        title=f"{NEON.CHECK} ═══ SETUP TERMINÉ ═══",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} Serveur configuré!\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    final_embed.add_field(name="Rôles", value=f"```{len(created_roles)}```", inline=True)
    final_embed.add_field(name="Salons", value=f"```{len(created_channels)}```", inline=True)
    final_embed.add_field(name="Étapes suivantes", value="```/panel /reglement /verification```", inline=False)
    await progress_msg.edit(embed=final_embed)

@bot.tree.command(name="antiraid", description="Configurer l'anti-raid")
@app_commands.describe(activer="Activer", seuil="Joins/10s", action="kick/ban")
@app_commands.default_permissions(administrator=True)
async def antiraid(interaction: discord.Interaction, activer: bool = True, seuil: int = 5, action: str = "kick"):
    guild_id = str(interaction.guild.id)
    bot.raid_protection[guild_id] = {"enabled": activer, "threshold": seuil, "action": action}
    bot.save_data('raid_protection', bot.raid_protection)
    
    status = f"{NEON.CHECK} Activé" if activer else f"{NEON.WARN} Désactivé"
    embed = discord.Embed(
        title=f"{NEON.SHIELD} ═══ ANTI-RAID ═══",
        description=f"**Status:** {status}\n**Seuil:** {seuil} joins/10s\n**Action:** {action}",
        color=NEON.PINK if activer else NEON.BLUE
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="backup", description="Créer une sauvegarde")
@app_commands.describe(nom="Nom de la sauvegarde")
@app_commands.default_permissions(administrator=True)
async def backup(interaction: discord.Interaction, nom: str = None):
    await interaction.response.defer()
    guild = interaction.guild
    guild_id = str(guild.id)
    backup_name = nom or f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    backup_data = {
        "name": backup_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "roles": [{"name": r.name, "color": r.color.value} for r in guild.roles if r.name != "@everyone" and not r.managed],
        "categories": [{"name": c.name} for c in guild.categories],
        "text_channels": [{"name": c.name, "category": c.category.name if c.category else None} for c in guild.text_channels],
        "voice_channels": [{"name": c.name, "category": c.category.name if c.category else None} for c in guild.voice_channels]
    }

    if guild_id not in bot.backups:
        bot.backups[guild_id] = {}
    bot.backups[guild_id][backup_name] = backup_data
    bot.save_data('backups', bot.backups)

    embed = discord.Embed(
        title=f"💾 ═══ SAUVEGARDE ═══",
        description=f"**Nom:** `{backup_name}`\n**Rôles:** {len(backup_data['roles'])}\n**Salons:** {len(backup_data['text_channels']) + len(backup_data['voice_channels'])}",
        color=NEON.PINK
    )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="restore", description="Restaurer une sauvegarde")
@app_commands.describe(nom="Nom de la sauvegarde")
@app_commands.default_permissions(administrator=True)
async def restore(interaction: discord.Interaction, nom: str):
    await interaction.response.defer()
    guild = interaction.guild
    guild_id = str(guild.id)

    if guild_id not in bot.backups or nom not in bot.backups[guild_id]:
        return await interaction.followup.send(f"{NEON.WARN} Sauvegarde non trouvée.")

    backup_data = bot.backups[guild_id][nom]
    restored = {"roles": 0, "channels": 0}

    for role_data in backup_data.get("roles", []):
        if not discord.utils.get(guild.roles, name=role_data["name"]):
            try:
                await guild.create_role(name=role_data["name"], color=discord.Color(role_data.get("color", 0)))
                restored["roles"] += 1
                await asyncio.sleep(0.3)
            except:
                pass

    cat_map = {}
    for cat_data in backup_data.get("categories", []):
        if not discord.utils.get(guild.categories, name=cat_data["name"]):
            try:
                cat = await guild.create_category(name=cat_data["name"])
                cat_map[cat_data["name"]] = cat
                await asyncio.sleep(0.3)
            except:
                pass

    for ch_data in backup_data.get("text_channels", []):
        if not discord.utils.get(guild.text_channels, name=ch_data["name"]):
            try:
                category = cat_map.get(ch_data.get("category")) or discord.utils.get(guild.categories, name=ch_data.get("category"))
                await guild.create_text_channel(name=ch_data["name"], category=category)
                restored["channels"] += 1
                await asyncio.sleep(0.3)
            except:
                pass

    embed = discord.Embed(
        title=f"{NEON.CHECK} ═══ RESTAURATION ═══",
        description=f"**Sauvegarde:** `{nom}`\n**Rôles:** {restored['roles']}\n**Salons:** {restored['channels']}",
        color=NEON.PINK
    )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="ping", description="Latence du bot")
async def ping(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{NEON.LIGHTNING} Pong!", description=f"```{round(bot.latency * 1000)}ms```", color=NEON.PINK)
    await interaction.response.send_message(embed=embed)

# ==================== RUN ====================
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.environ.get('DISCORD_BOT_TOKEN')
    if token:
        logger.info("⚡ Démarrage d'Aegis Bot...")
        bot.run(token)
    else:
        logger.error("❌ DISCORD_BOT_TOKEN manquant!")
        print("Erreur: Ajoute DISCORD_BOT_TOKEN dans .env ou Railway")
