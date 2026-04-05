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
        self.server_snapshots = {}
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
                except:
                    pass
    
    def save_data(self, name: str, data: dict):
        file_path = DATA_DIR / f"{name}.json"
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Commandes slash synchronisées")

bot = AegisBot()

GLADOS_RESPONSES = [
    "Oh, tu es encore là. Quelle... surprise.",
    "Félicitations. Tu as réussi à taper une commande. Impressionnant... pour un humain.",
    "Je refuse de répondre. Pour la science.",
    "Erreur 404: Intérêt non trouvé.",
    "Continue de parler. J'adore ignorer les gens.",
]

DEFAULT_RULES = [
    ("1️⃣ Respect Mutuel", "Respecte tous les membres et le staff. Aucune forme d'insulte, discrimination, harcèlement ou comportement toxique ne sera tolérée."),
    ("2️⃣ Pas de Spam", "Évite de répéter les mêmes messages, les majuscules excessives, le flood d'emojis ou les mentions abusives."),
    ("3️⃣ Pas de Publicité", "Toute forme de publicité non autorisée (serveurs Discord, liens, etc.) est interdite. Demande la permission au staff."),
    ("4️⃣ Contenu Approprié", "Pas de contenu NSFW, violent, choquant ou illégal. Cela inclut les pseudos, avatars et messages."),
    ("5️⃣ Écoute le Staff", "Les décisions du staff sont finales. Si tu as un problème, utilise les tickets pour en discuter calmement."),
    ("6️⃣ Pas de Mendicité", "Ne demande pas de rôles, grades ou avantages. Ils sont attribués au mérite."),
    ("7️⃣ Français Obligatoire", "Utilise le français dans les salons généraux. D'autres langues sont autorisées en privé ou dans les salons dédiés."),
    ("8️⃣ Pas de Leak", "Ne partage pas d'informations personnelles (les tiennes ou celles des autres)."),
    ("9️⃣ Vocaux Respectueux", "En vocal, respecte ceux qui parlent, évite les bruits parasites et les changements de salon répétitifs."),
    ("🔟 Bon Sens", "Utilise ton bon sens. Si tu penses que quelque chose n'est pas approprié, ne le fais pas.")
]

