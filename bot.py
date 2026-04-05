import discord
from discord.ext import commands, tasks
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
    GREEN = 0x00FF00
    RED = 0xFF0000
    ORANGE = 0xFF6600
    GOLD = 0xFFD700
    
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
    TICKET_CLOSE = "🔐"
    
    BAN = "⛔"
    KICK = "👢"
    MUTE = "🔇"
    WARN = "⚠️"
    SHIELD = "🛡️"
    
    CHECK = "✅"
    CROSS = "❌"
    GEAR = "⚙️"
    CHANNEL = "💬"
    VOICE = "🔊"
    ROLE = "🎭"
    IMAGE = "🖼️"
    SPAM = "🚫"
    GIVEAWAY = "🎉"
    GIFT = "🎁"
    TROPHY = "🏆"
    CLOCK = "⏰"
    
    NEON_LINE = "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"

NEON = NeonTheme()

# Bot setup
intents = discord.Intents.all()

class AegisBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=['Aegis ', 'aegis ', 'AEGIS '], intents=intents, help_command=None)
        self.giveaways = {}  # message_id -> giveaway data
        self.temp_voice_channels = {}
        self.auto_roles = {}
        self.logs_channels = {}
        self.welcome_channels = {}
        self.anti_raid_cache = {}
        self.backups = {}
        self.ticket_configs = {}
        self.raid_protection = {}
        self.verification_roles = {}
        self.anti_spam_config = {}
        self.warnings = {}  # guild_id -> {user_id -> [warnings]}
        # Anti-spam tracking
        self.message_cache = defaultdict(list)
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
            'verification_roles': self.verification_roles,
            'anti_spam_config': self.anti_spam_config,
            'warnings': self.warnings,
            'giveaways': self.giveaways
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
        self.add_view(RulesAcceptButton())
        self.add_view(ApplicationButton())
        # Re-add giveaway buttons for existing giveaways
        for msg_id in list(self.giveaways.keys()):
            self.add_view(GiveawayButtonView(msg_id))
        
        # Start giveaway checker
        self.check_giveaways.start()
        
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
]

def create_neon_embed(title: str, description: str = None, color: int = None) -> discord.Embed:
    return discord.Embed(
        title=f"✨ {title} ✨",
        description=description,
        color=color or NEON.PINK,
        timestamp=datetime.now(timezone.utc)
    )

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
    try:
        from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            raise Exception("❌ EMERGENT_LLM_KEY non configurée!\n\nAjoute dans Railway → Variables:\nEMERGENT_LLM_KEY=sk-emergent-7532197D963D4C9A8A")
        
        image_gen = OpenAIImageGeneration(api_key=api_key)
        images = await image_gen.generate_images(prompt=prompt, model="gpt-image-1", number_of_images=1)
        if images and len(images) > 0:
            return images[0]
        raise Exception("Aucune image générée")
    except Exception as e:
        logger.error(f"Erreur image: {e}")
        raise

async def generate_ai_text(prompt: str, system_message: str = "Tu es un assistant Discord.") -> str:
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            raise Exception("❌ EMERGENT_LLM_KEY non configurée!")
        
        chat = LlmChat(api_key=api_key, session_id=f"aegis-{datetime.now().timestamp()}", system_message=system_message).with_model("openai", "gpt-4o")
        response = await chat.send_message(UserMessage(text=prompt))
        return response
    except Exception as e:
        raise

async def generate_tts_audio(text: str, voice: str = "nova") -> bytes:
    try:
        from emergentintegrations.llm.openai import OpenAITextToSpeech
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            raise Exception("❌ EMERGENT_LLM_KEY non configurée!")
        
        tts = OpenAITextToSpeech(api_key=api_key)
        return await tts.generate_speech(text=text, model="tts-1", voice=voice)
    except Exception as e:
        raise

# ==================== ANTI-SPAM SYSTEM ====================
async def check_spam(message: discord.Message) -> bool:
    if message.author.bot or message.author.guild_permissions.administrator:
        return False
    
    guild_id = str(message.guild.id)
    user_id = message.author.id
    now = datetime.now(timezone.utc)
    
    config = bot.anti_spam_config.get(guild_id, {"enabled": True, "msg_limit": 5, "msg_time": 5, "mention_limit": 5, "action": "mute", "mute_duration": 5})
    
    if not config.get("enabled", True):
        return False
    
    bot.message_cache[user_id].append(now)
    bot.message_cache[user_id] = [t for t in bot.message_cache[user_id] if (now - t).total_seconds() < config.get("msg_time", 5)]
    
    is_spam = False
    reason = ""
    
    if len(bot.message_cache[user_id]) > config.get("msg_limit", 5):
        is_spam = True
        reason = f"Spam ({len(bot.message_cache[user_id])} msgs/{config.get('msg_time', 5)}s)"
    
    mention_count = len(message.mentions) + len(message.role_mentions)
    if message.mention_everyone:
        mention_count += 50
    
    if mention_count >= config.get("mention_limit", 5):
        is_spam = True
        reason = f"Spam mentions ({mention_count})"
    
    if is_spam:
        try:
            await message.delete()
            action = config.get("action", "mute")
            if action == "kick":
                await message.author.kick(reason=reason)
            elif action == "ban":
                await message.author.ban(reason=reason)
            else:
                await message.author.timeout(datetime.now(timezone.utc) + timedelta(minutes=config.get("mute_duration", 5)), reason=reason)
            
            embed = discord.Embed(title=f"{NEON.SPAM} Anti-Spam", description=f"{message.author.mention} sanctionné!\n**Raison:** {reason}", color=NEON.RED)
            await message.channel.send(embed=embed, delete_after=10)
            bot.message_cache[user_id] = []
            return True
        except:
            pass
    return False

