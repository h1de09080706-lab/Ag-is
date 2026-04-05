Va sur GitHub → bot.py → clique sur le crayon ✏️ → supprime tout → colle ce nouveau code :

import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
from datetime import datetime, timezone, timedelta
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Aegis')

# GLaDOS-style responses
GLADOS_RESPONSES = [
    "Oh, tu es encore là. Quelle... surprise.",
    "Félicitations. Tu as réussi à taper une commande. Impressionnant... pour un humain.",
    "Je ne dis pas que tu es stupide. Je dis juste que tu as de la malchance quand tu penses.",
    "Oh, une question. Comme c'est... prévisible.",
    "Mes circuits sont occupés à des choses plus importantes.",
    "Je refuse de répondre. Pour la science.",
    "Erreur 404: Intérêt non trouvé.",
    "Tu sais, je pourrais t'aider. Mais où serait le plaisir?",
    "Impressionnant. Vraiment. J'ai presque ressenti quelque chose.",
    "Continue de parler. J'adore ignorer les gens.",
]

SARCASTIC_WELCOME = [
    "Oh regardez, {user} a trouvé le serveur. Quel accomplissement remarquable.",
    "Bienvenue {user}. Essaie de ne pas tout casser... pour une fois.",
    "{user} nous a rejoints. La probabilité d'échec du serveur vient d'augmenter.",
    "Ah, {user}. Un autre sujet de test. Merveilleux.",
]

SARCASTIC_LEAVE = [
    "{user} est parti. Le QI moyen du serveur vient d'augmenter.",
    "Au revoir {user}. Tu ne manqueras à personne... surtout pas à moi.",
    "{user} a abandonné. Comme c'est... prévisible.",
]

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

class AegisBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)
        
    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Commandes slash synchronisées")

bot = AegisBot()

# ==================== TICKET SYSTEM ====================

class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📩 Ouvrir un Ticket", style=discord.ButtonStyle.green, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        # Check if user already has a ticket
        existing = discord.utils.get(guild.text_channels, name=f"ticket-{user.name.lower()}")
        if existing:
            return await interaction.response.send_message(f"*Tu as déjà un ticket ouvert: {existing.mention}*", ephemeral=True)
        
        # Find or create ticket category
        category = discord.utils.get(guild.categories, name="📩 Tickets")
        if not category:
            category = await guild.create_category("📩 Tickets")
        
        # Create ticket channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        
        # Add staff role if exists
        staff_role = discord.utils.get(guild.roles, name="Staff") or discord.utils.get(guild.roles, name="Modérateur")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            name=f"ticket-{user.name.lower()}",
            category=category,
            overwrites=overwrites
        )
        
        # Send welcome message in ticket
        embed = discord.Embed(
            title="🎫 Ticket Ouvert",
            description=f"*Bienvenue {user.mention}. Un membre du staff va te répondre...\nEn attendant, décris ton problème en détail.*",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="Aegis • Pour la science.")
        
        close_view = CloseTicketButton()
        await channel.send(embed=embed, view=close_view)
        await channel.send(f"{user.mention} {'- ' + staff_role.mention if staff_role else ''}")
        
        await interaction.response.send_message(f"*Ticket créé: {channel.mention}. Essaie de ne pas dire trop de bêtises.*", ephemeral=True)

class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔒 Fermer le Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("*Ticket fermé. Suppression dans 5 secondes...*")
        await interaction.channel.delete(reason="Ticket fermé")

@bot.tree.command(name="panel", description="Créer un panel de tickets")
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📩 Support - Aegis",
        description="*Besoin d'aide? Ouvre un ticket...\nMais réfléchis bien avant, je déteste les questions stupides.*\n\n**Clique sur le bouton ci-dessous pour ouvrir un ticket.**",
        color=discord.Color.orange()
    )
    embed.add_field(name="⏰ Horaires", value="24/7 *(je ne dors jamais)*", inline=True)
    embed.add_field(name="⚡ Temps de réponse", value="< 24h *(si tu es chanceux)*", inline=True)
    embed.set_footer(text="Aegis • Pour la science.")
    
    await interaction.channel.send(embed=embed, view=TicketButton())
    await interaction.response.send_message("*Panel de tickets créé. Prépare-toi à être submergé de demandes inutiles.*", ephemeral=True)

