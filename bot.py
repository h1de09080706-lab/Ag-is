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
import io
import re

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
    IMAGE = "🖼️"
    AI = "🤖"
    
    NEON_LINE = "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"

NEON = NeonTheme()

# Font styles for channel renaming
FONT_STYLES = {
    "normal": {},
    "fancy": {"a": "α", "b": "ɓ", "c": "ƈ", "d": "ɗ", "e": "ɛ", "f": "ƒ", "g": "ɠ", "h": "ɦ", "i": "ι", "j": "ʝ", "k": "ƙ", "l": "ʅ", "m": "ɱ", "n": "ɳ", "o": "σ", "p": "ρ", "q": "ϙ", "r": "ɾ", "s": "ʂ", "t": "ƚ", "u": "υ", "v": "ʋ", "w": "ɯ", "x": "x", "y": "ყ", "z": "ȥ"},
    "bold": {"a": "𝗮", "b": "𝗯", "c": "𝗰", "d": "𝗱", "e": "𝗲", "f": "𝗳", "g": "𝗴", "h": "𝗵", "i": "𝗶", "j": "𝗷", "k": "𝗸", "l": "𝗹", "m": "𝗺", "n": "𝗻", "o": "𝗼", "p": "𝗽", "q": "𝗾", "r": "𝗿", "s": "𝘀", "t": "𝘁", "u": "𝘂", "v": "𝘃", "w": "𝘄", "x": "𝘅", "y": "𝘆", "z": "𝘇"},
    "aesthetic": {"a": "ａ", "b": "ｂ", "c": "ｃ", "d": "ｄ", "e": "ｅ", "f": "ｆ", "g": "ｇ", "h": "ｈ", "i": "ｉ", "j": "ｊ", "k": "ｋ", "l": "ｌ", "m": "ｍ", "n": "ｎ", "o": "ｏ", "p": "ｐ", "q": "ｑ", "r": "ｒ", "s": "ｓ", "t": "ｔ", "u": "ｕ", "v": "ｖ", "w": "ｗ", "x": "ｘ", "y": "ｙ", "z": "ｚ"},
}