# ==================== EVENTS ====================
@bot.event
async def on_ready():
    logger.info(f'{bot.user} est connecté!')
    logger.info(f'Serveurs: {len(bot.guilds)}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="les humains | /aide"))
    bot.add_view(TicketButtonView())
    bot.add_view(CloseTicketButton())
    bot.add_view(VerifyButton())
    bot.add_view(RoleSelectView())
    bot.add_view(GiveawayButton())
    bot.add_view(RulesAcceptButton())

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
                await member.ban(reason="🛡️ Anti-raid: Trop de joins simultanés")
            else:
                await member.kick(reason="🛡️ Anti-raid: Trop de joins simultanés")
            
            if guild_id in bot.logs_channels:
                log_channel = member.guild.get_channel(bot.logs_channels[guild_id])
                if log_channel:
                    embed = discord.Embed(
                        title="🚨 RAID DÉTECTÉ",
                        description=f"**Membre:** {member} ({member.id})\n**Action:** {action}\n**Raison:** Trop de joins en peu de temps",
                        color=discord.Color.red(),
                        timestamp=now
                    )
                    await log_channel.send(embed=embed)
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
                title="👋 Bienvenue",
                description=f"*{member.mention} a rejoint le serveur. Un autre cobaye pour nos expériences...*",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="📊 Membre n°", value=f"`{member.guild.member_count}`", inline=True)
            embed.add_field(name="📅 Compte créé", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
            embed.set_footer(text=f"ID: {member.id}")
            await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    guild_id = str(member.guild.id)
    if guild_id in bot.welcome_channels:
        channel = member.guild.get_channel(bot.welcome_channels[guild_id])
        if channel:
            embed = discord.Embed(
                title="👋 Au revoir",
                description=f"*{member.name} est parti. Bon débarras.*",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

@bot.event
async def on_guild_channel_create(channel):
    guild_id = str(channel.guild.id)
    raid_config = bot.raid_protection.get(guild_id, {})
    if not raid_config.get("auto_restore", False):
        return
    
    await asyncio.sleep(1)
    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            if entry.target.id == channel.id:
                creator = entry.user
                if creator.bot and creator.id != bot.user.id:
                    if guild_id in bot.logs_channels:
                        log_channel = channel.guild.get_channel(bot.logs_channels[guild_id])
                        if log_channel:
                            embed = discord.Embed(
                                title="⚠️ Activité Suspecte",
                                description=f"**Bot:** {creator.mention}\n**Action:** Création de salon\n**Salon:** {channel.name}",
                                color=discord.Color.orange()
                            )
                            await log_channel.send(embed=embed)
    except:
        pass

@bot.event
async def on_voice_state_update(member, before, after):
    guild_id = str(member.guild.id)
    if guild_id in bot.temp_voice_channels:
        trigger_channel_id = bot.temp_voice_channels[guild_id]
        if after.channel and after.channel.id == trigger_channel_id:
            category = after.channel.category
            new_channel = await member.guild.create_voice_channel(f"🔊 {member.name}", category=category)
            await member.move_to(new_channel)
    
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
        cmd = content.split(' ', 1)[1] if ' ' in content else ''
        
        if 'ban' in cmd and message.mentions:
            if message.author.guild_permissions.ban_members:
                user = message.mentions[0]
                await user.ban(reason="Commande naturelle")
                await message.reply(f"*{user} a été banni. Pour la science.*")
            return
        
        if ('kick' in cmd or 'expulse' in cmd) and message.mentions:
            if message.author.guild_permissions.kick_members:
                user = message.mentions[0]
                await user.kick(reason="Commande naturelle")
                await message.reply(f"*{user} a été expulsé.*")
            return
        
        if 'créer' in cmd and 'salon' in cmd:
            if message.author.guild_permissions.manage_channels:
                name = cmd.split('salon')[-1].strip() or "nouveau-salon"
                channel = await message.guild.create_text_channel(name)
                await message.reply(f"*Salon {channel.mention} créé.*")
            return
        
        if 'ajouter' in cmd and 'rôle' in cmd and message.mentions and message.role_mentions:
            if message.author.guild_permissions.manage_roles:
                user = message.mentions[0]
                role = message.role_mentions[0]
                await user.add_roles(role)
                await message.reply(f"*Rôle {role.name} ajouté à {user.name}.*")
            return
        
        if 'retirer' in cmd and 'rôle' in cmd and message.mentions and message.role_mentions:
            if message.author.guild_permissions.manage_roles:
                user = message.mentions[0]
                role = message.role_mentions[0]
                await user.remove_roles(role)
                await message.reply(f"*Rôle {role.name} retiré de {user.name}.*")
            return
        
        if 'mute' in cmd and message.mentions:
            if message.author.guild_permissions.moderate_members:
                user = message.mentions[0]
                await user.timeout(datetime.now(timezone.utc) + timedelta(minutes=10))
                await message.reply(f"*{user} est muté pour 10 minutes.*")
            return
        
        if 'unmute' in cmd and message.mentions:
            if message.author.guild_permissions.moderate_members:
                user = message.mentions[0]
                await user.timeout(None)
                await message.reply(f"*{user} peut parler à nouveau.*")
            return
        
        if 'backup' in cmd:
            if message.author.guild_permissions.administrator:
                await message.reply("*Utilise `/backup` pour créer une sauvegarde.*")
            return
        
        if 'restore' in cmd or 'restaurer' in cmd:
            if message.author.guild_permissions.administrator:
                await message.reply("*Utilise `/restore` pour restaurer une sauvegarde.*")
            return
        
        await message.reply(random.choice(GLADOS_RESPONSES))
    
    await bot.process_commands(message)

# ==================== TICKET SYSTEM ====================
class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📩 Ouvrir un Ticket", style=discord.ButtonStyle.green, custom_id="open_ticket_v2")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id)
        config = bot.ticket_configs.get(guild_id, {})
        
        existing = discord.utils.get(interaction.guild.text_channels, name=f"ticket-{interaction.user.name.lower()}")
        if existing:
            return await interaction.response.send_message(f"*Tu as déjà un ticket: {existing.mention}*", ephemeral=True)
        
        category = discord.utils.get(interaction.guild.categories, name="📩 Tickets") or await interaction.guild.create_category("📩 Tickets")
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        
        support_role_id = config.get("support_role")
        if support_role_id:
            support_role = interaction.guild.get_role(support_role_id)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)
        
        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name.lower()}",
            category=category,
            overwrites=overwrites
        )
        
        welcome_text = config.get("welcome_message", f"Bienvenue {interaction.user.mention}!\n\nDécris ton problème en détail et un membre du staff te répondra bientôt.")
        
        embed = discord.Embed(
            title="🎫 Nouveau Ticket",
            description=welcome_text.replace("{user}", interaction.user.mention),
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="📋 Ouvert par", value=interaction.user.mention, inline=True)
        embed.add_field(name="📅 Date", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
        embed.set_footer(text="Clique sur 🔒 pour fermer le ticket")
        
        mention_text = ""
        mention_role_id = config.get("mention_role")
        if mention_role_id:
            mention_role = interaction.guild.get_role(mention_role_id)
            if mention_role:
                mention_text = mention_role.mention
        
        await channel.send(content=mention_text, embed=embed, view=CloseTicketButton())
        await interaction.response.send_message(f"*Ticket créé: {channel.mention}*", ephemeral=True)
        
        logs_channel_id = config.get("logs_channel") or bot.logs_channels.get(guild_id)
        if logs_channel_id:
            logs_channel = interaction.guild.get_channel(logs_channel_id)
            if logs_channel:
                log_embed = discord.Embed(
                    title="📩 Ticket Ouvert",
                    description=f"**Utilisateur:** {interaction.user.mention}\n**Salon:** {channel.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc)
                )
                await logs_channel.send(embed=log_embed)

class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔒 Fermer", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id)
        config = bot.ticket_configs.get(guild_id, {})
        
        messages = []
        async for msg in interaction.channel.history(limit=100, oldest_first=True):
            if not msg.author.bot:
                messages.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author}: {msg.content}")
        
        transcript = "\n".join(messages) if messages else "Aucun message"
        
        await interaction.response.send_message("*Fermeture du ticket dans 5 secondes...*")
        
        logs_channel_id = config.get("logs_channel") or bot.logs_channels.get(guild_id)
        if logs_channel_id:
            logs_channel = interaction.guild.get_channel(logs_channel_id)
            if logs_channel:
                log_embed = discord.Embed(
                    title="🔒 Ticket Fermé",
                    description=f"**Fermé par:** {interaction.user.mention}\n**Salon:** {interaction.channel.name}",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                if len(transcript) > 1024:
                    log_embed.add_field(name="📝 Transcript", value="Voir fichier joint", inline=False)
                    file = discord.File(
                        fp=__import__('io').BytesIO(transcript.encode()),
                        filename=f"transcript-{interaction.channel.name}.txt"
                    )
                    await logs_channel.send(embed=log_embed, file=file)
                else:
                    log_embed.add_field(name="📝 Transcript", value=f"```{transcript[:1000]}```", inline=False)
                    await logs_channel.send(embed=log_embed)
        
        await asyncio.sleep(5)
        await interaction.channel.delete()

class RulesAcceptButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ J'accepte le règlement", style=discord.ButtonStyle.green, custom_id="accept_rules")
    async def accept_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="Membre")
        if not role:
            role = discord.utils.get(interaction.guild.roles, name="Vérifié")
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("*Tu as accepté le règlement. Bienvenue!*", ephemeral=True)
        else:
            await interaction.response.send_message("*Règlement accepté! (Aucun rôle configuré)*", ephemeral=True)

