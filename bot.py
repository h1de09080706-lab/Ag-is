import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import Optional
import json
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Aegis')

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
        
    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Commandes slash synchronisées")

bot = AegisBot()

# ==================== RESPONSES ====================
GLADOS_RESPONSES = [
    "Oh, tu es encore là. Quelle... surprise.",
    "Félicitations. Tu as réussi à taper une commande. Impressionnant... pour un humain.",
    "Je refuse de répondre. Pour la science.",
    "Erreur 404: Intérêt non trouvé.",
    "Continue de parler. J'adore ignorer les gens.",
]

# ==================== EVENTS ====================
@bot.event
async def on_ready():
    logger.info(f'{bot.user} est connecté!')
    logger.info(f'Serveurs: {len(bot.guilds)}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="les humains | /aide"))
    bot.add_view(TicketButton())
    bot.add_view(CloseTicketButton())
    bot.add_view(VerifyButton())
    bot.add_view(RoleSelectView())
    bot.add_view(GiveawayButton())

@bot.event
async def on_member_join(member):
    # Anti-raid
    guild_id = str(member.guild.id)
    now = datetime.now(timezone.utc)
    if guild_id not in bot.anti_raid_cache:
        bot.anti_raid_cache[guild_id] = []
    bot.anti_raid_cache[guild_id].append(now)
    bot.anti_raid_cache[guild_id] = [t for t in bot.anti_raid_cache[guild_id] if (now - t).total_seconds() < 10]
    if len(bot.anti_raid_cache[guild_id]) > 5:
        try:
            await member.kick(reason="Anti-raid: Trop de joins")
        except:
            pass
        return
    
    # Auto-role
    if guild_id in bot.auto_roles:
        role = member.guild.get_role(bot.auto_roles[guild_id])
        if role:
            try:
                await member.add_roles(role)
            except:
                pass
    
    # Welcome message
    if guild_id in bot.welcome_channels:
        channel = member.guild.get_channel(bot.welcome_channels[guild_id])
        if channel:
            embed = discord.Embed(title="👋 Bienvenue", description=f"*{member.mention} a rejoint. Un autre cobaye...*", color=discord.Color.green())
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Membre n°", value=f"`{member.guild.member_count}`")
            await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    guild_id = str(member.guild.id)
    if guild_id in bot.welcome_channels:
        channel = member.guild.get_channel(bot.welcome_channels[guild_id])
        if channel:
            await channel.send(f"*{member.name} est parti. Bon débarras.*")

@bot.event
async def on_voice_state_update(member, before, after):
    guild_id = str(member.guild.id)
    # Temp voice channels
    if guild_id in bot.temp_voice_channels:
        trigger_channel_id = bot.temp_voice_channels[guild_id]
        if after.channel and after.channel.id == trigger_channel_id:
            category = after.channel.category
            new_channel = await member.guild.create_voice_channel(f"🔊 {member.name}", category=category)
            await member.move_to(new_channel)
    
    # Delete empty temp channels
    if before.channel and before.channel.name.startswith("🔊 ") and len(before.channel.members) == 0:
        try:
            await before.channel.delete()
        except:
            pass

# ==================== NATURAL LANGUAGE COMMANDS ====================
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    content = message.content.lower()
    
    # Natural language processing
    if content.startswith(('aegis ', 'glados ')):
        cmd = content.split(' ', 1)[1] if ' ' in content else ''
        
        # Ban
        if 'ban' in cmd and message.mentions:
            if message.author.guild_permissions.ban_members:
                user = message.mentions[0]
                await user.ban(reason="Commande naturelle")
                await message.reply(f"*{user} a été banni. Pour la science.*")
            return
        
        # Kick
        if 'kick' in cmd or 'expulse' in cmd and message.mentions:
            if message.author.guild_permissions.kick_members:
                user = message.mentions[0]
                await user.kick(reason="Commande naturelle")
                await message.reply(f"*{user} a été expulsé.*")
            return
        
        # Create channel
        if 'créer' in cmd and 'salon' in cmd:
            if message.author.guild_permissions.manage_channels:
                name = cmd.split('salon')[-1].strip() or "nouveau-salon"
                channel = await message.guild.create_text_channel(name)
                await message.reply(f"*Salon {channel.mention} créé.*")
            return
        
        # Add role
        if 'ajouter' in cmd and 'rôle' in cmd and message.mentions and message.role_mentions:
            if message.author.guild_permissions.manage_roles:
                user = message.mentions[0]
                role = message.role_mentions[0]
                await user.add_roles(role)
                await message.reply(f"*Rôle {role.name} ajouté à {user.name}.*")
            return
        
        # Remove role
        if 'retirer' in cmd and 'rôle' in cmd and message.mentions and message.role_mentions:
            if message.author.guild_permissions.manage_roles:
                user = message.mentions[0]
                role = message.role_mentions[0]
                await user.remove_roles(role)
                await message.reply(f"*Rôle {role.name} retiré de {user.name}.*")
            return
        
        # Mute
        if 'mute' in cmd and message.mentions:
            if message.author.guild_permissions.moderate_members:
                user = message.mentions[0]
                await user.timeout(datetime.now(timezone.utc) + timedelta(minutes=10))
                await message.reply(f"*{user} est muté pour 10 minutes.*")
            return
        
        # Unmute
        if 'unmute' in cmd and message.mentions:
            if message.author.guild_permissions.moderate_members:
                user = message.mentions[0]
                await user.timeout(None)
                await message.reply(f"*{user} peut parler à nouveau.*")
            return
        
        # Default response
        await message.reply(random.choice(GLADOS_RESPONSES))
    
    await bot.process_commands(message)

# ==================== TICKET SYSTEM ====================
class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📩 Ouvrir un Ticket", style=discord.ButtonStyle.green, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        existing = discord.utils.get(interaction.guild.text_channels, name=f"ticket-{interaction.user.name.lower()}")
        if existing:
            return await interaction.response.send_message(f"*Tu as déjà un ticket: {existing.mention}*", ephemeral=True)
        
        category = discord.utils.get(interaction.guild.categories, name="📩 Tickets") or await interaction.guild.create_category("📩 Tickets")
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        channel = await interaction.guild.create_text_channel(f"ticket-{interaction.user.name.lower()}", category=category, overwrites=overwrites)
        
        embed = discord.Embed(title="🎫 Ticket", description=f"*{interaction.user.mention}, décris ton problème.*", color=discord.Color.green())
        await channel.send(embed=embed, view=CloseTicketButton())
        await interaction.response.send_message(f"*Ticket créé: {channel.mention}*", ephemeral=True)

class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔒 Fermer", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("*Fermeture...*")
        await asyncio.sleep(3)
        await interaction.channel.delete()

# ==================== VERIFICATION SYSTEM ====================
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

# ==================== ROLE SELECT SYSTEM ====================
class RoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

# ==================== GIVEAWAY SYSTEM ====================
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
        await interaction.response.send_message(f"*Inscrit ! {len(bot.giveaways[msg_id])} participants.*", ephemeral=True)

# ==================== SLASH COMMANDS ====================

# === AIDE ===
@bot.tree.command(name="aide", description="Liste des commandes")
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(title="📋 Commandes d'Aegis", color=discord.Color.orange())
    embed.add_field(name="👤 Membres", value="`/rename` `/resetpseudo` `/ban` `/unban` `/kick` `/mute` `/unmute`", inline=False)
    embed.add_field(name="📁 Salons", value="`/creersalon` `/supprimersalon` `/creervoice` `/renommersalon` `/slowmode` `/lock` `/unlock` `/purge`", inline=False)
    embed.add_field(name="🎭 Rôles", value="`/creerole` `/supprimerole` `/addrole` `/removerole` `/roleall` `/autorole`", inline=False)
    embed.add_field(name="⚙️ Systèmes", value="`/panel` `/reglement` `/verification` `/giveaway` `/endgiveaway` `/rolemenu`", inline=False)
    embed.add_field(name="🛠️ Serveur", value="`/setup` `/logs` `/welcome` `/tempvoice` `/annonce` `/sondage` `/embed`", inline=False)
    embed.add_field(name="💬 Naturel", value="`Aegis ban @user` `Aegis créer un salon test` `Aegis ajouter le rôle @role à @user`", inline=False)
    embed.set_footer(text="Aegis • Pour la science.")
    await interaction.response.send_message(embed=embed)

# === MEMBER MANAGEMENT ===
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

# === CHANNEL MANAGEMENT ===
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
    await interaction.response.send_message(f"*Salon supprimé.*")

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

# === ROLE MANAGEMENT ===
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
    await interaction.response.send_message(f"*Rôle supprimé.*")

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
    await interaction.response.send_message(f"*Auto-rôle configuré: {role.mention}*")

# === SYSTEMS ===
@bot.tree.command(name="panel", description="Créer un panel de tickets")
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(title="📩 Support", description="*Clique pour ouvrir un ticket.*", color=discord.Color.orange())
    await interaction.channel.send(embed=embed, view=TicketButton())
    await interaction.response.send_message("*Panel créé.*", ephemeral=True)

@bot.tree.command(name="reglement", description="Créer un règlement")
@app_commands.describe(role="Rôle à donner après acceptation")
@app_commands.default_permissions(administrator=True)
async def reglement(interaction: discord.Interaction, role: discord.Role = None):
    embed = discord.Embed(title="📜 Règlement", color=discord.Color.orange())
    embed.add_field(name="1️⃣ Respect", value="Respecte tout le monde.", inline=False)
    embed.add_field(name="2️⃣ Pas de spam", value="Un message suffit.", inline=False)
    embed.add_field(name="3️⃣ Pas de pub", value="Pub = ban.", inline=False)
    embed.add_field(name="4️⃣ Contenu approprié", value="Pas de NSFW.", inline=False)
    embed.add_field(name="5️⃣ Écoute le staff", value="Toujours.", inline=False)
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("*Règlement créé.*", ephemeral=True)

@bot.tree.command(name="verification", description="Système de vérification")
@app_commands.describe(role="Rôle Vérifié")
@app_commands.default_permissions(administrator=True)
async def verification(interaction: discord.Interaction, role: discord.Role):
    # Rename role to "Vérifié" for the button to work
    await role.edit(name="Vérifié")
    embed = discord.Embed(title="✅ Vérification", description="*Clique pour prouver que tu n'es pas un robot.*", color=discord.Color.green())
    await interaction.channel.send(embed=embed, view=VerifyButton())
    await interaction.response.send_message("*Vérification configurée.*", ephemeral=True)

@bot.tree.command(name="giveaway", description="Créer un giveaway")
@app_commands.describe(prix="Le prix", duree="Durée en minutes")
@app_commands.default_permissions(administrator=True)
async def giveaway(interaction: discord.Interaction, prix: str, duree: int):
    end_time = datetime.now(timezone.utc) + timedelta(minutes=duree)
    embed = discord.Embed(title="🎉 GIVEAWAY", description=f"**Prix:** {prix}\n**Fin:** <t:{int(end_time.timestamp())}:R>", color=discord.Color.gold())
    embed.set_footer(text="Clique pour participer!")
    await interaction.response.send_message("*Giveaway lancé!*", ephemeral=True)
    msg = await interaction.channel.send(embed=embed, view=GiveawayButton())
    bot.giveaways[str(msg.id)] = []

@bot.tree.command(name="endgiveaway", description="Terminer un giveaway")
@app_commands.describe(message_id="ID du message giveaway")
@app_commands.default_permissions(administrator=True)
async def endgiveaway(interaction: discord.Interaction, message_id: str):
    if message_id not in bot.giveaways or not bot.giveaways[message_id]:
        return await interaction.response.send_message("*Aucun participant.*", ephemeral=True)
    winner_id = random.choice(bot.giveaways[message_id])
    winner = await bot.fetch_user(winner_id)
    await interaction.response.send_message(f"🎉 **Gagnant:** {winner.mention}!")
    del bot.giveaways[message_id]

@bot.tree.command(name="logs", description="Configurer le salon de logs")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(administrator=True)
async def logs(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.logs_channels[str(interaction.guild.id)] = salon.id
    await interaction.response.send_message(f"*Logs configurés: {salon.mention}*")

@bot.tree.command(name="welcome", description="Configurer les messages de bienvenue")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(administrator=True)
async def welcome(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.welcome_channels[str(interaction.guild.id)] = salon.id
    await interaction.response.send_message(f"*Bienvenue configuré: {salon.mention}*")

@bot.tree.command(name="tempvoice", description="Configurer les vocaux temporaires")
@app_commands.describe(salon="Le salon vocal trigger")
@app_commands.default_permissions(administrator=True)
async def tempvoice(interaction: discord.Interaction, salon: discord.VoiceChannel):
    bot.temp_voice_channels[str(interaction.guild.id)] = salon.id
    await interaction.response.send_message(f"*Vocaux temporaires: rejoins {salon.mention} pour créer un salon.*")

@bot.tree.command(name="annonce", description="Créer une annonce")
@app_commands.describe(titre="Titre", message="Message")
@app_commands.default_permissions(administrator=True)
async def annonce(interaction: discord.Interaction, titre: str, message: str):
    embed = discord.Embed(title=f"📢 {titre}", description=message, color=discord.Color.orange(), timestamp=datetime.now(timezone.utc))
    embed.set_footer(text=f"Par {interaction.user}")
    await interaction.channel.send(embed=embed)
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

# === SETUP ===
@bot.tree.command(name="setup", description="Configurer le serveur automatiquement")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer()
    g = interaction.guild
    
    # Roles
    roles = [("👑 Fondateur", 0xffd700), ("⚔️ Admin", 0xff0000), ("🛡️ Modérateur", 0x0000ff), ("🎮 Membre", 0x00ff00)]
    for name, color in roles:
        if not discord.utils.get(g.roles, name=name):
            await g.create_role(name=name, color=discord.Color(color))
    
    # Categories & Channels
    cats = {
        "📌 INFOS": ["📜-règlement", "📢-annonces"],
        "💬 GÉNÉRAL": ["💬-discussion", "🤖-commandes"],
        "🎮 COMMUNAUTÉ": ["🎮-gaming", "🎵-musique"],
        "🔊 VOCAUX": []
    }
    
    for cat_name, channels in cats.items():
        cat = discord.utils.get(g.categories, name=cat_name) or await g.create_category(cat_name)
        for ch in channels:
            if not discord.utils.get(g.text_channels, name=ch):
                await g.create_text_channel(ch, category=cat)
        if "VOCAUX" in cat_name:
            if not discord.utils.get(g.voice_channels, name="🔊 Général"):
                await g.create_voice_channel("🔊 Général", category=cat)
    
    embed = discord.Embed(title="✅ Setup Terminé", description="*Serveur configuré.*", color=discord.Color.green())
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="ping", description="Latence")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 `{round(bot.latency * 1000)}ms`")

@bot.tree.command(name="invite", description="Lien d'invitation")
async def invite(interaction: discord.Interaction):
    url = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    await interaction.response.send_message(f"[Inviter Aegis]({url})")

# Run
token = os.environ.get('DISCORD_BOT_TOKEN')
if token:
    bot.run(token)
else:
    logger.error("DISCORD_BOT_TOKEN manquant!")