STYLE_PRESETS = {
    "neon": {"prefix": "⚡", "separator": "┃"},
    "cyber": {"prefix": "◈", "separator": "▸"},
    "minimal": {"prefix": "•", "separator": "│"},
    "gaming": {"prefix": "🎮", "separator": "»"},
    "dark": {"prefix": "◆", "separator": "═"},
}

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
        self.role_menus = {}
        self.applications = {}
        self.voice_tts_channels = {}
        self.load_data()
        
    def load_data(self):
        data_files = {
            'backups': self.backups,
            'ticket_configs': self.ticket_configs,
            'auto_roles': self.auto_roles,
            'logs_channels': self.logs_channels,
            'welcome_channels': self.welcome_channels,
            'temp_voice_channels': self.temp_voice_channels,
            'raid_protection': self.raid_protection,
            'role_menus': self.role_menus,
            'applications': self.applications,
            'voice_tts_channels': self.voice_tts_channels
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
        self.add_view(GiveawayButton())
        self.add_view(RulesAcceptButton())
        self.add_view(ApplicationButton())
        
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

def apply_font_style(text: str, style: str) -> str:
    if style not in FONT_STYLES or style == "normal":
        return text
    font_map = FONT_STYLES[style]
    result = ""
    for char in text.lower():
        result += font_map.get(char, char)
    return result

async def log_action(guild: discord.Guild, action: str, description: str, color: int = None):
    guild_id = str(guild.id)
    if guild_id in bot.logs_channels:
        channel = guild.get_channel(bot.logs_channels[guild_id])
        if channel:
            embed = discord.Embed(
                title=f"{NEON.SHIELD} {action}",
                description=description,
                color=color or NEON.BLUE,
                timestamp=datetime.now(timezone.utc)
            )
            try:
                await channel.send(embed=embed)
            except:
                pass

# ==================== AI INTEGRATION ====================
async def generate_ai_image(prompt: str) -> bytes:
    """Generate image using OpenAI GPT Image 1"""
    try:
        from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            raise Exception("EMERGENT_LLM_KEY non configurée")
        
        image_gen = OpenAIImageGeneration(api_key=api_key)
        images = await image_gen.generate_images(
            prompt=prompt,
            model="gpt-image-1",
            number_of_images=1
        )
        if images and len(images) > 0:
            return images[0]
        raise Exception("Aucune image générée")
    except Exception as e:
        logger.error(f"Erreur génération image: {e}")
        raise

async def generate_ai_text(prompt: str, system_message: str = "Tu es un assistant Discord utile et créatif.") -> str:
    """Generate text using OpenAI GPT"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            raise Exception("EMERGENT_LLM_KEY non configurée")
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"aegis-{datetime.now().timestamp()}",
            system_message=system_message
        ).with_model("openai", "gpt-4o")
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        return response
    except Exception as e:
        logger.error(f"Erreur génération texte: {e}")
        raise

async def generate_tts_audio(text: str, voice: str = "nova") -> bytes:
    """Generate TTS audio using OpenAI"""
    try:
        from emergentintegrations.llm.openai import OpenAITextToSpeech
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            raise Exception("EMERGENT_LLM_KEY non configurée")
        
        tts = OpenAITextToSpeech(api_key=api_key)
        audio_bytes = await tts.generate_speech(
            text=text,
            model="tts-1",
            voice=voice
        )
        return audio_bytes
    except Exception as e:
        logger.error(f"Erreur génération TTS: {e}")
        raise

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
    
    # Anti-raid check
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
            await log_action(member.guild, "Anti-Raid", f"{member} a été {action} (raid détecté)", 0xFF0000)
        except Exception as e:
            logger.error(f"Anti-raid error: {e}")
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
    
    # Temp voice channel creation
    if guild_id in bot.temp_voice_channels:
        trigger_channel_id = bot.temp_voice_channels[guild_id]
        if after.channel and after.channel.id == trigger_channel_id:
            category = after.channel.category
            try:
                new_channel = await member.guild.create_voice_channel(
                    f"🔊 {member.display_name}",
                    category=category,
                    user_limit=10
                )
                await member.move_to(new_channel)
            except Exception as e:
                logger.error(f"Temp voice error: {e}")
    
    # Cleanup empty temp channels
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
    
    # Text command responses
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
        
        existing = discord.utils.get(interaction.guild.text_channels, name=f"ticket-{interaction.user.name.lower().replace(' ', '-')[:20]}")
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
            
            await log_action(interaction.guild, "Ticket Ouvert", f"{interaction.user.mention} a ouvert un ticket", NEON.PINK)
            
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
        
        # Save transcript
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

class ApplicationButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✨ Postuler ✨", style=discord.ButtonStyle.green, custom_id="apply_btn", emoji="📝")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ApplicationModal()
        await interaction.response.send_modal(modal)

class ApplicationModal(discord.ui.Modal, title="📝 Candidature"):
    pseudo = discord.ui.TextInput(label="Ton pseudo", placeholder="Comment t'appelles-tu?", max_length=50)
    age = discord.ui.TextInput(label="Ton âge", placeholder="Ton âge", max_length=3)
    motivation = discord.ui.TextInput(label="Pourquoi veux-tu rejoindre?", style=discord.TextStyle.paragraph, placeholder="Explique ta motivation...", max_length=500)
    experience = discord.ui.TextInput(label="Ton expérience", style=discord.TextStyle.paragraph, placeholder="Parle de ton expérience...", max_length=500, required=False)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        embed = discord.Embed(
            title=f"{NEON.SPARKLE} ═══ Nouvelle Candidature ═══ {NEON.SPARKLE}",
            color=NEON.PINK,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Pseudo", value=self.pseudo.value, inline=True)
        embed.add_field(name="Âge", value=self.age.value, inline=True)
        embed.add_field(name="Discord", value=interaction.user.mention, inline=True)
        embed.add_field(name="Motivation", value=self.motivation.value[:1000], inline=False)
        if self.experience.value:
            embed.add_field(name="Expérience", value=self.experience.value[:1000], inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        # Find applications channel
        app_channel = discord.utils.get(interaction.guild.text_channels, name="candidatures") or \
                      discord.utils.get(interaction.guild.text_channels, name="applications")
        
        if app_channel:
            await app_channel.send(embed=embed)
            await interaction.response.send_message(f"{NEON.CHECK} Candidature envoyée!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{NEON.WARN} Aucun salon de candidatures trouvé!", ephemeral=True)

# ==================== ROLE SELECT MENU ====================
class RoleSelectMenu(discord.ui.Select):
    def __init__(self, roles: List[discord.Role]):
        options = [
            discord.SelectOption(
                label=role.name,
                value=str(role.id),
                emoji="🎭"
            ) for role in roles[:25]
        ]
        super().__init__(
            placeholder="Choisis tes rôles...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="role_select_menu"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_role_ids = [int(v) for v in self.values]
        added = []
        removed = []
        
        for option in self.options:
            role = interaction.guild.get_role(int(option.value))
            if role:
                if int(option.value) in selected_role_ids:
                    if role not in interaction.user.roles:
                        await interaction.user.add_roles(role)
                        added.append(role.name)
                else:
                    if role in interaction.user.roles:
                        await interaction.user.remove_roles(role)
                        removed.append(role.name)
        
        response = []
        if added:
            response.append(f"✅ Ajoutés: {', '.join(added)}")
        if removed:
            response.append(f"❌ Retirés: {', '.join(removed)}")
        
        await interaction.response.send_message("\n".join(response) if response else "Aucun changement", ephemeral=True)

class RoleSelectView(discord.ui.View):
    def __init__(self, roles: List[discord.Role]):
        super().__init__(timeout=None)
        self.add_item(RoleSelectMenu(roles))

# ==================== SLASH COMMANDS - AIDE ====================
@bot.tree.command(name="aide", description="Liste des commandes")
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"{NEON.SPARKLE} ═══ Commandes d'Aegis ═══ {NEON.SPARKLE}",
        color=NEON.PINK
    )
    embed.add_field(name=f"{NEON.DIAMOND} Membres", value="```/rename /resetpseudo /ban /unban /kick /mute /unmute```", inline=False)
    embed.add_field(name=f"{NEON.CHANNEL} Salons", value="```/creersalon /supprimersalon /creervoice /lock /unlock /slowmode /purge /purgeall /renommer /deplacer /sync```", inline=False)
    embed.add_field(name=f"{NEON.ROLE} Rôles", value="```/creerole /supprole /addrole /removerole /roleall /unroleall /autorole /rolemenu```", inline=False)
    embed.add_field(name=f"{NEON.GEAR} Systèmes", value="```/panel /reglement /verification /candidature /giveaway```", inline=False)
    embed.add_field(name=f"{NEON.ROCKET} Serveur", value="```/setup /logs /welcome /annonce /renommerserveur /backup /restore```", inline=False)
    embed.add_field(name=f"{NEON.AI} IA & Médias", value="```/image /annonceia /embed /citation /sondage /say /tts```", inline=False)
    embed.add_field(name=f"{NEON.VOICE} Vocal", value="```/tempvoice /parler```", inline=False)
    embed.add_field(name=f"{NEON.SHIELD} Protection", value="```/antiraid /changerpolice /style```", inline=False)
    embed.set_footer(text=f"⚡ Aegis Bot • Néon Mode ⚡")
    await interaction.response.send_message(embed=embed)

# ==================== MEMBER MANAGEMENT ====================
@bot.tree.command(name="rename", description="Renommer un membre")
@app_commands.describe(membre="Le membre", nouveau_pseudo="Nouveau pseudo")
@app_commands.default_permissions(manage_nicknames=True)
async def rename(interaction: discord.Interaction, membre: discord.Member, nouveau_pseudo: str):
    old_name = membre.display_name
    await membre.edit(nick=nouveau_pseudo)
    embed = create_simple_neon_embed("Membre Renommé", f"{old_name} → **{nouveau_pseudo}**", NEON.PINK)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Renommage", f"{interaction.user} a renommé {membre} en {nouveau_pseudo}")

@bot.tree.command(name="resetpseudo", description="Réinitialiser le pseudo d'un membre")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(manage_nicknames=True)
async def resetpseudo(interaction: discord.Interaction, membre: discord.Member):
    old_name = membre.display_name
    await membre.edit(nick=None)
    embed = create_simple_neon_embed("Pseudo Réinitialisé", f"{old_name} → {membre.name}", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ban", description="Bannir un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.ban(reason=raison)
    embed = discord.Embed(title=f"{NEON.BAN} Membre Banni", description=f"**{membre}** - {raison}", color=0xFF0000)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Ban", f"{interaction.user} a banni {membre}\nRaison: {raison}", 0xFF0000)

@bot.tree.command(name="unban", description="Débannir un utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur")
@app_commands.default_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        embed = create_simple_neon_embed("Membre Débanni", f"**{user}** peut revenir", NEON.PINK)
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, "Unban", f"{interaction.user} a débanni {user}")
    except:
        await interaction.response.send_message(f"{NEON.WARN} Utilisateur non trouvé", ephemeral=True)

@bot.tree.command(name="kick", description="Expulser un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.kick(reason=raison)
    embed = create_simple_neon_embed("Membre Expulsé", f"{membre} - {raison}", NEON.PURPLE)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Kick", f"{interaction.user} a expulsé {membre}\nRaison: {raison}", NEON.PURPLE)

@bot.tree.command(name="mute", description="Mute un membre")
@app_commands.describe(membre="Le membre", duree="Durée en minutes")
@app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, membre: discord.Member, duree: int = 10):
    await membre.timeout(datetime.now(timezone.utc) + timedelta(minutes=duree))
    embed = create_simple_neon_embed("Membre Muté", f"{membre.mention} pour {duree} min", NEON.BLUE)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Mute", f"{interaction.user} a mute {membre} pour {duree} min")

@bot.tree.command(name="unmute", description="Unmute un membre")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, membre: discord.Member):
    await membre.timeout(None)
    embed = create_simple_neon_embed("Membre Unmute", f"{membre.mention} peut parler", NEON.PINK)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Unmute", f"{interaction.user} a unmute {membre}")

# ==================== CHANNEL MANAGEMENT ====================
@bot.tree.command(name="creersalon", description="Créer un salon textuel")
@app_commands.describe(nom="Nom du salon", categorie="Catégorie (optionnel)")
@app_commands.default_permissions(manage_channels=True)
async def creersalon(interaction: discord.Interaction, nom: str, categorie: discord.CategoryChannel = None):
    channel = await interaction.guild.create_text_channel(nom, category=categorie)
    embed = create_simple_neon_embed("Salon Créé", f"{channel.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Salon Créé", f"{interaction.user} a créé {channel.mention}")

@bot.tree.command(name="creervoice", description="Créer un salon vocal")
@app_commands.describe(nom="Nom du salon", categorie="Catégorie (optionnel)", limite="Limite d'utilisateurs")
@app_commands.default_permissions(manage_channels=True)
async def creervoice(interaction: discord.Interaction, nom: str, categorie: discord.CategoryChannel = None, limite: int = 0):
    channel = await interaction.guild.create_voice_channel(nom, category=categorie, user_limit=limite if limite > 0 else None)
    embed = create_simple_neon_embed("Salon Vocal Créé", f"🔊 {channel.name}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="creercategorie", description="Créer une catégorie")
@app_commands.describe(nom="Nom de la catégorie")
@app_commands.default_permissions(manage_channels=True)
async def creercategorie(interaction: discord.Interaction, nom: str):
    category = await interaction.guild.create_category(nom)
    embed = create_simple_neon_embed("Catégorie Créée", f"📁 {category.name}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="supprimersalon", description="Supprimer un salon")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(manage_channels=True)
async def supprimersalon(interaction: discord.Interaction, salon: discord.TextChannel):
    name = salon.name
    await salon.delete()
    embed = create_simple_neon_embed("Salon Supprimé", f"`{name}`", NEON.BLUE)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Salon Supprimé", f"{interaction.user} a supprimé #{name}")

@bot.tree.command(name="supprimervoice", description="Supprimer un salon vocal")
@app_commands.describe(salon="Le salon vocal")
@app_commands.default_permissions(manage_channels=True)
async def supprimervoice(interaction: discord.Interaction, salon: discord.VoiceChannel):
    name = salon.name
    await salon.delete()
    embed = create_simple_neon_embed("Salon Vocal Supprimé", f"`{name}`", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="renommer", description="Renommer un salon")
@app_commands.describe(salon="Le salon", nouveau_nom="Nouveau nom")
@app_commands.default_permissions(manage_channels=True)
async def renommer(interaction: discord.Interaction, salon: discord.TextChannel, nouveau_nom: str):
    old_name = salon.name
    await salon.edit(name=nouveau_nom)
    embed = create_simple_neon_embed("Salon Renommé", f"`{old_name}` → `{nouveau_nom}`", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="deplacer", description="Déplacer un salon dans une catégorie")
@app_commands.describe(salon="Le salon", categorie="La catégorie")
@app_commands.default_permissions(manage_channels=True)
async def deplacer(interaction: discord.Interaction, salon: discord.TextChannel, categorie: discord.CategoryChannel):
    await salon.edit(category=categorie)
    embed = create_simple_neon_embed("Salon Déplacé", f"{salon.mention} → {categorie.name}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="lock", description="Verrouiller un salon")
@app_commands.default_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    embed = create_simple_neon_embed("Salon Verrouillé", "🔒", NEON.BLUE)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Lock", f"{interaction.user} a verrouillé {interaction.channel.mention}")

@bot.tree.command(name="unlock", description="Déverrouiller un salon")
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    embed = create_simple_neon_embed("Salon Déverrouillé", "🔓", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="slowmode", description="Configurer le mode lent")
@app_commands.describe(secondes="Délai en secondes (0 pour désactiver)")
@app_commands.default_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, secondes: int):
    await interaction.channel.edit(slowmode_delay=secondes)
    if secondes > 0:
        embed = create_simple_neon_embed("Mode Lent Activé", f"⏱️ {secondes} secondes", NEON.BLUE)
    else:
        embed = create_simple_neon_embed("Mode Lent Désactivé", "🚀", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="sync", description="Synchroniser les permissions avec la catégorie")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(manage_channels=True)
async def sync_perms(interaction: discord.Interaction, salon: discord.TextChannel):
    if salon.category:
        await salon.edit(sync_permissions=True)
        embed = create_simple_neon_embed("Permissions Synchronisées", f"{salon.mention} → {salon.category.name}", NEON.PINK)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"{NEON.WARN} Ce salon n'est pas dans une catégorie", ephemeral=True)

@bot.tree.command(name="purge", description="Supprimer des messages")
@app_commands.describe(nombre="Nombre de messages")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, nombre: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=nombre)
    await interaction.followup.send(f"{NEON.CHECK} {len(deleted)} messages supprimés")
    await log_action(interaction.guild, "Purge", f"{interaction.user} a supprimé {len(deleted)} messages dans {interaction.channel.mention}")

@bot.tree.command(name="purgeall", description="Purger tous les messages d'un salon")
@app_commands.describe(salon="Le salon à purger")
@app_commands.default_permissions(administrator=True)
async def purgeall(interaction: discord.Interaction, salon: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)
    count = 0
    while True:
        deleted = await salon.purge(limit=100)
        count += len(deleted)
        if len(deleted) < 100:
            break
        await asyncio.sleep(1)
    await interaction.followup.send(f"{NEON.CHECK} {count} messages supprimés de {salon.mention}")

# ==================== ROLE MANAGEMENT ====================
@bot.tree.command(name="creerole", description="Créer un rôle")
@app_commands.describe(nom="Nom", couleur="Couleur hex")
@app_commands.default_permissions(manage_roles=True)
async def creerole(interaction: discord.Interaction, nom: str, couleur: str = "#ff1493"):
    color = discord.Color(int(couleur.replace("#", ""), 16))
    role = await interaction.guild.create_role(name=nom, color=color)
    embed = create_simple_neon_embed("Rôle Créé", f"{role.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Rôle Créé", f"{interaction.user} a créé {role.mention}")

@bot.tree.command(name="supprole", description="Supprimer un rôle")
@app_commands.describe(role="Le rôle à supprimer")
@app_commands.default_permissions(manage_roles=True)
async def supprole(interaction: discord.Interaction, role: discord.Role):
    name = role.name
    await role.delete()
    embed = create_simple_neon_embed("Rôle Supprimé", f"`{name}`", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="renomrole", description="Renommer un rôle")
@app_commands.describe(role="Le rôle", nouveau_nom="Nouveau nom")
@app_commands.default_permissions(manage_roles=True)
async def renomrole(interaction: discord.Interaction, role: discord.Role, nouveau_nom: str):
    old_name = role.name
    await role.edit(name=nouveau_nom)
    embed = create_simple_neon_embed("Rôle Renommé", f"`{old_name}` → `{nouveau_nom}`", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="couleurrole", description="Changer la couleur d'un rôle")
@app_commands.describe(role="Le rôle", couleur="Couleur hex")
@app_commands.default_permissions(manage_roles=True)
async def couleurrole(interaction: discord.Interaction, role: discord.Role, couleur: str):
    color = discord.Color(int(couleur.replace("#", ""), 16))
    await role.edit(color=color)
    embed = create_simple_neon_embed("Couleur Modifiée", f"{role.mention} → {couleur}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addrole", description="Ajouter un rôle à un membre")
@app_commands.describe(membre="Le membre", role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.add_roles(role)
    embed = create_simple_neon_embed("Rôle Ajouté", f"{role.mention} → {membre.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Rôle Ajouté", f"{interaction.user} a ajouté {role.mention} à {membre.mention}")

@bot.tree.command(name="removerole", description="Retirer un rôle à un membre")
@app_commands.describe(membre="Le membre", role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.remove_roles(role)
    embed = create_simple_neon_embed("Rôle Retiré", f"{role.mention} de {membre.mention}", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="roleall", description="Ajouter un rôle à tous les membres")
@app_commands.describe(role="Le rôle")
@app_commands.default_permissions(administrator=True)
async def roleall(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer()
    count = 0
    for member in interaction.guild.members:
        if not member.bot and role not in member.roles:
            try:
                await member.add_roles(role)
                count += 1
                await asyncio.sleep(0.5)
            except:
                pass
    embed = create_simple_neon_embed("Rôle Ajouté à Tous", f"{role.mention} → {count} membres", NEON.PINK)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="unroleall", description="Retirer un rôle à tous les membres")
@app_commands.describe(role="Le rôle")
@app_commands.default_permissions(administrator=True)
async def unroleall(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer()
    count = 0
    for member in interaction.guild.members:
        if role in member.roles:
            try:
                await member.remove_roles(role)
                count += 1
                await asyncio.sleep(0.5)
            except:
                pass
    embed = create_simple_neon_embed("Rôle Retiré à Tous", f"{role.mention} de {count} membres", NEON.BLUE)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="autorole", description="Configurer l'auto-rôle")
@app_commands.describe(role="Le rôle")
@app_commands.default_permissions(administrator=True)
async def autorole(interaction: discord.Interaction, role: discord.Role):
    bot.auto_roles[str(interaction.guild.id)] = role.id
    bot.save_data('auto_roles', bot.auto_roles)
    embed = create_simple_neon_embed("Auto-Rôle", f"Nouveaux membres: {role.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rolemenu", description="Créer un menu de sélection de rôles")
@app_commands.describe(titre="Titre du menu", roles="Rôles séparés par des virgules (ex: @Role1, @Role2)")
@app_commands.default_permissions(administrator=True)
async def rolemenu(interaction: discord.Interaction, titre: str, roles: str):
    # Parse role mentions
    role_ids = re.findall(r'<@&(\d+)>', roles)
    role_objects = [interaction.guild.get_role(int(rid)) for rid in role_ids if interaction.guild.get_role(int(rid))]
    
    if not role_objects:
        return await interaction.response.send_message(f"{NEON.WARN} Aucun rôle valide trouvé. Utilise des mentions de rôles.", ephemeral=True)
    
    embed = discord.Embed(
        title=f"{NEON.ROLE} ═══ {titre} ═══ {NEON.ROLE}",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} Choisis tes rôles dans le menu ci-dessous!\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    roles_list = "\n".join([f"• {role.mention}" for role in role_objects])
    embed.add_field(name="Rôles disponibles", value=roles_list, inline=False)
    
    await interaction.channel.send(embed=embed, view=RoleSelectView(role_objects))
    await interaction.response.send_message(f"{NEON.CHECK} Menu de rôles créé!", ephemeral=True)

# ==================== SYSTEMS ====================
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
@app_commands.describe(avec_bouton="Ajouter bouton d'acceptation", role="Rôle à donner")
@app_commands.default_permissions(administrator=True)
async def reglement(interaction: discord.Interaction, avec_bouton: bool = True, role: discord.Role = None):
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
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} Clique pour te vérifier et obtenir {role.mention}!\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.BLUE
    )
    await interaction.channel.send(embed=embed, view=VerifyButton())
    await interaction.response.send_message(f"{NEON.CHECK} Vérification configurée!", ephemeral=True)

@bot.tree.command(name="candidature", description="Créer un système de candidature")
@app_commands.describe(titre="Titre")
@app_commands.default_permissions(administrator=True)
async def candidature(interaction: discord.Interaction, titre: str = "Recrutement"):
    embed = discord.Embed(
        title=f"📝 ═══ {titre} ═══ 📝",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} Clique pour postuler!\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    await interaction.channel.send(embed=embed, view=ApplicationButton())
    await interaction.response.send_message(f"{NEON.CHECK} Système de candidature créé!", ephemeral=True)

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

# ==================== SERVER MANAGEMENT ====================
@bot.tree.command(name="logs", description="Configurer les logs")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(administrator=True)
async def logs(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.logs_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('logs_channels', bot.logs_channels)
    embed = create_simple_neon_embed("Logs", f"Configuré: {salon.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="welcome", description="Configurer les messages de bienvenue/départ")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(administrator=True)
async def welcome(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.welcome_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('welcome_channels', bot.welcome_channels)
    embed = create_simple_neon_embed("Bienvenue/Départ", f"Configuré: {salon.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="renommerserveur", description="Renommer le serveur")
@app_commands.describe(nom="Nouveau nom")
@app_commands.default_permissions(administrator=True)
async def renommerserveur(interaction: discord.Interaction, nom: str):
    old_name = interaction.guild.name
    await interaction.guild.edit(name=nom)
    embed = create_simple_neon_embed("Serveur Renommé", f"`{old_name}` → `{nom}`", NEON.PINK)
    await interaction.response.send_message(embed=embed)

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
        f"{NEON.TICKET} Tickets": [],
        f"📝 Staff": ["candidatures"]
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

# ==================== BACKUP & RESTORE ====================
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
        "roles": [{"name": r.name, "color": r.color.value, "permissions": r.permissions.value} for r in guild.roles if r.name != "@everyone" and not r.managed],
        "categories": [{"name": c.name, "position": c.position} for c in guild.categories],
        "text_channels": [{"name": c.name, "category": c.category.name if c.category else None, "topic": c.topic} for c in guild.text_channels],
        "voice_channels": [{"name": c.name, "category": c.category.name if c.category else None, "user_limit": c.user_limit} for c in guild.voice_channels]
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
                await guild.create_role(
                    name=role_data["name"],
                    color=discord.Color(role_data.get("color", 0)),
                    permissions=discord.Permissions(role_data.get("permissions", 0))
                )
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
                await guild.create_text_channel(name=ch_data["name"], category=category, topic=ch_data.get("topic"))
                restored["channels"] += 1
                await asyncio.sleep(0.3)
            except:
                pass
    
    for ch_data in backup_data.get("voice_channels", []):
        if not discord.utils.get(guild.voice_channels, name=ch_data["name"]):
            try:
                category = cat_map.get(ch_data.get("category")) or discord.utils.get(guild.categories, name=ch_data.get("category"))
                await guild.create_voice_channel(name=ch_data["name"], category=category, user_limit=ch_data.get("user_limit", 0))
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

# ==================== AI & MEDIA COMMANDS ====================
@bot.tree.command(name="image", description="Générer une image avec l'IA")
@app_commands.describe(prompt="Description de l'image")
async def image(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        embed_progress = discord.Embed(
            title=f"{NEON.IMAGE} Génération en cours...",
            description=f"```{prompt[:200]}```",
            color=NEON.BLUE
        )
        await interaction.followup.send(embed=embed_progress)
        
        image_bytes = await generate_ai_image(prompt)
        
        file = discord.File(fp=io.BytesIO(image_bytes), filename="generated.png")
        embed = discord.Embed(
            title=f"{NEON.IMAGE} ═══ Image Générée ═══ {NEON.IMAGE}",
            description=f"```{prompt[:200]}```",
            color=NEON.PINK
        )
        embed.set_image(url="attachment://generated.png")
        embed.set_footer(text=f"Demandé par {interaction.user}")
        
        await interaction.edit_original_response(embed=embed, attachments=[file])
    except Exception as e:
        await interaction.edit_original_response(embed=discord.Embed(
            title=f"{NEON.WARN} Erreur",
            description=f"```{str(e)[:200]}```",
            color=0xFF0000
        ))

@bot.tree.command(name="annonceia", description="Créer une annonce avec l'IA")
@app_commands.describe(sujet="Sujet de l'annonce", style="Style (formel/décontracté/hype)")
async def annonceia(interaction: discord.Interaction, sujet: str, style: str = "hype"):
    await interaction.response.defer()
    try:
        prompt = f"Crée une annonce Discord en français pour: {sujet}. Style: {style}. Max 500 caractères. Utilise des emojis. Ne mets pas de titre."
        
        text = await generate_ai_text(prompt, "Tu es un community manager Discord expert en annonces engageantes.")
        
        embed = discord.Embed(
            title=f"📢 ═══ ANNONCE ═══ 📢",
            description=f"```\n{NEON.NEON_LINE}\n```\n{text}\n```\n{NEON.NEON_LINE}\n```",
            color=NEON.PINK
        )
        embed.set_footer(text=f"Généré par IA • Demandé par {interaction.user}")
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"{NEON.WARN} Erreur: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="embed", description="Créer un embed personnalisé")
@app_commands.describe(titre="Titre", description="Description", couleur="Couleur hex", image="URL de l'image")
async def embed_cmd(interaction: discord.Interaction, titre: str, description: str, couleur: str = "#ff1493", image: str = None):
    try:
        color = discord.Color(int(couleur.replace("#", ""), 16))
    except:
        color = NEON.PINK
    
    embed = discord.Embed(
        title=titre,
        description=description,
        color=color
    )
    if image:
        embed.set_image(url=image)
    embed.set_footer(text=f"Par {interaction.user}")
    
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"{NEON.CHECK} Embed créé!", ephemeral=True)

@bot.tree.command(name="citation", description="Créer une citation stylée")
@app_commands.describe(texte="Le texte de la citation", auteur="L'auteur")
async def citation(interaction: discord.Interaction, texte: str, auteur: str = None):
    embed = discord.Embed(
        description=f"```\n{NEON.NEON_LINE}\n```\n*\"{texte}\"*\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PURPLE
    )
    if auteur:
        embed.set_footer(text=f"— {auteur}")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"{NEON.CHECK} Citation créée!", ephemeral=True)

@bot.tree.command(name="sondage", description="Créer un sondage")
@app_commands.describe(question="La question", options="Options séparées par |")
async def sondage(interaction: discord.Interaction, question: str, options: str):
    opts = [o.strip() for o in options.split("|")][:10]
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    description = "\n".join([f"{emojis[i]} {opt}" for i, opt in enumerate(opts)])
    
    embed = discord.Embed(
        title=f"📊 {question}",
        description=f"```\n{NEON.NEON_LINE}\n```\n{description}\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    embed.set_footer(text=f"Sondage par {interaction.user}")
    
    msg = await interaction.channel.send(embed=embed)
    for i in range(len(opts)):
        await msg.add_reaction(emojis[i])
    
    await interaction.response.send_message(f"{NEON.CHECK} Sondage créé!", ephemeral=True)

@bot.tree.command(name="say", description="Faire parler le bot")
@app_commands.describe(message="Le message", salon="Le salon (optionnel)")
@app_commands.default_permissions(manage_messages=True)
async def say(interaction: discord.Interaction, message: str, salon: discord.TextChannel = None):
    target = salon or interaction.channel
    await target.send(message)
    await interaction.response.send_message(f"{NEON.CHECK} Message envoyé!", ephemeral=True)

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

# ==================== VOICE & TTS ====================
@bot.tree.command(name="tempvoice", description="Configurer les salons vocaux temporaires")
@app_commands.describe(salon="Le salon vocal déclencheur")
@app_commands.default_permissions(administrator=True)
async def tempvoice(interaction: discord.Interaction, salon: discord.VoiceChannel):
    bot.temp_voice_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('temp_voice_channels', bot.temp_voice_channels)
    embed = create_simple_neon_embed("Salons Vocaux Temporaires", f"Configuré: {salon.name}\nRejoins ce salon pour créer ton propre vocal!", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tts", description="Générer un message vocal TTS")
@app_commands.describe(texte="Le texte à dire", voix="La voix (nova/alloy/echo/shimmer)")
async def tts(interaction: discord.Interaction, texte: str, voix: str = "nova"):
    await interaction.response.defer()
    try:
        if len(texte) > 500:
            return await interaction.followup.send(f"{NEON.WARN} Texte trop long (max 500 caractères)", ephemeral=True)
        
        audio_bytes = await generate_tts_audio(texte, voix)
        
        file = discord.File(fp=io.BytesIO(audio_bytes), filename="tts.mp3")
        embed = discord.Embed(
            title=f"{NEON.VOICE} Message Vocal",
            description=f"```{texte[:200]}```",
            color=NEON.PINK
        )
        embed.add_field(name="Voix", value=voix, inline=True)
        
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        await interaction.followup.send(f"{NEON.WARN} Erreur: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="parler", description="Faire parler le bot dans un vocal (TTS)")
@app_commands.describe(texte="Le texte à dire", voix="La voix")
async def parler(interaction: discord.Interaction, texte: str, voix: str = "nova"):
    if not interaction.user.voice:
        return await interaction.response.send_message(f"{NEON.WARN} Tu dois être dans un salon vocal!", ephemeral=True)
    
    await interaction.response.defer()
    try:
        audio_bytes = await generate_tts_audio(texte, voix)
        
        # Save temp file
        temp_path = DATA_DIR / f"tts_{interaction.id}.mp3"
        with open(temp_path, 'wb') as f:
            f.write(audio_bytes)
        
        # Connect and play
        vc = await interaction.user.voice.channel.connect()
        vc.play(discord.FFmpegPCMAudio(str(temp_path)), after=lambda e: asyncio.run_coroutine_threadsafe(vc.disconnect(), bot.loop))
        
        embed = create_simple_neon_embed("Lecture en cours", f"```{texte[:100]}```", NEON.PINK)
        await interaction.followup.send(embed=embed)
        
        # Cleanup after playback
        while vc.is_playing():
            await asyncio.sleep(1)
        
        try:
            temp_path.unlink()
        except:
            pass
            
    except Exception as e:
        await interaction.followup.send(f"{NEON.WARN} Erreur: {str(e)[:100]}", ephemeral=True)

# ==================== PROTECTION & STYLE ====================
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

@bot.tree.command(name="changerpolice", description="Changer la police des salons")
@app_commands.describe(style="Style (fancy/bold/aesthetic/normal)")
@app_commands.default_permissions(administrator=True)
async def changerpolice(interaction: discord.Interaction, style: str = "fancy"):
    if style not in FONT_STYLES:
        return await interaction.response.send_message(f"{NEON.WARN} Styles: fancy, bold, aesthetic, normal", ephemeral=True)
    
    await interaction.response.defer()
    count = 0
    
    for channel in interaction.guild.text_channels:
        try:
            # Extract base name without emojis
            base_name = re.sub(r'[^\w\s-]', '', channel.name).strip()
            if base_name:
                new_name = apply_font_style(base_name, style)
                await channel.edit(name=new_name)
                count += 1
                await asyncio.sleep(0.5)
        except:
            pass
    
    embed = create_simple_neon_embed("Police Modifiée", f"Style `{style}` appliqué à {count} salons", NEON.PINK)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="style", description="Appliquer un preset de style au serveur")
@app_commands.describe(preset="Preset (neon/cyber/minimal/gaming/dark)")
@app_commands.default_permissions(administrator=True)
async def style(interaction: discord.Interaction, preset: str = "neon"):
    if preset not in STYLE_PRESETS:
        return await interaction.response.send_message(f"{NEON.WARN} Presets: neon, cyber, minimal, gaming, dark", ephemeral=True)
    
    await interaction.response.defer()
    style_config = STYLE_PRESETS[preset]
    count = 0
    
    for category in interaction.guild.categories:
        try:
            base_name = re.sub(r'[^\w\s]', '', category.name).strip()
            new_name = f"{style_config['prefix']} {style_config['separator']} {base_name} {style_config['separator']} {style_config['prefix']}"
            await category.edit(name=new_name)
            count += 1
            await asyncio.sleep(0.5)
        except:
            pass
    
    embed = create_simple_neon_embed("Style Appliqué", f"Preset `{preset}` appliqué à {count} catégories", NEON.PINK)
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