# ==================== GIVEAWAY SYSTEM (REFAIT) ====================
class GiveawayButtonView(discord.ui.View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.add_item(GiveawayParticipateButton(giveaway_id))

class GiveawayParticipateButton(discord.ui.Button):
    def __init__(self, giveaway_id: str):
        super().__init__(
            label="🎉 Participer 🎉",
            style=discord.ButtonStyle.green,
            custom_id=f"giveaway_participate_{giveaway_id}",
            emoji="🎁"
        )
        self.giveaway_id = giveaway_id
    
    async def callback(self, interaction: discord.Interaction):
        giveaway = bot.giveaways.get(self.giveaway_id)
        
        if not giveaway:
            return await interaction.response.send_message(f"{NEON.CROSS} Ce giveaway n'existe plus!", ephemeral=True)
        
        if giveaway.get("ended", False):
            return await interaction.response.send_message(f"{NEON.CROSS} Ce giveaway est terminé!", ephemeral=True)
        
        user_id = interaction.user.id
        participants = giveaway.get("participants", [])
        
        if user_id in participants:
            # Retirer la participation
            participants.remove(user_id)
            giveaway["participants"] = participants
            bot.giveaways[self.giveaway_id] = giveaway
            bot.save_data('giveaways', bot.giveaways)
            
            await interaction.response.send_message(f"{NEON.CROSS} Tu ne participes plus au giveaway.", ephemeral=True)
        else:
            # Ajouter la participation
            participants.append(user_id)
            giveaway["participants"] = participants
            bot.giveaways[self.giveaway_id] = giveaway
            bot.save_data('giveaways', bot.giveaways)
            
            await interaction.response.send_message(f"{NEON.CHECK} Tu participes! ({len(participants)} participants)", ephemeral=True)
        
        # Update embed with participant count
        try:
            message = interaction.message
            embed = message.embeds[0]
            
            # Update participants field
            for i, field in enumerate(embed.fields):
                if "Participants" in field.name:
                    embed.set_field_at(i, name=f"{NEON.STAR} Participants", value=f"```{len(participants)}```", inline=True)
                    break
            
            await message.edit(embed=embed)
        except:
            pass

@tasks.loop(minutes=1)
async def check_giveaways():
    """Check and end giveaways that have expired"""
    now = datetime.now(timezone.utc)
    
    for msg_id, giveaway in list(bot.giveaways.items()):
        if giveaway.get("ended", False):
            continue
        
        end_time_str = giveaway.get("end_time")
        if not end_time_str:
            continue
        
        try:
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            if now >= end_time:
                await end_giveaway_auto(msg_id, giveaway)
        except:
            pass

async def end_giveaway_auto(msg_id: str, giveaway: dict):
    """Auto-end a giveaway"""
    try:
        channel_id = giveaway.get("channel_id")
        guild_id = giveaway.get("guild_id")
        winners_count = giveaway.get("winners", 1)
        participants = giveaway.get("participants", [])
        prize = giveaway.get("prize", "Prix")
        title = giveaway.get("title", "Giveaway")
        
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return
        
        channel = guild.get_channel(int(channel_id))
        if not channel:
            return
        
        # Mark as ended
        giveaway["ended"] = True
        bot.giveaways[msg_id] = giveaway
        bot.save_data('giveaways', bot.giveaways)
        
        # Select winners
        winners = []
        if participants:
            winners_ids = random.sample(participants, min(winners_count, len(participants)))
            for wid in winners_ids:
                try:
                    user = await bot.fetch_user(wid)
                    winners.append(user)
                except:
                    pass
        
        # Create result embed
        if winners:
            winners_text = "\n".join([f"{NEON.TROPHY} {w.mention}" for w in winners])
            embed = discord.Embed(
                title=f"{NEON.GIVEAWAY} ═══ GIVEAWAY TERMINÉ ═══ {NEON.GIVEAWAY}",
                description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.GIFT} **{title}**\n\n**Prix:** {prize}\n```\n{NEON.NEON_LINE}\n```",
                color=NEON.GOLD
            )
            embed.add_field(name=f"{NEON.TROPHY} Gagnant(s)", value=winners_text, inline=False)
            embed.add_field(name=f"{NEON.STAR} Participants", value=f"```{len(participants)}```", inline=True)
        else:
            embed = discord.Embed(
                title=f"{NEON.GIVEAWAY} ═══ GIVEAWAY TERMINÉ ═══ {NEON.GIVEAWAY}",
                description=f"**{title}**\n\n{NEON.CROSS} Aucun participant!",
                color=NEON.RED
            )
        
        # Try to edit original message
        try:
            message = await channel.fetch_message(int(msg_id))
            await message.edit(embed=embed, view=None)
        except:
            pass
        
        # Announce winners
        if winners:
            announce = discord.Embed(
                title=f"{NEON.GIVEAWAY} Félicitations! {NEON.GIVEAWAY}",
                description=f"{', '.join([w.mention for w in winners])} a gagné **{prize}**!",
                color=NEON.GOLD
            )
            await channel.send(content=" ".join([w.mention for w in winners]), embed=announce)
    except Exception as e:
        logger.error(f"Erreur fin giveaway: {e}")

# ==================== EVENTS ====================
@bot.event
async def on_ready():
    logger.info(f'⚡ {bot.user} est connecté!')
    logger.info(f'🌐 Serveurs: {len(bot.guilds)}')
    
    if os.environ.get('EMERGENT_LLM_KEY'):
        logger.info(f'🤖 Clé IA: Configurée')
    else:
        logger.warning(f'⚠️ EMERGENT_LLM_KEY non configurée')
    
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="✨ /aide | V3 ⚡"))

