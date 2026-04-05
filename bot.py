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
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Aegis')

# Data storage path
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ==================== NEON THEME CONFIG ====================
class NeonTheme:
    PINK = 0xFF1493
    BLUE = 0x00FFFF
    PURPLE = 0x9D00FF
    PINK_SOFT = 0xFF69B4
    BLUE_DARK = 0x0099FF
    GREEN = 0x00FF00
    RED = 0xFF0000
    ORANGE = 0xFF6600
    
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
    SPAM = "🚫"
    
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
        self.role_menus = {}
        self.applications = {}
        self.voice_tts_channels = {}
        self.verification_roles = {}
        self.anti_spam_config = {}
        # Anti-spam tracking
        self.message_cache = defaultdict(list)  # user_id -> list of timestamps
        self.spam_warnings = defaultdict(int)  # user_id -> warning count
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
            'voice_tts_channels': self.voice_tts_channels,
            'verification_roles': self.verification_roles,
            'anti_spam_config': self.anti_spam_config
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
        self.add_view(VerifyButtonDynamic())
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

def create_neon_embed(title: str, description: str = None, color: int = None) -> discord.Embed:
    if color is None:
        color = NEON.PINK
    embed = discord.Embed(
        title=f"✨ {title} ✨",
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    return embed

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
            raise Exception("❌ EMERGENT_LLM_KEY non configurée dans Railway!\n\nVa dans Railway → Settings → Variables et ajoute:\nEMERGENT_LLM_KEY=sk-emergent-7532197D963D4C9A8A")
        
        image_gen = OpenAIImageGeneration(api_key=api_key)
        images = await image_gen.generate_images(
            prompt=prompt,
            model="gpt-image-1",
            number_of_images=1
        )
        if images and len(images) > 0:
            return images[0]
        raise Exception("Aucune image générée")
    except ImportError:
        raise Exception("❌ Module emergentintegrations non installé!\n\nAjoute dans requirements.txt:\nemergentintegrations")
    except Exception as e:
        logger.error(f"Erreur génération image: {e}")
        raise

async def generate_ai_text(prompt: str, system_message: str = "Tu es un assistant Discord utile et créatif.") -> str:
    """Generate text using OpenAI GPT"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            raise Exception("❌ EMERGENT_LLM_KEY non configurée!")
        
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
            raise Exception("❌ EMERGENT_LLM_KEY non configurée!")
        
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

# ==================== ANTI-SPAM SYSTEM ====================
async def check_spam(message: discord.Message) -> bool:
    """Check if message is spam and take action"""
    if message.author.bot or message.author.guild_permissions.administrator:
        return False
    
    guild_id = str(message.guild.id)
    user_id = message.author.id
    now = datetime.now(timezone.utc)
    
    # Get config
    config = bot.anti_spam_config.get(guild_id, {"enabled": True, "msg_limit": 5, "msg_time": 5, "mention_limit": 5, "action": "mute", "mute_duration": 5})
    
    if not config.get("enabled", True):
        return False
    
    # Check message spam (X messages in Y seconds)
    bot.message_cache[user_id].append(now)
    bot.message_cache[user_id] = [t for t in bot.message_cache[user_id] if (now - t).total_seconds() < config.get("msg_time", 5)]
    
    is_spam = False
    reason = ""
    
    # Message spam check
    if len(bot.message_cache[user_id]) > config.get("msg_limit", 5):
        is_spam = True
        reason = f"Spam de messages ({len(bot.message_cache[user_id])} messages en {config.get('msg_time', 5)}s)"
    
    # Mention spam check
    mention_count = len(message.mentions) + len(message.role_mentions)
    if message.mention_everyone:
        mention_count += message.guild.member_count
    
    if mention_count >= config.get("mention_limit", 5):
        is_spam = True
        reason = f"Spam de mentions ({mention_count} mentions)"
    
    if is_spam:
        action = config.get("action", "mute")
        try:
            # Delete the spam message
            await message.delete()
            
            # Take action
            if action == "kick":
                await message.author.kick(reason=f"{NEON.SPAM} Anti-Spam: {reason}")
            elif action == "ban":
                await message.author.ban(reason=f"{NEON.SPAM} Anti-Spam: {reason}")
            else:  # mute
                duration = config.get("mute_duration", 5)
                await message.author.timeout(datetime.now(timezone.utc) + timedelta(minutes=duration), reason=f"{NEON.SPAM} Anti-Spam: {reason}")
            
            # Send warning
            embed = discord.Embed(
                title=f"{NEON.SPAM} Anti-Spam",
                description=f"{message.author.mention} a été sanctionné!\n**Raison:** {reason}\n**Action:** {action}",
                color=NEON.RED
            )
            await message.channel.send(embed=embed, delete_after=10)
            
            # Log
            await log_action(message.guild, "Anti-Spam", f"{message.author} - {reason} - Action: {action}", NEON.RED)
            
            # Clear cache for user
            bot.message_cache[user_id] = []
            
            return True
        except Exception as e:
            logger.error(f"Anti-spam error: {e}")
    
    return False

# ==================== EVENTS ====================
@bot.event
async def on_ready():
    logger.info(f'⚡ {bot.user} est connecté!')
    logger.info(f'🌐 Serveurs: {len(bot.guilds)}')
    
    # Check for API key
    if os.environ.get('EMERGENT_LLM_KEY'):
        logger.info(f'🤖 Clé IA: Configurée')
    else:
        logger.warning(f'⚠️ EMERGENT_LLM_KEY non configurée - IA désactivée')
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="✨ /aide | Anti-Spam ON ⚡"
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
            await log_action(member.guild, "Anti-Raid", f"{member} a été {action} (raid détecté)", NEON.RED)
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
    
    if before.channel and before.channel.name.startswith("🔊 ") and len(before.channel.members) == 0:
        try:
            await before.channel.delete()
        except:
            pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Anti-spam check
    if message.guild:
        is_spam = await check_spam(message)
        if is_spam:
            return
    
    content = message.content.lower()
    if content.startswith(('aegis ', 'glados ')):
        await message.reply(random.choice(GLADOS_RESPONSES))
    
    await bot.process_commands(message)

# ==================== TICKET SYSTEM (CUSTOMIZABLE) ====================
class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

class DynamicTicketButton(discord.ui.Button):
    def __init__(self, label: str = "✨ Ouvrir un Ticket ✨", custom_id: str = "open_ticket_dynamic"):
        super().__init__(label=label, style=discord.ButtonStyle.blurple, custom_id=custom_id, emoji="🎫")
    
    async def callback(self, interaction: discord.Interaction):
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
            
            await log_action(interaction.guild, "Ticket Ouvert", f"{interaction.user.mention} a ouvert un ticket")
            
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
        guild_id = str(interaction.guild.id)
        
        # Try to find configured role first
        role_id = bot.verification_roles.get(guild_id)
        role = None
        
        if role_id:
            role = interaction.guild.get_role(role_id)
        
        # Fallback to common role names
        if not role:
            for name in ["Membre", "Vérifié", "✅ Vérifié", "🎮 Membre", "Verified"]:
                role = discord.utils.get(interaction.guild.roles, name=name)
                if role:
                    break
        
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"{NEON.CHECK} Règlement accepté! Tu as reçu le rôle {role.mention}", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(f"{NEON.WARN} Je n'ai pas la permission d'ajouter ce rôle.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{NEON.CHECK} Règlement accepté!", ephemeral=True)

# ==================== VERIFICATION (FIXED) ====================
class VerifyButtonDynamic(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✨ Vérifier ✨", style=discord.ButtonStyle.green, custom_id="verify_btn_dynamic", emoji="✅")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id)
        
        # Get configured role
        role_id = bot.verification_roles.get(guild_id)
        role = None
        
        if role_id:
            role = interaction.guild.get_role(role_id)
        
        # Fallback
        if not role:
            for name in ["Vérifié", "✅ Vérifié", "Verified", "Membre"]:
                role = discord.utils.get(interaction.guild.roles, name=name)
                if role:
                    break
        
        # Create role if not exists
        if not role:
            try:
                role = await interaction.guild.create_role(
                    name="✅ Vérifié",
                    color=discord.Color.green(),
                    reason="Auto-création rôle vérification"
                )
                bot.verification_roles[guild_id] = role.id
                bot.save_data('verification_roles', bot.verification_roles)
            except:
                return await interaction.response.send_message(f"{NEON.WARN} Impossible de créer le rôle.", ephemeral=True)
        
        # Check if already has role
        if role in interaction.user.roles:
            return await interaction.response.send_message(f"{NEON.CHECK} Tu es déjà vérifié!", ephemeral=True)
        
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"{NEON.CHECK} Vérifié! Tu as reçu le rôle {role.mention}", ephemeral=True)
            await log_action(interaction.guild, "Vérification", f"{interaction.user.mention} s'est vérifié", NEON.GREEN)
        except discord.Forbidden:
            await interaction.response.send_message(f"{NEON.WARN} Je n'ai pas la permission d'ajouter le rôle. Vérifie que mon rôle est au-dessus du rôle à donner.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"{NEON.WARN} Erreur: {str(e)[:50]}", ephemeral=True)

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
        
        app_channel = discord.utils.get(interaction.guild.text_channels, name="candidatures") or \
                      discord.utils.get(interaction.guild.text_channels, name="applications")
        
        if app_channel:
            await app_channel.send(embed=embed)
            await interaction.response.send_message(f"{NEON.CHECK} Candidature envoyée!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{NEON.WARN} Aucun salon 'candidatures' trouvé!", ephemeral=True)

# ==================== ROLE SELECT MENU ====================
class RoleSelectMenu(discord.ui.Select):
    def __init__(self, roles: List[discord.Role]):
        options = [
            discord.SelectOption(label=role.name, value=str(role.id), emoji="🎭")
            for role in roles[:25]
        ]
        super().__init__(placeholder="Choisis tes rôles...", min_values=0, max_values=len(options), options=options, custom_id="role_select_menu")
    
    async def callback(self, interaction: discord.Interaction):
        selected_role_ids = [int(v) for v in self.values]
        added, removed = [], []
        
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
        if added: response.append(f"✅ Ajoutés: {', '.join(added)}")
        if removed: response.append(f"❌ Retirés: {', '.join(removed)}")
        await interaction.response.send_message("\n".join(response) if response else "Aucun changement", ephemeral=True)

class RoleSelectView(discord.ui.View):
    def __init__(self, roles: List[discord.Role]):
        super().__init__(timeout=None)
        self.add_item(RoleSelectMenu(roles))

# ==================== SLASH COMMANDS ====================

@bot.tree.command(name="aide", description="Liste des commandes")
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{NEON.SPARKLE} ═══ Commandes d'Aegis V2 ═══ {NEON.SPARKLE}", color=NEON.PINK)
    embed.add_field(name=f"{NEON.DIAMOND} Membres", value="```/rename /resetpseudo /ban /unban /kick /mute /unmute```", inline=False)
    embed.add_field(name=f"{NEON.CHANNEL} Salons", value="```/creersalon /creervoice /supprimersalon /lock /unlock /slowmode /purge /purgeall```", inline=False)
    embed.add_field(name=f"{NEON.ROLE} Rôles", value="```/creerole /supprole /addrole /removerole /roleall /autorole /rolemenu```", inline=False)
    embed.add_field(name=f"{NEON.GEAR} Systèmes", value="```/panel /reglement /verification /candidature /giveaway```", inline=False)
    embed.add_field(name=f"{NEON.ROCKET} Serveur", value="```/setup /logs /welcome /backup /restore```", inline=False)
    embed.add_field(name=f"{NEON.AI} IA", value="```/image /annonceia /tts /parler```", inline=False)
    embed.add_field(name=f"{NEON.SPAM} Protection", value="```/antiraid /antispam```", inline=False)
    embed.set_footer(text=f"⚡ Aegis Bot V2 • Anti-Spam ON ⚡")
    await interaction.response.send_message(embed=embed)

# ==================== PANEL COMMAND (CUSTOMIZABLE) ====================
@bot.tree.command(name="panel", description="Créer un panel de tickets personnalisé")
@app_commands.describe(
    titre="Titre du panel",
    description="Description du panel",
    bouton="Texte du bouton",
    couleur="Couleur hex (ex: #ff1493)",
    role_support="Rôle support (optionnel)",
    logs_salon="Salon logs (optionnel)"
)
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction, 
                titre: str = "🎫 Support", 
                description: str = "Clique sur le bouton ci-dessous pour ouvrir un ticket et contacter le staff!",
                bouton: str = "✨ Ouvrir un Ticket ✨",
                couleur: str = "#ff1493",
                role_support: discord.Role = None, 
                logs_salon: discord.TextChannel = None):
    
    guild_id = str(interaction.guild.id)
    config = {
        "support_role": role_support.id if role_support else None,
        "logs_channel": logs_salon.id if logs_salon else None,
        "mention_role": role_support.id if role_support else None
    }
    bot.ticket_configs[guild_id] = config
    bot.save_data('ticket_configs', bot.ticket_configs)
    
    try:
        color = discord.Color(int(couleur.replace("#", ""), 16))
    except:
        color = NEON.PINK
    
    embed = discord.Embed(
        title=f"{NEON.TICKET} ═══ {titre} ═══ {NEON.TICKET}",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} {description}\n```\n{NEON.NEON_LINE}\n```",
        color=color
    )
    embed.set_footer(text=f"⚡ Aegis • Tickets ⚡")
    
    # Create view with custom button
    view = discord.ui.View(timeout=None)
    button = DynamicTicketButton(label=bouton)
    view.add_item(button)
    
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"{NEON.CHECK} Panel créé avec succès!\n**Titre:** {titre}\n**Bouton:** {bouton}", ephemeral=True)

# ==================== VERIFICATION (FIXED WITH ROLE CHOICE) ====================
@bot.tree.command(name="verification", description="Créer un système de vérification")
@app_commands.describe(role="Rôle à donner", titre="Titre", description="Description", bouton="Texte du bouton")
@app_commands.default_permissions(administrator=True)
async def verification(interaction: discord.Interaction, 
                       role: discord.Role = None,
                       titre: str = "🛡️ Vérification",
                       description: str = "Clique sur le bouton pour te vérifier et accéder au serveur!",
                       bouton: str = "✨ Vérifier ✨"):
    
    guild_id = str(interaction.guild.id)
    
    # Create role if not provided
    if not role:
        role = discord.utils.get(interaction.guild.roles, name="✅ Vérifié")
        if not role:
            try:
                role = await interaction.guild.create_role(
                    name="✅ Vérifié",
                    color=discord.Color.green(),
                    reason="Création auto rôle vérification"
                )
            except:
                return await interaction.response.send_message(f"{NEON.WARN} Impossible de créer le rôle.", ephemeral=True)
    
    # Save role config
    bot.verification_roles[guild_id] = role.id
    bot.save_data('verification_roles', bot.verification_roles)
    
    embed = discord.Embed(
        title=f"{NEON.SHIELD} ═══ {titre} ═══ {NEON.SHIELD}",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} {description}\n\n**Rôle:** {role.mention}\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.BLUE
    )
    
    await interaction.channel.send(embed=embed, view=VerifyButtonDynamic())
    await interaction.response.send_message(f"{NEON.CHECK} Vérification configurée!\n**Rôle:** {role.mention}\n\n⚠️ Assure-toi que le rôle du bot est AU-DESSUS du rôle {role.mention} dans la hiérarchie!", ephemeral=True)

# ==================== LOCK (IMPROVED) ====================
@bot.tree.command(name="lock", description="Verrouiller un salon avec options")
@app_commands.describe(
    salon="Salon à verrouiller (actuel si vide)",
    bloquer_lecture="Bloquer aussi la lecture du salon",
    bloquer_reactions="Bloquer les réactions",
    raison="Raison du verrouillage"
)
@app_commands.default_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction, 
               salon: discord.TextChannel = None,
               bloquer_lecture: bool = False,
               bloquer_reactions: bool = False,
               raison: str = "Verrouillage"):
    
    target = salon or interaction.channel
    
    overwrites = target.overwrites_for(interaction.guild.default_role)
    overwrites.send_messages = False
    
    if bloquer_lecture:
        overwrites.view_channel = False
    if bloquer_reactions:
        overwrites.add_reactions = False
    
    await target.set_permissions(interaction.guild.default_role, overwrite=overwrites)
    
    options = []
    options.append("Messages bloqués")
    if bloquer_lecture: options.append("Lecture bloquée")
    if bloquer_reactions: options.append("Réactions bloquées")
    
    embed = discord.Embed(
        title=f"🔒 Salon Verrouillé",
        description=f"**Salon:** {target.mention}\n**Options:** {', '.join(options)}\n**Raison:** {raison}",
        color=NEON.BLUE
    )
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Lock", f"{interaction.user} a verrouillé {target.mention}\nRaison: {raison}")

@bot.tree.command(name="unlock", description="Déverrouiller un salon")
@app_commands.describe(salon="Salon à déverrouiller (actuel si vide)")
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction, salon: discord.TextChannel = None):
    target = salon or interaction.channel
    
    overwrites = target.overwrites_for(interaction.guild.default_role)
    overwrites.send_messages = True
    overwrites.view_channel = True
    overwrites.add_reactions = True
    
    await target.set_permissions(interaction.guild.default_role, overwrite=overwrites)
    
    embed = create_neon_embed("Salon Déverrouillé", f"🔓 {target.mention} est maintenant ouvert!", NEON.PINK)
    await interaction.response.send_message(embed=embed)

# ==================== SETUP (EXTENDED) ====================
@bot.tree.command(name="setup", description="Configuration complète du serveur (25+ salons)")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer()
    g = interaction.guild
    created_roles = []
    created_text = []
    created_voice = []
    
    progress_embed = discord.Embed(
        title=f"{NEON.GEAR} ═══ SETUP EN COURS ═══",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.LIGHTNING} Configuration complète...\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.BLUE
    )
    progress_msg = await interaction.followup.send(embed=progress_embed)
    
    # Extended roles
    roles_config = [
        ("━━━ STAFF ━━━", 0x2f3136, False),
        (f"{NEON.CROWN} Fondateur", 0xFF1493, True),
        (f"{NEON.DIAMOND} Co-Fondateur", 0x9D00FF, True),
        (f"💼 Directeur", 0xE91E63, True),
        (f"⚔️ Administrateur", 0xe74c3c, True),
        (f"🛡️ Super-Modérateur", 0x3498db, True),
        (f"{NEON.SHIELD} Modérateur", 0x00FFFF, True),
        (f"🎮 Animateur", 0x2ecc71, False),
        (f"🔧 Support", 0xf39c12, False),
        ("━━━ GRADES ━━━", 0x2f3136, False),
        (f"💎 VIP", 0xf1c40f, False),
        (f"🌟 Premium", 0xe67e22, False),
        (f"🎖️ Fidèle", 0x9b59b6, False),
        (f"🔥 Actif", 0xe74c3c, False),
        ("━━━ MEMBRES ━━━", 0x2f3136, False),
        (f"{NEON.CHECK} Vérifié", 0x2ecc71, False),
        ("🎮 Membre", 0x95a5a6, False),
        ("━━━ BOTS ━━━", 0x2f3136, False),
        ("🤖 Bot", 0x7289da, False),
    ]
    
    for name, color, hoist in roles_config:
        if not discord.utils.get(g.roles, name=name):
            try:
                await g.create_role(name=name, color=discord.Color(color), hoist=hoist)
                created_roles.append(name)
                await asyncio.sleep(0.3)
            except:
                pass
    
    # Extended structure
    structure = {
        f"📌 ═══ IMPORTANT ═══": {
            "text": ["📜・règles", "📢・annonces", "📰・news", "🎁・partenariats"],
            "voice": []
        },
        f"👋 ═══ ACCUEIL ═══": {
            "text": ["👋・bienvenue", "🚪・départs", "✅・vérification", "🎫・rôles"],
            "voice": []
        },
        f"💬 ═══ DISCUSSION ═══": {
            "text": ["💬・général", "🖼️・médias", "🔗・liens", "🤖・bot-commands"],
            "voice": ["🔊 Général", "🔊 Discussion", "🔊 Chill"]
        },
        f"🎮 ═══ GAMING ═══": {
            "text": ["🎮・gaming-chat", "📺・streams", "🏆・clips"],
            "voice": ["🎮 Gaming 1", "🎮 Gaming 2", "🎮 Ranked"]
        },
        f"🎵 ═══ MUSIQUE ═══": {
            "text": ["🎵・playlist"],
            "voice": ["🎵 Musique", "🎧 Écoute"]
        },
        f"📩 ═══ SUPPORT ═══": {
            "text": ["❓・aide", "💡・suggestions", "🐛・bugs"],
            "voice": ["🆘 Support Vocal"]
        },
        f"🔒 ═══ STAFF ═══": {
            "text": ["📋・staff-chat", "📊・logs", "🗳️・votes-staff"],
            "voice": ["🔒 Staff Vocal", "🔒 Réunion"]
        },
        f"🎫 Tickets": {
            "text": [],
            "voice": []
        },
        f"📝 Candidatures": {
            "text": ["📝・candidatures"],
            "voice": []
        }
    }
    
    for cat_name, channels in structure.items():
        cat = discord.utils.get(g.categories, name=cat_name)
        if not cat:
            try:
                # Set permissions for staff category
                overwrites = {}
                if "STAFF" in cat_name:
                    overwrites = {
                        g.default_role: discord.PermissionOverwrite(view_channel=False),
                        g.me: discord.PermissionOverwrite(view_channel=True)
                    }
                cat = await g.create_category(cat_name, overwrites=overwrites)
                await asyncio.sleep(0.3)
            except:
                continue
        
        # Create text channels
        for ch in channels.get("text", []):
            if not discord.utils.get(g.text_channels, name=ch):
                try:
                    await g.create_text_channel(ch, category=cat)
                    created_text.append(ch)
                    await asyncio.sleep(0.3)
                except:
                    pass
        
        # Create voice channels
        for vc in channels.get("voice", []):
            if not discord.utils.get(g.voice_channels, name=vc):
                try:
                    await g.create_voice_channel(vc, category=cat)
                    created_voice.append(vc)
                    await asyncio.sleep(0.3)
                except:
                    pass
    
    # Save verification role
    verif_role = discord.utils.get(g.roles, name=f"{NEON.CHECK} Vérifié")
    if verif_role:
        bot.verification_roles[str(g.id)] = verif_role.id
        bot.save_data('verification_roles', bot.verification_roles)
    
    final_embed = discord.Embed(
        title=f"{NEON.CHECK} ═══ SETUP TERMINÉ ═══",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} Serveur configuré avec succès!\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    final_embed.add_field(name="🎭 Rôles créés", value=f"```{len(created_roles)}```", inline=True)
    final_embed.add_field(name="💬 Salons texte", value=f"```{len(created_text)}```", inline=True)
    final_embed.add_field(name="🔊 Salons vocaux", value=f"```{len(created_voice)}```", inline=True)
    final_embed.add_field(name="📋 Prochaines étapes", value="```1. /panel - Créer les tickets\n2. /verification - Système de vérif\n3. /reglement - Créer le règlement\n4. /logs - Configurer les logs\n5. /antispam - Activer l'anti-spam```", inline=False)
    await progress_msg.edit(embed=final_embed)

# ==================== ANTI-SPAM COMMAND ====================
@bot.tree.command(name="antispam", description="Configurer l'anti-spam")
@app_commands.describe(
    activer="Activer/Désactiver",
    messages_limite="Nombre de messages max",
    temps_secondes="En combien de secondes",
    mentions_limite="Nombre de mentions max par message",
    action="Action à prendre (mute/kick/ban)",
    duree_mute="Durée du mute en minutes"
)
@app_commands.default_permissions(administrator=True)
async def antispam(interaction: discord.Interaction,
                   activer: bool = True,
                   messages_limite: int = 5,
                   temps_secondes: int = 5,
                   mentions_limite: int = 5,
                   action: str = "mute",
                   duree_mute: int = 5):
    
    guild_id = str(interaction.guild.id)
    
    config = {
        "enabled": activer,
        "msg_limit": messages_limite,
        "msg_time": temps_secondes,
        "mention_limit": mentions_limite,
        "action": action,
        "mute_duration": duree_mute
    }
    
    bot.anti_spam_config[guild_id] = config
    bot.save_data('anti_spam_config', bot.anti_spam_config)
    
    status = f"{NEON.CHECK} Activé" if activer else f"{NEON.WARN} Désactivé"
    
    embed = discord.Embed(
        title=f"{NEON.SPAM} ═══ ANTI-SPAM ═══ {NEON.SPAM}",
        description=f"```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK if activer else NEON.BLUE
    )
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Action", value=action.upper(), inline=True)
    embed.add_field(name="Durée mute", value=f"{duree_mute} min", inline=True)
    embed.add_field(name="🔴 Spam Messages", value=f"{messages_limite} msgs / {temps_secondes}s", inline=True)
    embed.add_field(name="🔴 Spam Mentions", value=f"{mentions_limite}+ mentions", inline=True)
    embed.set_footer(text="L'anti-spam protège contre le flood et le spam de mentions")
    
    await interaction.response.send_message(embed=embed)

# ==================== OTHER COMMANDS ====================

@bot.tree.command(name="rename", description="Renommer un membre")
@app_commands.describe(membre="Le membre", nouveau_pseudo="Nouveau pseudo")
@app_commands.default_permissions(manage_nicknames=True)
async def rename(interaction: discord.Interaction, membre: discord.Member, nouveau_pseudo: str):
    old_name = membre.display_name
    await membre.edit(nick=nouveau_pseudo)
    embed = create_neon_embed("Membre Renommé", f"{old_name} → **{nouveau_pseudo}**", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="resetpseudo", description="Réinitialiser le pseudo")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(manage_nicknames=True)
async def resetpseudo(interaction: discord.Interaction, membre: discord.Member):
    await membre.edit(nick=None)
    embed = create_neon_embed("Pseudo Réinitialisé", f"{membre.mention}", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ban", description="Bannir un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.ban(reason=raison)
    embed = discord.Embed(title=f"{NEON.BAN} Membre Banni", description=f"**{membre}**\n**Raison:** {raison}", color=NEON.RED)
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild, "Ban", f"{interaction.user} a banni {membre}\nRaison: {raison}", NEON.RED)

@bot.tree.command(name="unban", description="Débannir un utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur")
@app_commands.default_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        embed = create_neon_embed("Membre Débanni", f"**{user}** peut revenir", NEON.PINK)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message(f"{NEON.WARN} Utilisateur non trouvé", ephemeral=True)

@bot.tree.command(name="kick", description="Expulser un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.kick(reason=raison)
    embed = create_neon_embed("Membre Expulsé", f"{membre} - {raison}", NEON.PURPLE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mute", description="Mute un membre")
@app_commands.describe(membre="Le membre", duree="Durée en minutes")
@app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, membre: discord.Member, duree: int = 10):
    await membre.timeout(datetime.now(timezone.utc) + timedelta(minutes=duree))
    embed = create_neon_embed("Membre Muté", f"{membre.mention} pour {duree} min", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unmute", description="Unmute un membre")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, membre: discord.Member):
    await membre.timeout(None)
    embed = create_neon_embed("Membre Unmute", f"{membre.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="creersalon", description="Créer un salon textuel")
@app_commands.describe(nom="Nom du salon", categorie="Catégorie")
@app_commands.default_permissions(manage_channels=True)
async def creersalon(interaction: discord.Interaction, nom: str, categorie: discord.CategoryChannel = None):
    channel = await interaction.guild.create_text_channel(nom, category=categorie)
    embed = create_neon_embed("Salon Créé", f"{channel.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="creervoice", description="Créer un salon vocal")
@app_commands.describe(nom="Nom", categorie="Catégorie", limite="Limite users")
@app_commands.default_permissions(manage_channels=True)
async def creervoice(interaction: discord.Interaction, nom: str, categorie: discord.CategoryChannel = None, limite: int = 0):
    channel = await interaction.guild.create_voice_channel(nom, category=categorie, user_limit=limite if limite > 0 else None)
    embed = create_neon_embed("Salon Vocal Créé", f"🔊 {channel.name}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="supprimersalon", description="Supprimer un salon")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(manage_channels=True)
async def supprimersalon(interaction: discord.Interaction, salon: discord.TextChannel):
    name = salon.name
    await salon.delete()
    embed = create_neon_embed("Salon Supprimé", f"`{name}`", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="slowmode", description="Mode lent")
@app_commands.describe(secondes="Délai (0 = désactiver)")
@app_commands.default_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, secondes: int):
    await interaction.channel.edit(slowmode_delay=secondes)
    embed = create_neon_embed("Mode Lent", f"{'Activé: ' + str(secondes) + 's' if secondes > 0 else 'Désactivé'}", NEON.BLUE if secondes > 0 else NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="purge", description="Supprimer des messages")
@app_commands.describe(nombre="Nombre de messages")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, nombre: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=nombre)
    await interaction.followup.send(f"{NEON.CHECK} {len(deleted)} messages supprimés")

@bot.tree.command(name="purgeall", description="Purger tous les messages")
@app_commands.describe(salon="Le salon")
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
    await interaction.followup.send(f"{NEON.CHECK} {count} messages supprimés")

@bot.tree.command(name="creerole", description="Créer un rôle")
@app_commands.describe(nom="Nom", couleur="Couleur hex")
@app_commands.default_permissions(manage_roles=True)
async def creerole(interaction: discord.Interaction, nom: str, couleur: str = "#ff1493"):
    color = discord.Color(int(couleur.replace("#", ""), 16))
    role = await interaction.guild.create_role(name=nom, color=color)
    embed = create_neon_embed("Rôle Créé", f"{role.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="supprole", description="Supprimer un rôle")
@app_commands.describe(role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def supprole(interaction: discord.Interaction, role: discord.Role):
    name = role.name
    await role.delete()
    embed = create_neon_embed("Rôle Supprimé", f"`{name}`", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addrole", description="Ajouter un rôle")
@app_commands.describe(membre="Le membre", role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.add_roles(role)
    embed = create_neon_embed("Rôle Ajouté", f"{role.mention} → {membre.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="removerole", description="Retirer un rôle")
@app_commands.describe(membre="Le membre", role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.remove_roles(role)
    embed = create_neon_embed("Rôle Retiré", f"{role.mention} de {membre.mention}", NEON.BLUE)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="roleall", description="Ajouter un rôle à tous")
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
    embed = create_neon_embed("Rôle Ajouté à Tous", f"{role.mention} → {count} membres", NEON.PINK)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="autorole", description="Auto-rôle pour nouveaux membres")
@app_commands.describe(role="Le rôle")
@app_commands.default_permissions(administrator=True)
async def autorole(interaction: discord.Interaction, role: discord.Role):
    bot.auto_roles[str(interaction.guild.id)] = role.id
    bot.save_data('auto_roles', bot.auto_roles)
    embed = create_neon_embed("Auto-Rôle", f"Nouveaux membres: {role.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rolemenu", description="Menu de sélection de rôles")
@app_commands.describe(titre="Titre", roles="Rôles (@Role1, @Role2)")
@app_commands.default_permissions(administrator=True)
async def rolemenu(interaction: discord.Interaction, titre: str, roles: str):
    role_ids = re.findall(r'<@&(\d+)>', roles)
    role_objects = [interaction.guild.get_role(int(rid)) for rid in role_ids if interaction.guild.get_role(int(rid))]
    
    if not role_objects:
        return await interaction.response.send_message(f"{NEON.WARN} Utilise des mentions de rôles.", ephemeral=True)
    
    embed = discord.Embed(
        title=f"{NEON.ROLE} ═══ {titre} ═══ {NEON.ROLE}",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} Choisis tes rôles!\n\n" + "\n".join([f"• {r.mention}" for r in role_objects]) + f"\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    await interaction.channel.send(embed=embed, view=RoleSelectView(role_objects))
    await interaction.response.send_message(f"{NEON.CHECK} Menu créé!", ephemeral=True)

@bot.tree.command(name="reglement", description="Créer un règlement")
@app_commands.describe(avec_bouton="Bouton d'acceptation", role="Rôle à donner")
@app_commands.default_permissions(administrator=True)
async def reglement(interaction: discord.Interaction, avec_bouton: bool = True, role: discord.Role = None):
    if role:
        bot.verification_roles[str(interaction.guild.id)] = role.id
        bot.save_data('verification_roles', bot.verification_roles)
    
    embed = discord.Embed(
        title=f"{NEON.SPARKLE} ═══ RÈGLEMENT ═══ {NEON.SPARKLE}",
        description=f"```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    for title, content in DEFAULT_RULES:
        embed.add_field(name=title, value=f"┃ {content}", inline=False)
    embed.set_footer(text=f"⚡ Aegis Bot V2 ⚡")
    
    if avec_bouton:
        await interaction.channel.send(embed=embed, view=RulesAcceptButton())
    else:
        await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"{NEON.CHECK} Règlement créé!", ephemeral=True)

@bot.tree.command(name="candidature", description="Système de candidature")
@app_commands.describe(titre="Titre")
@app_commands.default_permissions(administrator=True)
async def candidature(interaction: discord.Interaction, titre: str = "Recrutement"):
    embed = discord.Embed(
        title=f"📝 ═══ {titre} ═══ 📝",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.SPARKLE} Clique pour postuler!\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.PINK
    )
    await interaction.channel.send(embed=embed, view=ApplicationButton())
    await interaction.response.send_message(f"{NEON.CHECK} Candidature créée!", ephemeral=True)

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
    winners_ids = random.sample(participants, min(gagnants, len(participants)))
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
    embed = create_neon_embed("Logs", f"Configuré: {salon.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="welcome", description="Messages de bienvenue/départ")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(administrator=True)
async def welcome(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.welcome_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('welcome_channels', bot.welcome_channels)
    embed = create_neon_embed("Bienvenue/Départ", f"Configuré: {salon.mention}", NEON.PINK)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="backup", description="Sauvegarder le serveur")
@app_commands.describe(nom="Nom de la sauvegarde")
@app_commands.default_permissions(administrator=True)
async def backup(interaction: discord.Interaction, nom: str = None):
    await interaction.response.defer(ephemeral=True)
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
        description=f"{NEON.CHECK} Sauvegarde créée!",
        color=NEON.PINK
    )
    embed.add_field(name="Rôles", value=f"```{len(backup_data['roles'])}```", inline=True)
    embed.add_field(name="Salons", value=f"```{len(backup_data['text_channels']) + len(backup_data['voice_channels'])}```", inline=True)
    await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Log only (name hidden from public)
    await log_action(guild, "Backup", f"Sauvegarde créée par {interaction.user}: `{backup_name}`")

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
    
    for ch_data in backup_data.get("voice_channels", []):
        if not discord.utils.get(guild.voice_channels, name=ch_data["name"]):
            try:
                category = cat_map.get(ch_data.get("category")) or discord.utils.get(guild.categories, name=ch_data.get("category"))
                await guild.create_voice_channel(name=ch_data["name"], category=category)
                restored["channels"] += 1
                await asyncio.sleep(0.3)
            except:
                pass
    
    embed = discord.Embed(
        title=f"{NEON.CHECK} ═══ RESTAURATION ═══",
        description=f"**Rôles:** {restored['roles']}\n**Salons:** {restored['channels']}",
        color=NEON.PINK
    )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="antiraid", description="Configurer l'anti-raid")
@app_commands.describe(activer="Activer", seuil="Joins/10s", action="kick/ban")
@app_commands.default_permissions(administrator=True)
async def antiraid(interaction: discord.Interaction, activer: bool = True, seuil: int = 5, action: str = "kick"):
    guild_id = str(interaction.guild.id)
    bot.raid_protection[guild_id] = {"enabled": activer, "threshold": seuil, "action": action}
    bot.save_data('raid_protection', bot.raid_protection)
    
    embed = discord.Embed(
        title=f"{NEON.SHIELD} ═══ ANTI-RAID ═══",
        description=f"**Status:** {'✅ Activé' if activer else '❌ Désactivé'}\n**Seuil:** {seuil} joins/10s\n**Action:** {action}",
        color=NEON.PINK if activer else NEON.BLUE
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tempvoice", description="Salons vocaux temporaires")
@app_commands.describe(salon="Salon déclencheur")
@app_commands.default_permissions(administrator=True)
async def tempvoice(interaction: discord.Interaction, salon: discord.VoiceChannel):
    bot.temp_voice_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('temp_voice_channels', bot.temp_voice_channels)
    embed = create_neon_embed("Vocaux Temporaires", f"Rejoins {salon.name} pour créer ton vocal!", NEON.PINK)
    await interaction.response.send_message(embed=embed)

# ==================== AI COMMANDS ====================
@bot.tree.command(name="image", description="Générer une image avec l'IA")
@app_commands.describe(prompt="Description de l'image")
async def image(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        embed_progress = discord.Embed(
            title=f"{NEON.IMAGE} Génération en cours...",
            description=f"```{prompt[:200]}```\n\n⏳ Cela peut prendre 30-60 secondes...",
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
        error_msg = str(e)
        await interaction.edit_original_response(embed=discord.Embed(
            title=f"{NEON.WARN} Erreur",
            description=f"```{error_msg[:500]}```",
            color=NEON.RED
        ))

@bot.tree.command(name="annonceia", description="Créer une annonce avec l'IA")
@app_commands.describe(sujet="Sujet", style="Style (formel/décontracté/hype)")
async def annonceia(interaction: discord.Interaction, sujet: str, style: str = "hype"):
    await interaction.response.defer()
    try:
        text = await generate_ai_text(
            f"Crée une annonce Discord en français pour: {sujet}. Style: {style}. Max 500 caractères. Utilise des emojis.",
            "Tu es un community manager Discord expert."
        )
        
        embed = discord.Embed(
            title=f"📢 ═══ ANNONCE ═══ 📢",
            description=f"```\n{NEON.NEON_LINE}\n```\n{text}\n```\n{NEON.NEON_LINE}\n```",
            color=NEON.PINK
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"{NEON.WARN} Erreur: {str(e)[:200]}", ephemeral=True)

@bot.tree.command(name="tts", description="Générer un audio TTS")
@app_commands.describe(texte="Le texte", voix="Voix (nova/alloy/echo/shimmer)")
async def tts(interaction: discord.Interaction, texte: str, voix: str = "nova"):
    await interaction.response.defer()
    try:
        if len(texte) > 500:
            return await interaction.followup.send(f"{NEON.WARN} Max 500 caractères", ephemeral=True)
        
        audio_bytes = await generate_tts_audio(texte, voix)
        file = discord.File(fp=io.BytesIO(audio_bytes), filename="tts.mp3")
        embed = discord.Embed(title=f"{NEON.VOICE} Message Vocal", description=f"```{texte[:200]}```", color=NEON.PINK)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        await interaction.followup.send(f"{NEON.WARN} Erreur: {str(e)[:200]}", ephemeral=True)

@bot.tree.command(name="parler", description="Faire parler le bot en vocal")
@app_commands.describe(texte="Le texte", voix="Voix")
async def parler(interaction: discord.Interaction, texte: str, voix: str = "nova"):
    if not interaction.user.voice:
        return await interaction.response.send_message(f"{NEON.WARN} Rejoins un vocal!", ephemeral=True)
    
    await interaction.response.defer()
    try:
        audio_bytes = await generate_tts_audio(texte, voix)
        temp_path = DATA_DIR / f"tts_{interaction.id}.mp3"
        with open(temp_path, 'wb') as f:
            f.write(audio_bytes)
        
        vc = await interaction.user.voice.channel.connect()
        vc.play(discord.FFmpegPCMAudio(str(temp_path)), after=lambda e: asyncio.run_coroutine_threadsafe(vc.disconnect(), bot.loop))
        
        embed = create_neon_embed("Lecture en cours", f"```{texte[:100]}```", NEON.PINK)
        await interaction.followup.send(embed=embed)
        
        while vc.is_playing():
            await asyncio.sleep(1)
        try:
            temp_path.unlink()
        except:
            pass
    except Exception as e:
        await interaction.followup.send(f"{NEON.WARN} Erreur: {str(e)[:100]}", ephemeral=True)

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
        logger.info("⚡ Démarrage d'Aegis Bot V2...")
        bot.run(token)
    else:
        logger.error("❌ DISCORD_BOT_TOKEN manquant!")
        print("Erreur: Ajoute DISCORD_BOT_TOKEN dans .env ou Railway")