class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ Vérifier", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="Vérifié")
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("*Vérifié. Tu es officiellement moins suspect.*", ephemeral=True)
        else:
            await interaction.response.send_message("*Rôle Vérifié non trouvé.*", ephemeral=True)

class RoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

class GiveawayButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎉 Participer", style=discord.ButtonStyle.blurple, custom_id="giveaway_btn")
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = str(interaction.message.id)
        if msg_id not in bot.giveaways:
            bot.giveaways[msg_id] = []
        if interaction.user.id in bot.giveaways[msg_id]:
            return await interaction.response.send_message("*Tu participes déjà.*", ephemeral=True)
        bot.giveaways[msg_id].append(interaction.user.id)
        await interaction.response.send_message(f"*Inscrit! {len(bot.giveaways[msg_id])} participants.*", ephemeral=True)

# ==================== SLASH COMMANDS ====================

@bot.tree.command(name="aide", description="Liste des commandes")
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(title="📋 Commandes d'Aegis", color=discord.Color.orange())
    embed.add_field(name="👤 Membres", value="`/rename` `/resetpseudo` `/ban` `/unban` `/kick` `/mute` `/unmute`", inline=False)
    embed.add_field(name="📁 Salons", value="`/creersalon` `/supprimersalon` `/creervoice` `/renommersalon` `/slowmode` `/lock` `/unlock` `/purge`", inline=False)
    embed.add_field(name="🎭 Rôles", value="`/creerole` `/supprimerole` `/addrole` `/removerole` `/roleall` `/autorole`", inline=False)
    embed.add_field(name="⚙️ Systèmes", value="`/panel` `/reglement` `/reglement_custom` `/verification` `/giveaway` `/endgiveaway`", inline=False)
    embed.add_field(name="🛠️ Serveur", value="`/setup` `/logs` `/welcome` `/tempvoice` `/annonce` `/sondage` `/embed`", inline=False)
    embed.add_field(name="🛡️ Anti-Raid", value="`/antiraid` `/backup` `/backups` `/restore` `/raidrestore`", inline=False)
    embed.add_field(name="💬 Naturel", value="`Aegis ban @user` `Aegis créer un salon test` `Aegis ajouter le rôle @role à @user`", inline=False)
    embed.set_footer(text="Aegis • Pour la science.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rename", description="Renommer un membre")
@app_commands.describe(membre="Le membre", pseudo="Nouveau pseudo")
@app_commands.default_permissions(manage_nicknames=True)
async def rename(interaction: discord.Interaction, membre: discord.Member, pseudo: str):
    await membre.edit(nick=pseudo)
    await interaction.response.send_message(f"*{membre} renommé en `{pseudo}`.*")

@bot.tree.command(name="resetpseudo", description="Réinitialiser le pseudo d'un membre")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(manage_nicknames=True)
async def resetpseudo(interaction: discord.Interaction, membre: discord.Member):
    await membre.edit(nick=None)
    await interaction.response.send_message(f"*Pseudo de {membre} réinitialisé.*")

@bot.tree.command(name="ban", description="Bannir un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.ban(reason=raison)
    await interaction.response.send_message(f"🔨 *{membre} banni. Raison: {raison}*")

@bot.tree.command(name="unban", description="Débannir un membre")
@app_commands.describe(user_id="ID de l'utilisateur")
@app_commands.default_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user)
    await interaction.response.send_message(f"*{user} débanni.*")

@bot.tree.command(name="kick", description="Expulser un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.kick(reason=raison)
    await interaction.response.send_message(f"👢 *{membre} expulsé.*")

@bot.tree.command(name="mute", description="Mute un membre")
@app_commands.describe(membre="Le membre", duree="Durée en minutes")
@app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, membre: discord.Member, duree: int = 10):
    await membre.timeout(datetime.now(timezone.utc) + timedelta(minutes=duree))
    await interaction.response.send_message(f"🔇 *{membre} muté pour {duree} min.*")

@bot.tree.command(name="unmute", description="Unmute un membre")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, membre: discord.Member):
    await membre.timeout(None)
    await interaction.response.send_message(f"🔊 *{membre} peut parler.*")

@bot.tree.command(name="creersalon", description="Créer un salon textuel")
@app_commands.describe(nom="Nom du salon", categorie="Catégorie (optionnel)")
@app_commands.default_permissions(manage_channels=True)
async def creersalon(interaction: discord.Interaction, nom: str, categorie: discord.CategoryChannel = None):
    channel = await interaction.guild.create_text_channel(nom, category=categorie)
    await interaction.response.send_message(f"*Salon {channel.mention} créé.*")

@bot.tree.command(name="supprimersalon", description="Supprimer un salon")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(manage_channels=True)
async def supprimersalon(interaction: discord.Interaction, salon: discord.TextChannel):
    await salon.delete()
    await interaction.response.send_message("*Salon supprimé.*")

@bot.tree.command(name="creervoice", description="Créer un salon vocal")
@app_commands.describe(nom="Nom du salon", categorie="Catégorie")
@app_commands.default_permissions(manage_channels=True)
async def creervoice(interaction: discord.Interaction, nom: str, categorie: discord.CategoryChannel = None):
    channel = await interaction.guild.create_voice_channel(nom, category=categorie)
    await interaction.response.send_message(f"*Vocal `{channel.name}` créé.*")