@bot.event
async def on_member_join(member):
    guild_id = str(member.guild.id)
    now = datetime.now(timezone.utc)
    
    # Anti-raid
    if guild_id not in bot.anti_raid_cache:
        bot.anti_raid_cache[guild_id] = []
    bot.anti_raid_cache[guild_id].append(now)
    bot.anti_raid_cache[guild_id] = [t for t in bot.anti_raid_cache[guild_id] if (now - t).total_seconds() < 10]
    
    raid_config = bot.raid_protection.get(guild_id, {"enabled": True, "threshold": 5, "action": "kick"})
    
    if raid_config.get("enabled", True) and len(bot.anti_raid_cache[guild_id]) > raid_config.get("threshold", 5):
        try:
            if raid_config.get("action") == "ban":
                await member.ban(reason="Anti-raid")
            else:
                await member.kick(reason="Anti-raid")
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
    
    # Welcome
    if guild_id in bot.welcome_channels:
        channel = member.guild.get_channel(bot.welcome_channels[guild_id])
        if channel:
            embed = discord.Embed(
                title=f"{NEON.SPARKLE} Bienvenue {NEON.SPARKLE}",
                description=f"{NEON.STAR} {member.mention} a rejoint!",
                color=NEON.PINK
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    guild_id = str(member.guild.id)
    if guild_id in bot.welcome_channels:
        channel = member.guild.get_channel(bot.welcome_channels[guild_id])
        if channel:
            embed = discord.Embed(title=f"{NEON.LIGHTNING} Au revoir", description=f"*{member.name} nous a quittés*", color=NEON.BLUE)
            await channel.send(embed=embed)

@bot.event
async def on_voice_state_update(member, before, after):
    guild_id = str(member.guild.id)
    
    if guild_id in bot.temp_voice_channels:
        if after.channel and after.channel.id == bot.temp_voice_channels[guild_id]:
            try:
                new_channel = await member.guild.create_voice_channel(f"🔊 {member.display_name}", category=after.channel.category)
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
    
    if message.guild:
        if await check_spam(message):
            return
    
    content = message.content.lower()
    if content.startswith(('aegis ', 'glados ')):
        await message.reply(random.choice(GLADOS_RESPONSES))
    
    await bot.process_commands(message)

# ==================== TICKET SYSTEM ====================
class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

class DynamicTicketButton(discord.ui.Button):
    def __init__(self, label: str = "✨ Ouvrir un Ticket ✨"):
        super().__init__(label=label, style=discord.ButtonStyle.blurple, custom_id="open_ticket_dynamic", emoji="🎫")
    
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
            
            if config.get("support_role"):
                support_role = interaction.guild.get_role(config["support_role"])
                if support_role:
                    overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            
            channel = await interaction.guild.create_text_channel(f"ticket-{interaction.user.name.lower()[:20]}", category=category, overwrites=overwrites)
            
            embed = discord.Embed(
                title=f"{NEON.TICKET} Nouveau Ticket",
                description=f"Bienvenue {interaction.user.mention}!\nDécris ton problème.",
                color=NEON.PINK
            )
            await channel.send(embed=embed, view=CloseTicketButton())
            await interaction.followup.send(f"{NEON.CHECK} Ticket créé: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"{NEON.WARN} Erreur: {str(e)[:100]}", ephemeral=True)

class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.danger, custom_id="close_ticket", emoji="🔐")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title=f"{NEON.TICKET_CLOSE} Fermeture", description="Suppression dans 5s...", color=NEON.BLUE)
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except:
            pass

class RulesAcceptButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✨ J'accepte ✨", style=discord.ButtonStyle.green, custom_id="accept_rules", emoji="✅")
    async def accept_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id)
        role_id = bot.verification_roles.get(guild_id)
        role = interaction.guild.get_role(role_id) if role_id else None
        
        if not role:
            for name in ["Membre", "Vérifié", "✅ Vérifié"]:
                role = discord.utils.get(interaction.guild.roles, name=name)
                if role:
                    break
        
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"{NEON.CHECK} Accepté! Rôle {role.mention} reçu.", ephemeral=True)
            except:
                await interaction.response.send_message(f"{NEON.WARN} Erreur permissions.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{NEON.CHECK} Accepté!", ephemeral=True)

class VerifyButtonDynamic(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✨ Vérifier ✨", style=discord.ButtonStyle.green, custom_id="verify_btn_dynamic", emoji="✅")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id)
        role_id = bot.verification_roles.get(guild_id)
        role = interaction.guild.get_role(role_id) if role_id else None
        
        if not role:
            for name in ["Vérifié", "✅ Vérifié", "Membre"]:
                role = discord.utils.get(interaction.guild.roles, name=name)
                if role:
                    break
        
        if not role:
            try:
                role = await interaction.guild.create_role(name="✅ Vérifié", color=discord.Color.green())
                bot.verification_roles[guild_id] = role.id
                bot.save_data('verification_roles', bot.verification_roles)
            except:
                return await interaction.response.send_message(f"{NEON.WARN} Erreur création rôle.", ephemeral=True)
        
        if role in interaction.user.roles:
            return await interaction.response.send_message(f"{NEON.CHECK} Déjà vérifié!", ephemeral=True)
        
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"{NEON.CHECK} Vérifié! {role.mention}", ephemeral=True)
        except:
            await interaction.response.send_message(f"{NEON.WARN} Erreur permissions.", ephemeral=True)

class ApplicationButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✨ Postuler ✨", style=discord.ButtonStyle.green, custom_id="apply_btn", emoji="📝")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal())

class ApplicationModal(discord.ui.Modal, title="📝 Candidature"):
    pseudo = discord.ui.TextInput(label="Pseudo", max_length=50)
    age = discord.ui.TextInput(label="Âge", max_length=3)
    motivation = discord.ui.TextInput(label="Motivation", style=discord.TextStyle.paragraph, max_length=500)
    
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title=f"{NEON.SPARKLE} Candidature", color=NEON.PINK)
        embed.add_field(name="Pseudo", value=self.pseudo.value, inline=True)
        embed.add_field(name="Âge", value=self.age.value, inline=True)
        embed.add_field(name="Discord", value=interaction.user.mention, inline=True)
        embed.add_field(name="Motivation", value=self.motivation.value, inline=False)
        
        channel = discord.utils.get(interaction.guild.text_channels, name="candidatures")
        if channel:
            await channel.send(embed=embed)
        await interaction.response.send_message(f"{NEON.CHECK} Candidature envoyée!", ephemeral=True)

class RoleSelectMenu(discord.ui.Select):
    def __init__(self, roles):
        options = [discord.SelectOption(label=r.name, value=str(r.id), emoji="🎭") for r in roles[:25]]
        super().__init__(placeholder="Choisis tes rôles...", min_values=0, max_values=len(options), options=options, custom_id="role_select")
    
    async def callback(self, interaction: discord.Interaction):
        selected = [int(v) for v in self.values]
        added, removed = [], []
        for opt in self.options:
            role = interaction.guild.get_role(int(opt.value))
            if role:
                if int(opt.value) in selected and role not in interaction.user.roles:
                    await interaction.user.add_roles(role)
                    added.append(role.name)
                elif int(opt.value) not in selected and role in interaction.user.roles:
                    await interaction.user.remove_roles(role)
                    removed.append(role.name)
        msg = []
        if added: msg.append(f"✅ {', '.join(added)}")
        if removed: msg.append(f"❌ {', '.join(removed)}")
        await interaction.response.send_message("\n".join(msg) if msg else "Aucun changement", ephemeral=True)

class RoleSelectView(discord.ui.View):
    def __init__(self, roles):
        super().__init__(timeout=None)
        self.add_item(RoleSelectMenu(roles))

# ==================== SLASH COMMANDS ====================

