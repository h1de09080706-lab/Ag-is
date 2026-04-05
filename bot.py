Clique "Add file" → "Create new file"

Nom : bot.py

Copie-colle TOUT ce code :

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

@bot.event
async def on_ready():
    logger.info(f'{bot.user} est connecté!')
    logger.info(f'Serveurs: {len(bot.guilds)}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="les humains échouer | /aide"))

@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel:
        await channel.send(random.choice(SARCASTIC_WELCOME).format(user=member.mention))

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

@bot.tree.command(name="aide", description="Affiche la liste des commandes")
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(title="📋 Commandes d'Aegis", description="*Oh, tu as besoin d'aide? Quelle surprise...*", color=discord.Color.orange())
    embed.add_field(name="🤖 IA", value="`/parler` - Me parler\n`@Aegis` - Me mentionner", inline=False)
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