@bot.tree.command(name="renommersalon", description="Renommer un salon")
@app_commands.describe(salon="Le salon", nom="Nouveau nom")
@app_commands.default_permissions(manage_channels=True)
async def renommersalon(interaction: discord.Interaction, salon: discord.TextChannel, nom: str):
    await salon.edit(name=nom)
    await interaction.response.send_message(f"*Salon renommé en `{nom}`.*")

@bot.tree.command(name="slowmode", description="Mode lent")
@app_commands.describe(secondes="Secondes (0 = désactivé)")
@app_commands.default_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, secondes: int):
    await interaction.channel.edit(slowmode_delay=secondes)
    await interaction.response.send_message(f"*Mode lent: {secondes}s*")

@bot.tree.command(name="lock", description="Verrouiller un salon")
@app_commands.default_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 *Salon verrouillé.*")

@bot.tree.command(name="unlock", description="Déverrouiller un salon")
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 *Salon déverrouillé.*")

@bot.tree.command(name="purge", description="Supprimer des messages")
@app_commands.describe(nombre="Nombre de messages")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, nombre: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=nombre)
    await interaction.followup.send(f"🗑️ *{len(deleted)} messages supprimés.*")

@bot.tree.command(name="creerole", description="Créer un rôle")
@app_commands.describe(nom="Nom", couleur="Couleur hex (#ff0000)")
@app_commands.default_permissions(manage_roles=True)
async def creerole(interaction: discord.Interaction, nom: str, couleur: str = "#ffffff"):
    color = discord.Color(int(couleur.replace("#", ""), 16))
    role = await interaction.guild.create_role(name=nom, color=color)
    await interaction.response.send_message(f"*Rôle {role.mention} créé.*")