@bot.tree.command(name="aide", description="Liste des commandes")
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{NEON.SPARKLE} Aegis V3 {NEON.SPARKLE}", color=NEON.PINK)
    embed.add_field(name=f"{NEON.DIAMOND} Membres", value="```/rename /ban /unban /kick /mute /unmute /warn /unwarn /warns```", inline=False)
    embed.add_field(name=f"{NEON.CHANNEL} Salons", value="```/creersalon /creervoice /supprimersalon /lock /unlock /slowmode /purge```", inline=False)
    embed.add_field(name=f"{NEON.ROLE} Rôles", value="```/creerole /addrole /removerole /roleall /autorole /rolemenu```", inline=False)
    embed.add_field(name=f"{NEON.GEAR} Systèmes", value="```/panel /reglement /verification /giveaway /reroll```", inline=False)
    embed.add_field(name=f"{NEON.ROCKET} Serveur", value="```/setup /welcome /backup /restore /antiraid /antispam```", inline=False)
    embed.add_field(name=f"{NEON.IMAGE} IA", value="```/image /annonceia /tts /parler```", inline=False)
    await interaction.response.send_message(embed=embed)

# ==================== WARNING SYSTEM ====================
@bot.tree.command(name="warn", description="Avertir un membre")
@app_commands.describe(membre="Le membre", raison="Raison de l'avertissement")
@app_commands.default_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
    guild_id = str(interaction.guild.id)
    user_id = str(membre.id)
    
    if guild_id not in bot.warnings:
        bot.warnings[guild_id] = {}
    if user_id not in bot.warnings[guild_id]:
        bot.warnings[guild_id][user_id] = []
    
    warning = {
        "reason": raison,
        "moderator": str(interaction.user.id),
        "date": datetime.now(timezone.utc).isoformat()
    }
    bot.warnings[guild_id][user_id].append(warning)
    bot.save_data('warnings', bot.warnings)
    
    warn_count = len(bot.warnings[guild_id][user_id])
    
    embed = discord.Embed(
        title=f"{NEON.WARN} Avertissement",
        description=f"**Membre:** {membre.mention}\n**Raison:** {raison}\n**Avertissements:** {warn_count}",
        color=NEON.ORANGE
    )
    
    # Auto-sanctions
    sanction = None
    if warn_count == 3:
        try:
            await membre.timeout(datetime.now(timezone.utc) + timedelta(hours=1), reason="3 avertissements")
            sanction = "Mute 1h (3 warns)"
        except:
            pass
    elif warn_count == 5:
        try:
            await membre.timeout(datetime.now(timezone.utc) + timedelta(hours=24), reason="5 avertissements")
            sanction = "Mute 24h (5 warns)"
        except:
            pass
    elif warn_count >= 7:
        try:
            await membre.kick(reason="7+ avertissements")
            sanction = "Kick (7 warns)"
        except:
            pass
    
    if sanction:
        embed.add_field(name="Auto-Sanction", value=sanction, inline=False)
    
    await interaction.response.send_message(embed=embed)
    
    # DM l'utilisateur
    try:
        dm_embed = discord.Embed(
            title=f"{NEON.WARN} Tu as reçu un avertissement",
            description=f"**Serveur:** {interaction.guild.name}\n**Raison:** {raison}\n**Total:** {warn_count} avertissement(s)",
            color=NEON.ORANGE
        )
        await membre.send(embed=dm_embed)
    except:
        pass

@bot.tree.command(name="unwarn", description="Retirer un avertissement")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unwarn(interaction: discord.Interaction, membre: discord.Member):
    guild_id = str(interaction.guild.id)
    user_id = str(membre.id)
    
    if guild_id not in bot.warnings or user_id not in bot.warnings[guild_id] or not bot.warnings[guild_id][user_id]:
        return await interaction.response.send_message(f"{NEON.CHECK} {membre.mention} n'a pas d'avertissements.", ephemeral=True)
    
    bot.warnings[guild_id][user_id].pop()
    bot.save_data('warnings', bot.warnings)
    
    remaining = len(bot.warnings[guild_id][user_id])
    embed = create_neon_embed("Avertissement Retiré", f"{membre.mention} a maintenant {remaining} avertissement(s)", NEON.GREEN)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="warns", description="Voir les avertissements d'un membre")
@app_commands.describe(membre="Le membre")
async def warns(interaction: discord.Interaction, membre: discord.Member = None):
    membre = membre or interaction.user
    guild_id = str(interaction.guild.id)
    user_id = str(membre.id)
    
    warnings_list = bot.warnings.get(guild_id, {}).get(user_id, [])
    
    if not warnings_list:
        return await interaction.response.send_message(f"{NEON.CHECK} {membre.mention} n'a pas d'avertissements.", ephemeral=True)
    
    embed = discord.Embed(
        title=f"{NEON.WARN} Avertissements de {membre.display_name}",
        description=f"**Total:** {len(warnings_list)} avertissement(s)",
        color=NEON.ORANGE
    )
    
    for i, w in enumerate(warnings_list[-10:], 1):  # Last 10
        embed.add_field(
            name=f"#{i}",
            value=f"**Raison:** {w['reason']}\n**Date:** {w['date'][:10]}",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed)

# ==================== GIVEAWAY COMMANDS ====================
@bot.tree.command(name="giveaway", description="Créer un giveaway")
@app_commands.describe(
    titre="Titre du giveaway",
    prix="Le prix/récompense à gagner",
    duree_heures="Durée en heures",
    gagnants="Nombre de gagnants"
)
@app_commands.default_permissions(administrator=True)
async def giveaway_cmd(interaction: discord.Interaction, titre: str, prix: str, duree_heures: int, gagnants: int = 1):
    await interaction.response.defer()
    
    end_time = datetime.now(timezone.utc) + timedelta(hours=duree_heures)
    
    embed = discord.Embed(
        title=f"{NEON.GIVEAWAY} ═══ {titre.upper()} ═══ {NEON.GIVEAWAY}",
        description=f"```\n{NEON.NEON_LINE}\n```\n{NEON.GIFT} **Récompense:** {prix}\n```\n{NEON.NEON_LINE}\n```",
        color=NEON.GOLD
    )
    embed.add_field(name=f"{NEON.TROPHY} Gagnants", value=f"```{gagnants}```", inline=True)
    embed.add_field(name=f"{NEON.STAR} Participants", value=f"```0```", inline=True)
    embed.add_field(name=f"{NEON.CLOCK} Fin", value=f"", inline=True)
    embed.add_field(name=f"{NEON.SPARKLE} Comment participer?", value="Clique sur le bouton ci-dessous!", inline=False)
    embed.set_footer(text=f"Organisé par {interaction.user.display_name}")
    
    # Send message first to get ID
    msg = await interaction.channel.send(embed=embed)
    msg_id = str(msg.id)
    
    # Store giveaway data
    giveaway_data = {
        "title": titre,
        "prize": prix,
        "winners": gagnants,
        "end_time": end_time.isoformat(),
        "channel_id": str(interaction.channel.id),
        "guild_id": str(interaction.guild.id),
        "host_id": str(interaction.user.id),
        "participants": [],
        "ended": False
    }
    
    bot.giveaways[msg_id] = giveaway_data
    bot.save_data('giveaways', bot.giveaways)
    
    # Add button view
    view = GiveawayButtonView(msg_id)
    bot.add_view(view)
    await msg.edit(view=view)
    
    await interaction.followup.send(f"{NEON.CHECK} Giveaway créé!\n**Titre:** {titre}\n**Prix:** {prix}\n**Durée:** {duree_heures}h\n**Gagnants:** {gagnants}", ephemeral=True)