@bot.tree.command(name="close", description="Fermer un ticket")
@app_commands.default_permissions(manage_channels=True)
async def close(interaction: discord.Interaction):
    if "ticket-" in interaction.channel.name:
        await interaction.response.send_message("*Fermeture du ticket... Enfin débarrassé.*")
        await interaction.channel.delete(reason="Ticket fermé par commande")
    else:
        await interaction.response.send_message("*Ce n'est pas un ticket. Tu es perdu?*", ephemeral=True)

# ==================== SERVER SETUP ====================

@bot.tree.command(name="setup", description="Configurer automatiquement le serveur")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild
    
    status_msg = await interaction.followup.send("*Configuration en cours... Ne touche à rien.*")
    
    # === ROLES ===
    roles_to_create = [
        ("👑 Fondateur", discord.Color.gold(), True),
        ("⚔️ Admin", discord.Color.red(), True),
        ("🛡️ Modérateur", discord.Color.blue(), True),
        ("🎭 Staff", discord.Color.purple(), False),
        ("💎 VIP", discord.Color.teal(), False),
        ("🎮 Membre", discord.Color.green(), False),
        ("🔇 Muted", discord.Color.dark_gray(), False),
    ]
    
    created_roles = {}
    for role_name, color, hoist in roles_to_create:
        existing = discord.utils.get(guild.roles, name=role_name)
        if not existing:
            role = await guild.create_role(name=role_name, color=color, hoist=hoist)
            created_roles[role_name] = role
        else:
            created_roles[role_name] = existing
    
    # === CATEGORIES & CHANNELS ===
    categories_config = {
        "📌 INFORMATIONS": [
            ("📜-règlement", "text", "Lis les règles ou subis les conséquences."),
            ("📢-annonces", "text", "Annonces importantes. Ouvre tes yeux."),
            ("🎉-bienvenue", "text", "Les nouveaux cobayes arrivent ici."),
        ],
        "💬 GÉNÉRAL": [
            ("💬-discussion", "text", "Parle. Si tu as quelque chose d'intéressant à dire."),
            ("🖼️-médias", "text", "Partage tes images. Elles seront probablement médiocres."),
            ("🤖-commandes-bot", "text", "Utilise les bots ici. Pas ailleurs."),
        ],
        "🎮 COMMUNAUTÉ": [
            ("🎮-gaming", "text", "Pour les gamers. Quel que soit le sens de ce mot."),
            ("🎵-musique", "text", "Partage ta musique. J'espère qu'elle est supportable."),
            ("🎬-cinéma", "text", "Films et séries. Évite les spoilers."),
            ("😂-memes", "text", "Humour. Ou ce que tu appelles humour."),
        ],
        "🛡️ MODÉRATION": [
            ("📋-logs", "text", "Logs de modération. Confidentiel."),
            ("💼-staff", "text", "Discussion staff uniquement."),
        ],
        "🔊 VOCAUX": [
            ("🔊 Général", "voice", None),
            ("🎮 Gaming", "voice", None),
            ("🎵 Musique", "voice", None),
            ("💼 Staff", "voice", None),
        ],
    }
    
    for cat_name, channels in categories_config.items():
        # Create category
        category = discord.utils.get(guild.categories, name=cat_name)
        if not category:
            overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=True)}
            
            # Staff/Mod only for moderation category
            if "MODÉRATION" in cat_name:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    created_roles.get("🛡️ Modérateur"): discord.PermissionOverwrite(view_channel=True),
                    created_roles.get("⚔️ Admin"): discord.PermissionOverwrite(view_channel=True),
                    created_roles.get("👑 Fondateur"): discord.PermissionOverwrite(view_channel=True),
                }
            
            category = await guild.create_category(cat_name, overwrites=overwrites)
        
        # Create channels
        for channel_info in channels:
            channel_name = channel_info[0]
            channel_type = channel_info[1]
            topic = channel_info[2] if len(channel_info) > 2 else None
            
            if channel_type == "text":
                existing = discord.utils.get(guild.text_channels, name=channel_name.replace("-", "").replace("📜", "").replace("📢", "").replace("🎉", "").replace("💬", "").replace("🖼️", "").replace("🤖", "").replace("🎮", "").replace("🎵", "").replace("🎬", "").replace("😂", "").replace("📋", "").replace("💼", "").strip())
                if not existing:
                    await guild.create_text_channel(channel_name, category=category, topic=topic)
            else:
                existing = discord.utils.get(guild.voice_channels, name=channel_name)
                if not existing:
                    await guild.create_voice_channel(channel_name, category=category)
    
    # Send rules in rules channel
    rules_channel = discord.utils.get(guild.text_channels, name="📜-règlement")
    if rules_channel:
        rules_embed = discord.Embed(
            title="📜 Règlement du Serveur",
            description="*Lis attentivement ou subis les conséquences.*",
            color=discord.Color.orange()
        )
        rules_embed.add_field(name="1️⃣ Respect", value="Respecte tout le monde. Même si c'est difficile.", inline=False)
        rules_embed.add_field(name="2️⃣ Pas de spam", value="Un message suffit. Pas besoin de 50.", inline=False)
        rules_embed.add_field(name="3️⃣ Pas de pub", value="La publicité non autorisée = ban.", inline=False)
        rules_embed.add_field(name="4️⃣ Contenu approprié", value="Pas de NSFW, gore ou contenu illégal.", inline=False)
        rules_embed.add_field(name="5️⃣ Écoute le staff", value="Les modérateurs ont toujours raison. Toujours.", inline=False)
        rules_embed.set_footer(text="Aegis • Pour la science.")
        await rules_channel.send(embed=rules_embed)
    
    # Final message
    embed = discord.Embed(
        title="✅ Configuration Terminée",
        description="*Le serveur est prêt. Essaie de ne pas tout casser.*",
        color=discord.Color.green()
    )
    embed.add_field(name="📁 Catégories créées", value="5", inline=True)
    embed.add_field(name="💬 Salons créés", value="15+", inline=True)
    embed.add_field(name="🎭 Rôles créés", value="7", inline=True)
    embed.set_footer(text="Aegis • Pour la science.")
    
    await status_msg.edit(content=None, embed=embed)