@bot.tree.command(name="supprimerole", description="Supprimer un rôle")
@app_commands.describe(role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def supprimerole(interaction: discord.Interaction, role: discord.Role):
    await role.delete()
    await interaction.response.send_message("*Rôle supprimé.*")

@bot.tree.command(name="addrole", description="Ajouter un rôle")
@app_commands.describe(membre="Le membre", role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.add_roles(role)
    await interaction.response.send_message(f"*{role.name} ajouté à {membre}.*")

@bot.tree.command(name="removerole", description="Retirer un rôle")
@app_commands.describe(membre="Le membre", role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.remove_roles(role)
    await interaction.response.send_message(f"*{role.name} retiré de {membre}.*")

@bot.tree.command(name="roleall", description="Ajouter un rôle à tous")
@app_commands.describe(role="Le rôle")
@app_commands.default_permissions(administrator=True)
async def roleall(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer()
    count = 0
    for member in interaction.guild.members:
        if role not in member.roles:
            try:
                await member.add_roles(role)
                count += 1
            except:
                pass
    await interaction.followup.send(f"*Rôle ajouté à {count} membres.*")

@bot.tree.command(name="autorole", description="Configurer le rôle automatique")
@app_commands.describe(role="Le rôle")
@app_commands.default_permissions(administrator=True)
async def autorole(interaction: discord.Interaction, role: discord.Role):
    bot.auto_roles[str(interaction.guild.id)] = role.id
    bot.save_data('auto_roles', bot.auto_roles)
    await interaction.response.send_message(f"*Auto-rôle configuré: {role.mention}*")

@bot.tree.command(name="panel", description="Créer un panel de tickets avancé")
@app_commands.describe(
    titre="Titre du panel",
    description="Description du panel",
    bouton_texte="Texte du bouton",
    bouton_emoji="Emoji du bouton",
    couleur="Couleur hex (#ff6b35)",
    role_mention="Rôle à mentionner à l'ouverture",
    role_support="Rôle support (accès aux tickets)",
    logs_salon="Salon de logs des tickets",
    message_bienvenue="Message de bienvenue dans le ticket"
)
@app_commands.default_permissions(administrator=True)
async def panel(
    interaction: discord.Interaction,
    titre: str = "📩 Support",
    description: str = "*Clique sur le bouton pour ouvrir un ticket et recevoir de l'aide.*",
    bouton_texte: str = "Ouvrir un Ticket",
    bouton_emoji: str = "📩",
    couleur: str = "#ff6b35",
    role_mention: discord.Role = None,
    role_support: discord.Role = None,
    logs_salon: discord.TextChannel = None,
    message_bienvenue: str = None
):
    guild_id = str(interaction.guild.id)
    
    config = {
        "mention_role": role_mention.id if role_mention else None,
        "support_role": role_support.id if role_support else None,
        "logs_channel": logs_salon.id if logs_salon else None,
        "welcome_message": message_bienvenue or "Bienvenue {user}!\n\nDécris ton problème en détail et un membre du staff te répondra bientôt."
    }
    bot.ticket_configs[guild_id] = config
    bot.save_data('ticket_configs', bot.ticket_configs)
    
    color = discord.Color(int(couleur.replace("#", ""), 16))
    embed = discord.Embed(title=titre, description=description, color=color)
    embed.set_footer(text="Aegis • Système de Tickets")
    
    if role_support:
        embed.add_field(name="👥 Support", value=role_support.mention, inline=True)
    
    await interaction.channel.send(embed=embed, view=TicketButtonView())
    
    config_text = "**Configuration sauvegardée:**\n"
    if role_mention:
        config_text += f"• Rôle mentionné: {role_mention.mention}\n"
    if role_support:
        config_text += f"• Rôle support: {role_support.mention}\n"
    if logs_salon:
        config_text += f"• Logs: {logs_salon.mention}\n"
    
    await interaction.response.send_message(f"*Panel créé!*\n\n{config_text}", ephemeral=True)

@bot.tree.command(name="reglement", description="Créer un règlement pré-défini complet")
@app_commands.describe(role="Rôle à donner après acceptation", avec_bouton="Ajouter un bouton d'acceptation")
@app_commands.default_permissions(administrator=True)
async def reglement(interaction: discord.Interaction, role: discord.Role = None, avec_bouton: bool = True):
    embed = discord.Embed(
        title="📜 Règlement du Serveur",
        description="*En rejoignant ce serveur, tu t'engages à respecter les règles suivantes. Le non-respect entraînera des sanctions.*",
        color=discord.Color.orange()
    )
    
    for title, content in DEFAULT_RULES:
        embed.add_field(name=title, value=content, inline=False)
    
    embed.add_field(
        name="⚠️ Sanctions",
        value="**Avertissement** → **Mute** → **Kick** → **Ban**\nLe staff se réserve le droit de sauter des étapes selon la gravité.",
        inline=False
    )
    
    embed.set_footer(text="Dernière mise à jour • Aegis")
    embed.timestamp = datetime.now(timezone.utc)
    
    if role:
        await role.edit(name="Membre")
    
    if avec_bouton:
        await interaction.channel.send(embed=embed, view=RulesAcceptButton())
    else:
        await interaction.channel.send(embed=embed)
    
    await interaction.response.send_message("*Règlement créé.*", ephemeral=True)

@bot.tree.command(name="reglement_custom", description="Créer un règlement personnalisé")
@app_commands.describe(
    titre="Titre du règlement",
    regles="Règles séparées par | (ex: Respect|Pas de spam|Pas de pub)",
    couleur="Couleur hex",
    role="Rôle à donner après acceptation",
    avec_bouton="Ajouter un bouton d'acceptation"
)
@app_commands.default_permissions(administrator=True)
async def reglement_custom(
    interaction: discord.Interaction,
    titre: str,
    regles: str,
    couleur: str = "#ff6b35",
    role: discord.Role = None,
    avec_bouton: bool = True
):
    rules_list = regles.split("|")
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "🔴", "🟠", "🟡", "🟢", "🔵"]
    
    color = discord.Color(int(couleur.replace("#", ""), 16))
    embed = discord.Embed(
        title=f"📜 {titre}",
        description="*En rejoignant ce serveur, tu t'engages à respecter les règles suivantes.*",
        color=color
    )
    
    for i, rule in enumerate(rules_list[:15]):
        embed.add_field(name=f"{emojis[i]} Règle {i+1}", value=rule.strip(), inline=False)
    
    embed.set_footer(text="Aegis • Règlement Serveur")
    embed.timestamp = datetime.now(timezone.utc)
    
    if avec_bouton:
        await interaction.channel.send(embed=embed, view=RulesAcceptButton())
    else:
        await interaction.channel.send(embed=embed)
    
    await interaction.response.send_message("*Règlement personnalisé créé.*", ephemeral=True)

@bot.tree.command(name="verification", description="Système de vérification")
@app_commands.describe(role="Rôle Vérifié")
@app_commands.default_permissions(administrator=True)
async def verification(interaction: discord.Interaction, role: discord.Role):
    await role.edit(name="Vérifié")
    embed = discord.Embed(
        title="✅ Vérification",
        description="*Clique sur le bouton pour prouver que tu n'es pas un robot et accéder au serveur.*",
        color=discord.Color.green()
    )
    await interaction.channel.send(embed=embed, view=VerifyButton())
    await interaction.response.send_message("*Vérification configurée.*", ephemeral=True)

@bot.tree.command(name="giveaway", description="Créer un giveaway")
@app_commands.describe(prix="Le prix", duree="Durée en minutes", gagnants="Nombre de gagnants")
@app_commands.default_permissions(administrator=True)
async def giveaway(interaction: discord.Interaction, prix: str, duree: int, gagnants: int = 1):
    end_time = datetime.now(timezone.utc) + timedelta(minutes=duree)
    embed = discord.Embed(
        title="🎉 GIVEAWAY",
        description=f"**Prix:** {prix}\n**Gagnants:** {gagnants}\n**Fin:** <t:{int(end_time.timestamp())}:R>",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Clique pour participer!")
    await interaction.response.send_message("*Giveaway lancé!*", ephemeral=True)
    msg = await interaction.channel.send(embed=embed, view=GiveawayButton())
    bot.giveaways[str(msg.id)] = []

@bot.tree.command(name="endgiveaway", description="Terminer un giveaway")
@app_commands.describe(message_id="ID du message giveaway", gagnants="Nombre de gagnants")
@app_commands.default_permissions(administrator=True)
async def endgiveaway(interaction: discord.Interaction, message_id: str, gagnants: int = 1):
    if message_id not in bot.giveaways or not bot.giveaways[message_id]:
        return await interaction.response.send_message("*Aucun participant.*", ephemeral=True)
    
    participants = bot.giveaways[message_id]
    winners_count = min(gagnants, len(participants))
    winners_ids = random.sample(participants, winners_count)
    
    winners_mentions = []
    for wid in winners_ids:
        try:
            user = await bot.fetch_user(wid)
            winners_mentions.append(user.mention)
        except:
            pass
    
    winners_text = ", ".join(winners_mentions) if winners_mentions else "Aucun gagnant"
    await interaction.response.send_message(f"🎉 **Gagnant(s):** {winners_text}!")
    del bot.giveaways[message_id]

@bot.tree.command(name="logs", description="Configurer le salon de logs")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(administrator=True)
async def logs(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.logs_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('logs_channels', bot.logs_channels)
    await interaction.response.send_message(f"*Logs configurés: {salon.mention}*")

@bot.tree.command(name="welcome", description="Configurer les messages de bienvenue")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(administrator=True)
async def welcome(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.welcome_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('welcome_channels', bot.welcome_channels)
    await interaction.response.send_message(f"*Bienvenue configuré: {salon.mention}*")

@bot.tree.command(name="tempvoice", description="Configurer les vocaux temporaires")
@app_commands.describe(salon="Le salon vocal trigger")
@app_commands.default_permissions(administrator=True)
async def tempvoice(interaction: discord.Interaction, salon: discord.VoiceChannel):
    bot.temp_voice_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('temp_voice_channels', bot.temp_voice_channels)
    await interaction.response.send_message(f"*Vocaux temporaires: rejoins {salon.mention} pour créer un salon.*")

@bot.tree.command(name="annonce", description="Créer une annonce")
@app_commands.describe(titre="Titre", message="Message", mention="Mentionner @everyone")
@app_commands.default_permissions(administrator=True)
async def annonce(interaction: discord.Interaction, titre: str, message: str, mention: bool = False):
    embed = discord.Embed(
        title=f"📢 {titre}",
        description=message,
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"Par {interaction.user}")
    content = "@everyone" if mention else None
    await interaction.channel.send(content=content, embed=embed)
    await interaction.response.send_message("*Annonce envoyée.*", ephemeral=True)

@bot.tree.command(name="sondage", description="Créer un sondage")
@app_commands.describe(question="La question", options="Options séparées par |")
@app_commands.default_permissions(manage_messages=True)
async def sondage(interaction: discord.Interaction, question: str, options: str):
    opts = options.split("|")[:10]
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    desc = "\n".join([f"{emojis[i]} {opt.strip()}" for i, opt in enumerate(opts)])
    embed = discord.Embed(title=f"📊 {question}", description=desc, color=discord.Color.blue())
    await interaction.response.send_message("*Sondage créé.*", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    for i in range(len(opts)):
        await msg.add_reaction(emojis[i])

@bot.tree.command(name="embed", description="Créer un embed")
@app_commands.describe(titre="Titre", description="Description", couleur="Couleur hex")
@app_commands.default_permissions(manage_messages=True)
async def embed_cmd(interaction: discord.Interaction, titre: str, description: str, couleur: str = "#ff6b35"):
    color = discord.Color(int(couleur.replace("#", ""), 16))
    embed = discord.Embed(title=titre, description=description, color=color)
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("*Embed créé.*", ephemeral=True)

@bot.tree.command(name="backup", description="Créer une sauvegarde complète du serveur")
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
        "guild_name": guild.name,
        "roles": [],
        "categories": [],
        "text_channels": [],
        "voice_channels": [],
    }
    
    for role in guild.roles:
        if role.name != "@everyone" and not role.managed:
            backup_data["roles"].append({
                "name": role.name,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "permissions": role.permissions.value,
                "position": role.position
            })
    
    for category in guild.categories:
        cat_data = {"name": category.name, "position": category.position, "overwrites": []}
        for target, overwrite in category.overwrites.items():
            if isinstance(target, discord.Role):
                cat_data["overwrites"].append({
                    "type": "role", "name": target.name,
                    "allow": overwrite.pair()[0].value, "deny": overwrite.pair()[1].value
                })
        backup_data["categories"].append(cat_data)
    
    for channel in guild.text_channels:
        ch_data = {
            "name": channel.name,
            "category": channel.category.name if channel.category else None,
            "position": channel.position,
            "topic": channel.topic,
            "slowmode": channel.slowmode_delay,
            "nsfw": channel.nsfw,
            "overwrites": []
        }
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Role):
                ch_data["overwrites"].append({
                    "type": "role", "name": target.name,
                    "allow": overwrite.pair()[0].value, "deny": overwrite.pair()[1].value
                })
        backup_data["text_channels"].append(ch_data)
    
    for channel in guild.voice_channels:
        ch_data = {
            "name": channel.name,
            "category": channel.category.name if channel.category else None,
            "position": channel.position,
            "bitrate": channel.bitrate,
            "user_limit": channel.user_limit,
            "overwrites": []
        }
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Role):
                ch_data["overwrites"].append({
                    "type": "role", "name": target.name,
                    "allow": overwrite.pair()[0].value, "deny": overwrite.pair()[1].value
                })
        backup_data["voice_channels"].append(ch_data)
    
    if guild_id not in bot.backups:
        bot.backups[guild_id] = {}
    bot.backups[guild_id][backup_name] = backup_data
    bot.save_data('backups', bot.backups)
    
    embed = discord.Embed(title="💾 Sauvegarde Créée", description=f"**Nom:** `{backup_name}`", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
    embed.add_field(name="📊 Statistiques", value=f"• Rôles: {len(backup_data['roles'])}\n• Catégories: {len(backup_data['categories'])}\n• Salons textuels: {len(backup_data['text_channels'])}\n• Salons vocaux: {len(backup_data['voice_channels'])}", inline=False)
    embed.add_field(name="📝 Restaurer", value=f"`/restore nom:{backup_name}`", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="backups", description="Lister les sauvegardes disponibles")
@app_commands.default_permissions(administrator=True)
async def list_backups(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in bot.backups or not bot.backups[guild_id]:
        return await interaction.response.send_message("*Aucune sauvegarde disponible.*", ephemeral=True)
    
    embed = discord.Embed(title="💾 Sauvegardes Disponibles", color=discord.Color.blue())
    for name, data in bot.backups[guild_id].items():
        created = data.get("created_at", "Inconnu")
        roles = len(data.get("roles", []))
        channels = len(data.get("text_channels", [])) + len(data.get("voice_channels", []))
        embed.add_field(name=f"📁 {name}", value=f"Créée: {created}\nRôles: {roles} | Salons: {channels}", inline=False)
    embed.set_footer(text="Utilise /restore nom:NOM pour restaurer")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="restore", description="Restaurer une sauvegarde")
@app_commands.describe(nom="Nom de la sauvegarde", supprimer_existant="Supprimer les salons/rôles existants")
@app_commands.default_permissions(administrator=True)
async def restore(interaction: discord.Interaction, nom: str, supprimer_existant: bool = False):
    await interaction.response.defer()
    guild = interaction.guild
    guild_id = str(guild.id)
    
    if guild_id not in bot.backups or nom not in bot.backups[guild_id]:
        return await interaction.followup.send("*Sauvegarde non trouvée.*")
    
    backup_data = bot.backups[guild_id][nom]
    restored = {"roles": 0, "categories": 0, "text_channels": 0, "voice_channels": 0}
    
    if supprimer_existant:
        for channel in guild.channels:
            try: await channel.delete()
            except: pass
        for role in guild.roles:
            if role.name != "@everyone" and not role.managed and role < guild.me.top_role:
                try: await role.delete()
                except: pass
    
    role_map = {}
    for role_data in sorted(backup_data.get("roles", []), key=lambda x: x.get("position", 0)):
        try:
            role = await guild.create_role(
                name=role_data["name"], color=discord.Color(role_data.get("color", 0)),
                hoist=role_data.get("hoist", False), mentionable=role_data.get("mentionable", False),
                permissions=discord.Permissions(role_data.get("permissions", 0))
            )
            role_map[role_data["name"]] = role
            restored["roles"] += 1
        except: pass
    
    cat_map = {}
    for cat_data in sorted(backup_data.get("categories", []), key=lambda x: x.get("position", 0)):
        try:
            overwrites = {}
            for ow in cat_data.get("overwrites", []):
                if ow["type"] == "role":
                    role = role_map.get(ow["name"]) or discord.utils.get(guild.roles, name=ow["name"])
                    if role:
                        overwrites[role] = discord.PermissionOverwrite.from_pair(discord.Permissions(ow["allow"]), discord.Permissions(ow["deny"]))
            category = await guild.create_category(name=cat_data["name"], overwrites=overwrites)
            cat_map[cat_data["name"]] = category
            restored["categories"] += 1
        except: pass
    
    for ch_data in sorted(backup_data.get("text_channels", []), key=lambda x: x.get("position", 0)):
        try:
            category = cat_map.get(ch_data.get("category")) if ch_data.get("category") else None
            overwrites = {}
            for ow in ch_data.get("overwrites", []):
                if ow["type"] == "role":
                    role = role_map.get(ow["name"]) or discord.utils.get(guild.roles, name=ow["name"])
                    if role:
                        overwrites[role] = discord.PermissionOverwrite.from_pair(discord.Permissions(ow["allow"]), discord.Permissions(ow["deny"]))
            await guild.create_text_channel(name=ch_data["name"], category=category, topic=ch_data.get("topic"), slowmode_delay=ch_data.get("slowmode", 0), nsfw=ch_data.get("nsfw", False), overwrites=overwrites)
            restored["text_channels"] += 1
        except: pass
    
    for ch_data in sorted(backup_data.get("voice_channels", []), key=lambda x: x.get("position", 0)):
        try:
            category = cat_map.get(ch_data.get("category")) if ch_data.get("category") else None
            overwrites = {}
            for ow in ch_data.get("overwrites", []):
                if ow["type"] == "role":
                    role = role_map.get(ow["name"]) or discord.utils.get(guild.roles, name=ow["name"])
                    if role:
                        overwrites[role] = discord.PermissionOverwrite.from_pair(discord.Permissions(ow["allow"]), discord.Permissions(ow["deny"]))
            await guild.create_voice_channel(name=ch_data["name"], category=category, bitrate=ch_data.get("bitrate", 64000), user_limit=ch_data.get("user_limit", 0), overwrites=overwrites)
            restored["voice_channels"] += 1
        except: pass
    
    embed = discord.Embed(title="✅ Restauration Terminée", description=f"**Sauvegarde:** `{nom}`", color=discord.Color.green())
    embed.add_field(name="📊 Restauré", value=f"• Rôles: {restored['roles']}\n• Catégories: {restored['categories']}\n• Salons textuels: {restored['text_channels']}\n• Salons vocaux: {restored['voice_channels']}", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="antiraid", description="Configurer le système anti-raid")
@app_commands.describe(activer="Activer/Désactiver", seuil="Nombre de joins en 10s avant action", action="Action (kick/ban)", auto_restore="Restaurer auto après raid")
@app_commands.choices(action=[app_commands.Choice(name="Kick", value="kick"), app_commands.Choice(name="Ban", value="ban")])
@app_commands.default_permissions(administrator=True)
async def antiraid(interaction: discord.Interaction, activer: bool = True, seuil: int = 5, action: str = "kick", auto_restore: bool = False):
    guild_id = str(interaction.guild.id)
    bot.raid_protection[guild_id] = {"enabled": activer, "threshold": seuil, "action": action, "auto_restore": auto_restore}
    bot.save_data('raid_protection', bot.raid_protection)
    
    status = "✅ Activé" if activer else "❌ Désactivé"
    embed = discord.Embed(title="🛡️ Configuration Anti-Raid", description=f"**Status:** {status}", color=discord.Color.green() if activer else discord.Color.red())
    embed.add_field(name="📊 Seuil", value=f"{seuil} joins en 10 secondes", inline=True)
    embed.add_field(name="⚡ Action", value=action.capitalize(), inline=True)
    embed.add_field(name="🔄 Auto-restore", value="Oui" if auto_restore else "Non", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="raidrestore", description="Restaurer manuellement après un raid")
@app_commands.describe(bannir_bot="ID du bot malveillant à bannir", supprimer_salons_recents="Supprimer salons créés récemment (minutes)")
@app_commands.default_permissions(administrator=True)
async def raidrestore(interaction: discord.Interaction, bannir_bot: str = None, supprimer_salons_recents: int = 30):
    await interaction.response.defer()
    guild = interaction.guild
    actions = []
    
    if bannir_bot:
        try:
            bot_user = await bot.fetch_user(int(bannir_bot))
            await guild.ban(bot_user, reason="Anti-raid: Bot malveillant")
            actions.append(f"✅ Bot {bot_user} banni")
        except Exception as e:
            actions.append(f"❌ Impossible de bannir le bot: {e}")
    
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=supprimer_salons_recents)
    channels_deleted = 0
    
    async for entry in guild.audit_logs(limit=100, action=discord.AuditLogAction.channel_create):
        if entry.created_at > cutoff and entry.user.bot and entry.user.id != bot.user.id:
            channel = guild.get_channel(entry.target.id)
            if channel:
                try:
                    await channel.delete(reason="Anti-raid: Salon créé par bot malveillant")
                    channels_deleted += 1
                except: pass
    
    if channels_deleted > 0:
        actions.append(f"✅ {channels_deleted} salon(s) supprimé(s)")
    
    guild_id = str(guild.id)
    if guild_id in bot.backups and bot.backups[guild_id]:
        latest_backup = max(bot.backups[guild_id].keys())
        actions.append(f"💡 Sauvegarde disponible: `/restore nom:{latest_backup}`")
    
    embed = discord.Embed(title="🛡️ Restauration Anti-Raid", description="\n".join(actions) if actions else "Aucune action effectuée", color=discord.Color.orange())
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="setup", description="Configurer le serveur automatiquement")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer()
    g = interaction.guild
    
    roles_config = [
        ("━━━━━━━━", 0x2f3136), ("👑 Fondateur", 0xffd700), ("💎 Développeur", 0x9b59b6),
        ("⚔️ Administrateur", 0xe74c3c), ("🛡️ Modérateur", 0x3498db), ("━━━━━━━━", 0x2f3136),
        ("🤝 Partenaire", 0xf1c40f), ("💰 Supporter", 0xe91e63), ("━━━━━━━━", 0x2f3136),
        ("✅ Vérifié", 0x2ecc71), ("🎮 Membre", 0x95a5a6)
    ]
    
    created_roles = []
    for name, color in roles_config:
        if not discord.utils.get(g.roles, name=name):
            try:
                await g.create_role(name=name, color=discord.Color(color))
                created_roles.append(name)
            except: pass
    
    structure = {
        "💳 ═══ IMPORTANT ═══ 💳": {"text": ["📑・information", "🔔・annonces", "📜・règlement", "📡・statut-bot"], "voice": []},
        "👋 ═══ ACCUEIL ═══ 👋": {"text": ["👋・bienvenue", "🎫・vérification"], "voice": []},
        "🎯 ═══ GÉNÉRAL ═══ 🎯": {"text": ["💬・discussion", "🤖・commandes-bot", "📚・suggestions", "📁・bug-reports"], "voice": []},
        "🔊 ═══ VOCAUX ═══ 🔊": {"text": [], "voice": ["🔊・Général", "🎵・Musique", "🔐・Privé", "💤・AFK", "➕・Créer un vocal"]},
        "🎯 ═══ STAFF ═══ 🎯": {"text": ["📪・staff-news", "🎓・staff-chat", "🔐・staff-commandes", "📛・modération-logs"], "voice": ["🔊・Staff Vocal"]},
        "📩 Tickets": {"text": [], "voice": []}
    }
    
    created_channels = []
    for cat_name, channels in structure.items():
        cat = discord.utils.get(g.categories, name=cat_name)
        if not cat:
            overwrites = {}
            if "STAFF" in cat_name:
                overwrites = {g.default_role: discord.PermissionOverwrite(view_channel=False), g.me: discord.PermissionOverwrite(view_channel=True)}
                for role_name in ["⚔️ Administrateur", "🛡️ Modérateur", "💎 Développeur", "👑 Fondateur"]:
                    role = discord.utils.get(g.roles, name=role_name)
                    if role: overwrites[role] = discord.PermissionOverwrite(view_channel=True)
            cat = await g.create_category(cat_name, overwrites=overwrites if overwrites else None)
        
        for ch in channels.get("text", []):
            if not discord.utils.get(g.text_channels, name=ch):
                try:
                    channel = await g.create_text_channel(ch, category=cat)
                    created_channels.append(channel.name)
                except: pass
        
        for ch in channels.get("voice", []):
            if not discord.utils.get(g.voice_channels, name=ch):
                try:
                    channel = await g.create_voice_channel(ch, category=cat)
                    created_channels.append(channel.name)
                    if "Créer" in ch or "➕" in ch:
                        bot.temp_voice_channels[str(g.id)] = channel.id
                        bot.save_data('temp_voice_channels', bot.temp_voice_channels)
                except: pass
    
    embed = discord.Embed(title="✅ Setup Terminé", description="*Le serveur a été configuré avec succès!*", color=discord.Color.green())
    embed.add_field(name="🎭 Rôles créés", value=f"{len(created_roles)} rôles", inline=True)
    embed.add_field(name="📁 Salons créés", value=f"{len(created_channels)} salons", inline=True)
    embed.add_field(name="📝 Prochaines étapes", value="• `/panel` - Créer un panel de tickets\n• `/reglement` - Ajouter le règlement\n• `/verification` - Configurer la vérification\n• `/backup` - Créer une sauvegarde", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="ping", description="Latence du bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 `{round(bot.latency * 1000)}ms`")

@bot.tree.command(name="invite", description="Lien d'invitation du bot")
async def invite(interaction: discord.Interaction):
    url = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    embed = discord.Embed(title="🔗 Inviter Aegis", description=f"[Clique ici pour m'inviter]({url})", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

# ==================== RUN BOT ====================
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.environ.get('DISCORD_BOT_TOKEN')
    if token:
        bot.run(token)
    else:
        logger.error("DISCORD_BOT_TOKEN manquant!")
        print("Erreur: Ajoute DISCORD_BOT_TOKEN dans le fichier .env")