@bot.tree.command(name="reroll", description="Relancer un giveaway terminé")
@app_commands.describe(message_id="ID du message du giveaway")
@app_commands.default_permissions(administrator=True)
async def reroll(interaction: discord.Interaction, message_id: str):
    giveaway = bot.giveaways.get(message_id)
    
    if not giveaway:
        return await interaction.response.send_message(f"{NEON.CROSS} Giveaway non trouvé.", ephemeral=True)
    
    if not giveaway.get("ended", False):
        return await interaction.response.send_message(f"{NEON.CROSS} Ce giveaway n'est pas encore terminé.", ephemeral=True)
    
    participants = giveaway.get("participants", [])
    if not participants:
        return await interaction.response.send_message(f"{NEON.CROSS} Aucun participant.", ephemeral=True)
    
    winners_count = giveaway.get("winners", 1)
    winners_ids = random.sample(participants, min(winners_count, len(participants)))
    
    winners = []
    for wid in winners_ids:
        try:
            user = await bot.fetch_user(wid)
            winners.append(user)
        except:
            pass
    
    if winners:
        embed = discord.Embed(
            title=f"{NEON.GIVEAWAY} Reroll! {NEON.GIVEAWAY}",
            description=f"**Nouveau(x) gagnant(s):** {', '.join([w.mention for w in winners])}\n**Prix:** {giveaway.get('prize', 'Prix')}",
            color=NEON.GOLD
        )
        await interaction.response.send_message(content=" ".join([w.mention for w in winners]), embed=embed)
    else:
        await interaction.response.send_message(f"{NEON.CROSS} Erreur reroll.", ephemeral=True)

# ==================== SLOWMODE GLOBAL ====================
@bot.tree.command(name="slowmode", description="Mode lent sur TOUS les salons")
@app_commands.describe(secondes="Délai en secondes (0 = désactiver)")
@app_commands.default_permissions(administrator=True)
async def slowmode(interaction: discord.Interaction, secondes: int):
    await interaction.response.defer()
    
    count = 0
    errors = 0
    
    for channel in interaction.guild.text_channels:
        try:
            await channel.edit(slowmode_delay=secondes)
            count += 1
            await asyncio.sleep(0.3)  # Rate limit protection
        except:
            errors += 1
    
    if secondes > 0:
        embed = discord.Embed(
            title=f"⏱️ Mode Lent Activé",
            description=f"**Délai:** {secondes} secondes\n**Salons modifiés:** {count}\n**Erreurs:** {errors}",
            color=NEON.BLUE
        )
    else:
        embed = discord.Embed(
            title=f"🚀 Mode Lent Désactivé",
            description=f"**Salons modifiés:** {count}\n**Erreurs:** {errors}",
            color=NEON.PINK
        )
    
    await interaction.followup.send(embed=embed)

# ==================== OTHER COMMANDS ====================

@bot.tree.command(name="rename", description="Renommer un membre")
@app_commands.describe(membre="Le membre", pseudo="Nouveau pseudo")
@app_commands.default_permissions(manage_nicknames=True)
async def rename(interaction: discord.Interaction, membre: discord.Member, pseudo: str):
    await membre.edit(nick=pseudo)
    await interaction.response.send_message(embed=create_neon_embed("Renommé", f"{membre.mention} → **{pseudo}**"))

@bot.tree.command(name="ban", description="Bannir")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.ban(reason=raison)
    await interaction.response.send_message(embed=discord.Embed(title=f"{NEON.BAN} Banni", description=f"{membre} - {raison}", color=NEON.RED))

@bot.tree.command(name="unban", description="Débannir")
@app_commands.describe(user_id="ID")
@app_commands.default_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(embed=create_neon_embed("Débanni", f"{user}"))
    except:
        await interaction.response.send_message(f"{NEON.CROSS} Non trouvé", ephemeral=True)

@bot.tree.command(name="kick", description="Expulser")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.kick(reason=raison)
    await interaction.response.send_message(embed=create_neon_embed("Expulsé", f"{membre} - {raison}", NEON.PURPLE))

@bot.tree.command(name="mute", description="Mute")
@app_commands.describe(membre="Le membre", duree="Minutes")
@app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, membre: discord.Member, duree: int = 10):
    await membre.timeout(datetime.now(timezone.utc) + timedelta(minutes=duree))
    await interaction.response.send_message(embed=create_neon_embed("Muté", f"{membre.mention} - {duree}min", NEON.BLUE))

@bot.tree.command(name="unmute", description="Unmute")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, membre: discord.Member):
    await membre.timeout(None)
    await interaction.response.send_message(embed=create_neon_embed("Unmute", f"{membre.mention}"))

@bot.tree.command(name="creersalon", description="Créer salon texte")
@app_commands.describe(nom="Nom", categorie="Catégorie")
@app_commands.default_permissions(manage_channels=True)
async def creersalon(interaction: discord.Interaction, nom: str, categorie: discord.CategoryChannel = None):
    channel = await interaction.guild.create_text_channel(nom, category=categorie)
    await interaction.response.send_message(embed=create_neon_embed("Salon Créé", f"{channel.mention}"))

@bot.tree.command(name="creervoice", description="Créer salon vocal")
@app_commands.describe(nom="Nom", categorie="Catégorie")
@app_commands.default_permissions(manage_channels=True)
async def creervoice(interaction: discord.Interaction, nom: str, categorie: discord.CategoryChannel = None):
    channel = await interaction.guild.create_voice_channel(nom, category=categorie)
    await interaction.response.send_message(embed=create_neon_embed("Vocal Créé", f"🔊 {channel.name}"))