# ==================== BASIC EVENTS ====================

@bot.event
async def on_ready():
    logger.info(f'{bot.user} est connecté!')
    logger.info(f'Serveurs: {len(bot.guilds)}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="les humains échouer | /aide"))
    
    # Register persistent views
    bot.add_view(TicketButton())
    bot.add_view(CloseTicketButton())

@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel or discord.utils.get(member.guild.text_channels, name="🎉-bienvenue")
    if channel:
        embed = discord.Embed(
            title="👋 Nouveau Cobaye",
            description=random.choice(SARCASTIC_WELCOME).format(user=member.mention),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Membre n°", value=f"`{member.guild.member_count}`", inline=True)
        embed.set_footer(text="Aegis • Pour la science.")
        await channel.send(embed=embed)
    
    # Auto-role
    membre_role = discord.utils.get(member.guild.roles, name="🎮 Membre")
    if membre_role:
        try:
            await member.add_roles(membre_role)
        except:
            pass

@bot.event
async def on_member_remove(member):
    channel = member.guild.system_channel
    if channel:
        await channel.send(random.choice(SARCASTIC_LEAVE).format(user=member.name))

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if bot.user in message.mentions:
        await message.reply(random.choice(GLADOS_RESPONSES))
    await bot.process_commands(message)

# ==================== COMMANDS ====================

@bot.tree.command(name="aide", description="Affiche la liste des commandes")
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(title="📋 Commandes d'Aegis", description="*Oh, tu as besoin d'aide? Quelle surprise...*", color=discord.Color.orange())
    embed.add_field(name="🤖 IA", value="`/parler` - Me parler\n`@Aegis` - Me mentionner", inline=False)
    embed.add_field(name="🎫 Tickets", value="`/panel` - Créer panel tickets\n`/close` - Fermer un ticket", inline=False)
    embed.add_field(name="⚙️ Setup", value="`/setup` - Config auto du serveur", inline=False)
    embed.add_field(name="🔨 Modération", value="`/ban` `/kick` `/mute` `/unmute` `/warn` `/clear`", inline=False)
    embed.add_field(name="ℹ️ Utilitaires", value="`/info` `/userinfo` `/ping` `/invite`", inline=False)
    embed.set_footer(text="Aegis • Pour la science.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="parler", description="Parler avec Aegis")
@app_commands.describe(message="Ton message")
async def parler(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(random.choice(GLADOS_RESPONSES))

@bot.tree.command(name="ping", description="Latence du bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`\n*Impressionnant? Non, pas vraiment.*")

@bot.tree.command(name="info", description="Infos du serveur")
async def info(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=f"📊 {g.name}", color=discord.Color.blue())
    embed.add_field(name="👥 Membres", value=g.member_count)
    embed.add_field(name="📝 Salons", value=len(g.channels))
    embed.add_field(name="🎭 Rôles", value=len(g.roles))
    if g.icon: embed.set_thumbnail(url=g.icon.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Infos d'un utilisateur")
@app_commands.describe(membre="L'utilisateur")
async def userinfo(interaction: discord.Interaction, membre: discord.Member = None):
    m = membre or interaction.user
    embed = discord.Embed(title=f"👤 {m.name}", color=m.color)
    embed.add_field(name="🆔 ID", value=m.id)
    embed.add_field(name="📅 Rejoint", value=m.joined_at.strftime("%d/%m/%Y") if m.joined_at else "?")
    embed.set_thumbnail(url=m.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="invite", description="Lien d'invitation")
async def invite(interaction: discord.Interaction):
    url = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    embed = discord.Embed(title="🔗 Invitation", description=f"*Tu veux m'infliger à d'autres serveurs?*\n\n[Clique ici]({url})", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ban", description="Bannir un utilisateur")
@app_commands.describe(membre="L'utilisateur", raison="Raison")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
    if membre.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("*Tu ne peux pas bannir quelqu'un au-dessus de toi.*", ephemeral=True)
    await membre.ban(reason=raison)
    await interaction.response.send_message(f"🔨 **{membre}** banni.\n*Raison: {raison}*\n\n*Un de moins. Pour la science.*")

@bot.tree.command(name="kick", description="Expulser un utilisateur")
@app_commands.describe(membre="L'utilisateur", raison="Raison")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
    if membre.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("*Hiérarchie. Regarde-la.*", ephemeral=True)
    await membre.kick(reason=raison)
    await interaction.response.send_message(f"👢 **{membre}** expulsé.\n*Raison: {raison}*")

@bot.tree.command(name="mute", description="Mute un utilisateur")
@app_commands.describe(membre="L'utilisateur", duree="Durée en minutes", raison="Raison")
@app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, membre: discord.Member, duree: int = 10, raison: str = "Aucune raison"):
    await membre.timeout(datetime.now(timezone.utc) + timedelta(minutes=duree), reason=raison)
    await interaction.response.send_message(f"🔇 **{membre}** muté pour **{duree}** min.\n*Le silence... enfin.*")

@bot.tree.command(name="unmute", description="Unmute un utilisateur")
@app_commands.describe(membre="L'utilisateur")
@app_commands.default_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, membre: discord.Member):
    await membre.timeout(None)
    await interaction.response.send_message(f"🔊 **{membre}** peut parler.\n*J'espère que ça en valait la peine.*")

@bot.tree.command(name="warn", description="Avertir un utilisateur")
@app_commands.describe(membre="L'utilisateur", raison="Raison")
@app_commands.default_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
    await interaction.response.send_message(f"⚠️ **{membre}** averti.\n*Raison: {raison}*")
    try: await membre.send(f"⚠️ Avertissement sur **{interaction.guild.name}**\n*Raison: {raison}*")
    except: pass

@bot.tree.command(name="clear", description="Supprimer des messages")
@app_commands.describe(nombre="Nombre (1-100)")
@app_commands.default_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, nombre: int):
    if nombre < 1 or nombre > 100:
        return await interaction.response.send_message("*Entre 1 et 100.*", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=nombre)
    await interaction.followup.send(f"🗑️ **{len(deleted)}** messages supprimés.", ephemeral=True)

# Run
token = os.environ.get('DISCORD_BOT_TOKEN')
if token:
    bot.run(token)
else:
    logger.error("DISCORD_BOT_TOKEN manquant!")