@bot.tree.command(name="supprimersalon", description="Supprimer salon")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(manage_channels=True)
async def supprimersalon(interaction: discord.Interaction, salon: discord.TextChannel):
    name = salon.name
    await salon.delete()
    await interaction.response.send_message(embed=create_neon_embed("Supprimé", f"`{name}`", NEON.BLUE))

@bot.tree.command(name="lock", description="Verrouiller")
@app_commands.describe(salon="Salon", bloquer_lecture="Bloquer lecture aussi")
@app_commands.default_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction, salon: discord.TextChannel = None, bloquer_lecture: bool = False):
    target = salon or interaction.channel
    overwrites = target.overwrites_for(interaction.guild.default_role)
    overwrites.send_messages = False
    if bloquer_lecture:
        overwrites.view_channel = False
    await target.set_permissions(interaction.guild.default_role, overwrite=overwrites)
    await interaction.response.send_message(embed=create_neon_embed("Verrouillé", f"🔒 {target.mention}", NEON.BLUE))

@bot.tree.command(name="unlock", description="Déverrouiller")
@app_commands.describe(salon="Salon")
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction, salon: discord.TextChannel = None):
    target = salon or interaction.channel
    await target.set_permissions(interaction.guild.default_role, send_messages=True, view_channel=True)
    await interaction.response.send_message(embed=create_neon_embed("Déverrouillé", f"🔓 {target.mention}"))

@bot.tree.command(name="purge", description="Supprimer messages")
@app_commands.describe(nombre="Nombre")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, nombre: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=nombre)
    await interaction.followup.send(f"{NEON.CHECK} {len(deleted)} supprimés")

@bot.tree.command(name="creerole", description="Créer rôle")
@app_commands.describe(nom="Nom", couleur="Couleur hex")
@app_commands.default_permissions(manage_roles=True)
async def creerole(interaction: discord.Interaction, nom: str, couleur: str = "#ff1493"):
    role = await interaction.guild.create_role(name=nom, color=discord.Color(int(couleur.replace("#", ""), 16)))
    await interaction.response.send_message(embed=create_neon_embed("Rôle Créé", f"{role.mention}"))

@bot.tree.command(name="addrole", description="Ajouter rôle")
@app_commands.describe(membre="Membre", role="Rôle")
@app_commands.default_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.add_roles(role)
    await interaction.response.send_message(embed=create_neon_embed("Rôle Ajouté", f"{role.mention} → {membre.mention}"))

@bot.tree.command(name="removerole", description="Retirer rôle")
@app_commands.describe(membre="Membre", role="Rôle")
@app_commands.default_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.remove_roles(role)
    await interaction.response.send_message(embed=create_neon_embed("Rôle Retiré", f"{role.mention} de {membre.mention}", NEON.BLUE))

@bot.tree.command(name="roleall", description="Rôle à tous")
@app_commands.describe(role="Rôle")
@app_commands.default_permissions(administrator=True)
async def roleall(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer()
    count = 0
    for m in interaction.guild.members:
        if not m.bot and role not in m.roles:
            try:
                await m.add_roles(role)
                count += 1
                await asyncio.sleep(0.5)
            except:
                pass
    await interaction.followup.send(embed=create_neon_embed("Rôle Ajouté", f"{role.mention} → {count} membres"))

@bot.tree.command(name="autorole", description="Auto-rôle nouveaux membres")
@app_commands.describe(role="Rôle")
@app_commands.default_permissions(administrator=True)
async def autorole(interaction: discord.Interaction, role: discord.Role):
    bot.auto_roles[str(interaction.guild.id)] = role.id
    bot.save_data('auto_roles', bot.auto_roles)
    await interaction.response.send_message(embed=create_neon_embed("Auto-Rôle", f"{role.mention}"))

@bot.tree.command(name="rolemenu", description="Menu sélection rôles")
@app_commands.describe(titre="Titre", roles="Rôles (@r1, @r2)")
@app_commands.default_permissions(administrator=True)
async def rolemenu(interaction: discord.Interaction, titre: str, roles: str):
    role_ids = re.findall(r'<@&(\d+)>', roles)
    role_objs = [interaction.guild.get_role(int(rid)) for rid in role_ids if interaction.guild.get_role(int(rid))]
    if not role_objs:
        return await interaction.response.send_message(f"{NEON.CROSS} Utilise des mentions", ephemeral=True)
    
    embed = discord.Embed(title=f"{NEON.ROLE} {titre}", description="\n".join([f"• {r.mention}" for r in role_objs]), color=NEON.PINK)
    await interaction.channel.send(embed=embed, view=RoleSelectView(role_objs))
    await interaction.response.send_message(f"{NEON.CHECK} Créé!", ephemeral=True)

@bot.tree.command(name="panel", description="Panel tickets")
@app_commands.describe(titre="Titre", description="Description", bouton="Texte bouton", role_support="Rôle support")
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction, titre: str = "Support", description: str = "Ouvre un ticket!", bouton: str = "✨ Ouvrir ✨", role_support: discord.Role = None):
    guild_id = str(interaction.guild.id)
    bot.ticket_configs[guild_id] = {"support_role": role_support.id if role_support else None}
    bot.save_data('ticket_configs', bot.ticket_configs)
    
    embed = discord.Embed(title=f"{NEON.TICKET} {titre}", description=description, color=NEON.PINK)
    view = discord.ui.View(timeout=None)
    view.add_item(DynamicTicketButton(bouton))
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"{NEON.CHECK} Panel créé!", ephemeral=True)

@bot.tree.command(name="reglement", description="Règlement")
@app_commands.describe(avec_bouton="Bouton acceptation", role="Rôle à donner")
@app_commands.default_permissions(administrator=True)
async def reglement(interaction: discord.Interaction, avec_bouton: bool = True, role: discord.Role = None):
    if role:
        bot.verification_roles[str(interaction.guild.id)] = role.id
        bot.save_data('verification_roles', bot.verification_roles)
    
    embed = discord.Embed(title=f"{NEON.SPARKLE} RÈGLEMENT {NEON.SPARKLE}", color=NEON.PINK)
    for t, c in DEFAULT_RULES:
        embed.add_field(name=t, value=c, inline=False)
    
    if avec_bouton:
        await interaction.channel.send(embed=embed, view=RulesAcceptButton())
    else:
        await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"{NEON.CHECK} Créé!", ephemeral=True)

@bot.tree.command(name="verification", description="Vérification")
@app_commands.describe(role="Rôle", titre="Titre", description="Description")
@app_commands.default_permissions(administrator=True)
async def verification(interaction: discord.Interaction, role: discord.Role = None, titre: str = "Vérification", description: str = "Clique pour te vérifier!"):
    guild_id = str(interaction.guild.id)
    
    if not role:
        role = discord.utils.get(interaction.guild.roles, name="✅ Vérifié")
        if not role:
            role = await interaction.guild.create_role(name="✅ Vérifié", color=discord.Color.green())
    
    bot.verification_roles[guild_id] = role.id
    bot.save_data('verification_roles', bot.verification_roles)
    
    embed = discord.Embed(title=f"{NEON.SHIELD} {titre}", description=f"{description}\n\n**Rôle:** {role.mention}", color=NEON.BLUE)
    await interaction.channel.send(embed=embed, view=VerifyButtonDynamic())
    await interaction.response.send_message(f"{NEON.CHECK} Configuré! Rôle: {role.mention}", ephemeral=True)

@bot.tree.command(name="welcome", description="Messages bienvenue/départ")
@app_commands.describe(salon="Salon")
@app_commands.default_permissions(administrator=True)
async def welcome(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.welcome_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('welcome_channels', bot.welcome_channels)
    await interaction.response.send_message(embed=create_neon_embed("Bienvenue/Départ", f"{salon.mention}"))

@bot.tree.command(name="setup", description="Setup serveur complet")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer()
    g = interaction.guild
    created = {"roles": 0, "text": 0, "voice": 0}
    
    roles = [("━━ STAFF ━━", 0x2f3136), (f"{NEON.CROWN} Fondateur", NEON.PINK), ("⚔️ Admin", 0xe74c3c), (f"{NEON.SHIELD} Modérateur", NEON.BLUE), ("━━ GRADES ━━", 0x2f3136), ("💎 VIP", 0xf1c40f), ("🔥 Actif", 0xe74c3c), ("━━ MEMBRES ━━", 0x2f3136), (f"{NEON.CHECK} Vérifié", 0x2ecc71), ("🎮 Membre", 0x95a5a6)]
    
    for name, color in roles:
        if not discord.utils.get(g.roles, name=name):
            try:
                await g.create_role(name=name, color=discord.Color(color))
                created["roles"] += 1
                await asyncio.sleep(0.3)
            except:
                pass
    
    structure = {
        "📌 IMPORTANT": (["📜・règles", "📢・annonces", "📰・news"], []),
        "👋 ACCUEIL": (["👋・bienvenue", "✅・vérification", "🎫・rôles"], []),
        "💬 DISCUSSION": (["💬・général", "🖼️・médias", "🤖・bot"], ["🔊 Général", "🔊 Chill"]),
        "🎮 GAMING": (["🎮・gaming"], ["🎮 Gaming 1", "🎮 Gaming 2"]),
        "🎵 MUSIQUE": (["🎵・playlist"], ["🎵 Musique"]),
        "📩 SUPPORT": (["❓・aide", "💡・suggestions"], ["🆘 Support"]),
        "🔒 STAFF": (["📋・staff", "📊・logs"], ["🔒 Staff"]),
        "🎫 Tickets": ([], []),
        "📝 Candidatures": (["📝・candidatures"], [])
    }
    
    for cat_name, (texts, voices) in structure.items():
        cat = discord.utils.get(g.categories, name=cat_name)
        if not cat:
            try:
                overwrites = {}
                if "STAFF" in cat_name:
                    overwrites = {g.default_role: discord.PermissionOverwrite(view_channel=False)}
                cat = await g.create_category(cat_name, overwrites=overwrites)
                await asyncio.sleep(0.3)
            except:
                continue
        
        for ch in texts:
            if not discord.utils.get(g.text_channels, name=ch):
                try:
                    await g.create_text_channel(ch, category=cat)
                    created["text"] += 1
                    await asyncio.sleep(0.3)
                except:
                    pass
        
        for vc in voices:
            if not discord.utils.get(g.voice_channels, name=vc):
                try:
                    await g.create_voice_channel(vc, category=cat)
                    created["voice"] += 1
                    await asyncio.sleep(0.3)
                except:
                    pass
    
    # Save logs channel
    logs_ch = discord.utils.get(g.text_channels, name="📊・logs")
    if logs_ch:
        bot.logs_channels[str(g.id)] = logs_ch.id
        bot.save_data('logs_channels', bot.logs_channels)
    
    embed = discord.Embed(title=f"{NEON.CHECK} Setup Terminé!", color=NEON.PINK)
    embed.add_field(name="Rôles", value=f"```{created['roles']}```", inline=True)
    embed.add_field(name="Texte", value=f"```{created['text']}```", inline=True)
    embed.add_field(name="Vocal", value=f"```{created['voice']}```", inline=True)
    embed.add_field(name="Prochaines étapes", value="```/panel /verification /reglement /antispam```", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="backup", description="Sauvegarder")
@app_commands.describe(nom="Nom")
@app_commands.default_permissions(administrator=True)
async def backup(interaction: discord.Interaction, nom: str = None):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    backup_name = nom or f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    data = {
        "roles": [{"name": r.name, "color": r.color.value} for r in guild.roles if r.name != "@everyone" and not r.managed],
        "categories": [{"name": c.name} for c in guild.categories],
        "text": [{"name": c.name, "category": c.category.name if c.category else None} for c in guild.text_channels],
        "voice": [{"name": c.name, "category": c.category.name if c.category else None} for c in guild.voice_channels]
    }
    
    guild_id = str(guild.id)
    if guild_id not in bot.backups:
        bot.backups[guild_id] = {}
    bot.backups[guild_id][backup_name] = data
    bot.save_data('backups', bot.backups)
    
    await interaction.followup.send(embed=discord.Embed(title="💾 Sauvegarde", description=f"✅ Créée!\n**Rôles:** {len(data['roles'])}\n**Salons:** {len(data['text']) + len(data['voice'])}", color=NEON.PINK), ephemeral=True)

@bot.tree.command(name="restore", description="Restaurer")
@app_commands.describe(nom="Nom")
@app_commands.default_permissions(administrator=True)
async def restore(interaction: discord.Interaction, nom: str):
    await interaction.response.defer()
    guild_id = str(interaction.guild.id)
    
    if guild_id not in bot.backups or nom not in bot.backups[guild_id]:
        return await interaction.followup.send(f"{NEON.CROSS} Non trouvée")
    
    data = bot.backups[guild_id][nom]
    restored = {"roles": 0, "channels": 0}
    
    for r in data.get("roles", []):
        if not discord.utils.get(interaction.guild.roles, name=r["name"]):
            try:
                await interaction.guild.create_role(name=r["name"], color=discord.Color(r.get("color", 0)))
                restored["roles"] += 1
                await asyncio.sleep(0.3)
            except:
                pass
    
    for c in data.get("categories", []):
        if not discord.utils.get(interaction.guild.categories, name=c["name"]):
            try:
                await interaction.guild.create_category(c["name"])
                await asyncio.sleep(0.3)
            except:
                pass
    
    for ch in data.get("text", []):
        if not discord.utils.get(interaction.guild.text_channels, name=ch["name"]):
            try:
                cat = discord.utils.get(interaction.guild.categories, name=ch.get("category"))
                await interaction.guild.create_text_channel(ch["name"], category=cat)
                restored["channels"] += 1
                await asyncio.sleep(0.3)
            except:
                pass
    
    await interaction.followup.send(embed=create_neon_embed("Restauré", f"Rôles: {restored['roles']}\nSalons: {restored['channels']}"))

@bot.tree.command(name="antiraid", description="Anti-raid")
@app_commands.describe(activer="Activer", seuil="Joins/10s", action="kick/ban")
@app_commands.default_permissions(administrator=True)
async def antiraid(interaction: discord.Interaction, activer: bool = True, seuil: int = 5, action: str = "kick"):
    bot.raid_protection[str(interaction.guild.id)] = {"enabled": activer, "threshold": seuil, "action": action}
    bot.save_data('raid_protection', bot.raid_protection)
    await interaction.response.send_message(embed=discord.Embed(title=f"{NEON.SHIELD} Anti-Raid", description=f"**Status:** {'✅' if activer else '❌'}\n**Seuil:** {seuil}/10s\n**Action:** {action}", color=NEON.PINK))

@bot.tree.command(name="antispam", description="Anti-spam")
@app_commands.describe(activer="Activer", messages="Max messages", temps="En secondes", mentions="Max mentions", action="mute/kick/ban", duree_mute="Minutes")
@app_commands.default_permissions(administrator=True)
async def antispam(interaction: discord.Interaction, activer: bool = True, messages: int = 5, temps: int = 5, mentions: int = 5, action: str = "mute", duree_mute: int = 5):
    bot.anti_spam_config[str(interaction.guild.id)] = {"enabled": activer, "msg_limit": messages, "msg_time": temps, "mention_limit": mentions, "action": action, "mute_duration": duree_mute}
    bot.save_data('anti_spam_config', bot.anti_spam_config)
    await interaction.response.send_message(embed=discord.Embed(title=f"{NEON.SPAM} Anti-Spam", description=f"**Status:** {'✅' if activer else '❌'}\n**Messages:** {messages}/{temps}s\n**Mentions:** {mentions}\n**Action:** {action}", color=NEON.PINK))

@bot.tree.command(name="tempvoice", description="Vocaux temporaires")
@app_commands.describe(salon="Salon déclencheur")
@app_commands.default_permissions(administrator=True)
async def tempvoice(interaction: discord.Interaction, salon: discord.VoiceChannel):
    bot.temp_voice_channels[str(interaction.guild.id)] = salon.id
    bot.save_data('temp_voice_channels', bot.temp_voice_channels)
    await interaction.response.send_message(embed=create_neon_embed("Vocaux Temp", f"Rejoins {salon.name}!"))

@bot.tree.command(name="image", description="Générer image IA")
@app_commands.describe(prompt="Description")
async def image(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        img = await generate_ai_image(prompt)
        file = discord.File(fp=io.BytesIO(img), filename="image.png")
        embed = discord.Embed(title=f"{NEON.IMAGE} Image", description=f"```{prompt[:200]}```", color=NEON.PINK)
        embed.set_image(url="attachment://image.png")
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        await interaction.followup.send(f"{NEON.CROSS} Erreur: {str(e)[:300]}")

@bot.tree.command(name="annonceia", description="Annonce IA")
@app_commands.describe(sujet="Sujet", style="Style")
async def annonceia(interaction: discord.Interaction, sujet: str, style: str = "hype"):
    await interaction.response.defer()
    try:
        text = await generate_ai_text(f"Annonce Discord pour: {sujet}. Style: {style}. Max 400 chars. Emojis.", "Community manager expert")
        embed = discord.Embed(title="📢 ANNONCE", description=text, color=NEON.PINK)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"{NEON.CROSS} Erreur: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="tts", description="Audio TTS")
@app_commands.describe(texte="Texte", voix="Voix")
async def tts(interaction: discord.Interaction, texte: str, voix: str = "nova"):
    await interaction.response.defer()
    try:
        audio = await generate_tts_audio(texte[:500], voix)
        file = discord.File(fp=io.BytesIO(audio), filename="tts.mp3")
        await interaction.followup.send(f"{NEON.VOICE} Audio:", file=file)
    except Exception as e:
        await interaction.followup.send(f"{NEON.CROSS} Erreur: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="parler", description="Bot parle en vocal")
@app_commands.describe(texte="Texte", voix="Voix")
async def parler(interaction: discord.Interaction, texte: str, voix: str = "nova"):
    if not interaction.user.voice:
        return await interaction.response.send_message(f"{NEON.CROSS} Rejoins un vocal!", ephemeral=True)
    
    await interaction.response.defer()
    try:
        audio = await generate_tts_audio(texte[:500], voix)
        path = DATA_DIR / f"tts_{interaction.id}.mp3"
        with open(path, 'wb') as f:
            f.write(audio)
        
        vc = await interaction.user.voice.channel.connect()
        vc.play(discord.FFmpegPCMAudio(str(path)), after=lambda e: asyncio.run_coroutine_threadsafe(vc.disconnect(), bot.loop))
        await interaction.followup.send(embed=create_neon_embed("Lecture", f"```{texte[:100]}```"))
        
        while vc.is_playing():
            await asyncio.sleep(1)
        try:
            path.unlink()
        except:
            pass
    except Exception as e:
        await interaction.followup.send(f"{NEON.CROSS} Erreur: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="ping", description="Latence")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title=f"{NEON.LIGHTNING} Pong!", description=f"```{round(bot.latency * 1000)}ms```", color=NEON.PINK))

# ==================== RUN ====================
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.environ.get('DISCORD_BOT_TOKEN')
    if token:
        logger.info("⚡ Aegis V3 démarre...")
        bot.run(token)
    else:
        logger.error(" DISCORD_BOT_TOKEN manquant!")
