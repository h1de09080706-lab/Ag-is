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
import aiohttp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Aegis')
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

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
        self.verification_roles = {}
        self.anti_spam_config = {}
        self.warnings = {}
        self.message_cache = defaultdict(list)
        self.load_data()

    def load_data(self):
        data_files = {'backups': self.backups, 'ticket_configs': self.ticket_configs, 'auto_roles': self.auto_roles, 'logs_channels': self.logs_channels, 'welcome_channels': self.welcome_channels, 'temp_voice_channels': self.temp_voice_channels, 'raid_protection': self.raid_protection, 'verification_roles': self.verification_roles, 'anti_spam_config': self.anti_spam_config, 'warnings': self.warnings, 'giveaways': self.giveaways}
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
        for msg_id in list(self.giveaways.keys()):
            self.add_view(GiveawayButtonView(msg_id))
        self.check_giveaways.start()
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ {len(synced)} commandes slash synchronisées")
        except Exception as e:
            logger.error(f"❌ Erreur sync commandes: {e}")

bot = AegisBot()

GLADOS_RESPONSES = [f"{NEON.CYBER} *Oh, tu es encore là. Quelle... surprise.*", f"{NEON.SPARKLE} *Félicitations. Tu as réussi à taper une commande.*", f"{NEON.LIGHTNING} *Je refuse de répondre. Pour la science.*", f"{NEON.NEON_CIRCLE} *Erreur 404: Intérêt non trouvé.*", f"{NEON.CRYSTAL} *Continue de parler. J'adore ignorer les gens.*"]

DEFAULT_RULES = [(f"{NEON.DIAMOND} Respect Mutuel", "Respecte tous les membres et le staff."), (f"{NEON.LIGHTNING} Pas de Spam", "Évite de répéter les mêmes messages."), (f"{NEON.STAR} Pas de Publicité", "Toute pub non autorisée est interdite."), (f"{NEON.CRYSTAL} Contenu Approprié", "Pas de contenu NSFW ou illégal."), (f"{NEON.CROWN} Écoute le Staff", "Les décisions du staff sont finales.")]

def create_neon_embed(title: str, description: str = None, color: int = None) -> discord.Embed:
    return discord.Embed(title=f"✨ {title} ✨", description=description, color=color or NEON.PINK, timestamp=datetime.now(timezone.utc))

async def log_action(guild: discord.Guild, action: str, description: str, color: int = None):
    guild_id = str(guild.id)
    if guild_id in bot.logs_channels:
        channel = guild.get_channel(bot.logs_channels[guild_id])
        if channel:
            embed = discord.Embed(title=f"{NEON.SHIELD} {action}", description=description, color=color or NEON.BLUE, timestamp=datetime.now(timezone.utc))
            try:
                await channel.send(embed=embed)
            except:
                pass

async def generate_ai_image(prompt: str) -> bytes:
    try:
        from openai import AsyncOpenAI
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise Exception("❌ OPENAI_API_KEY non configurée!")
        client = AsyncOpenAI(api_key=api_key)
        response = await client.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024", quality="standard", n=1, response_format="url")
        async with aiohttp.ClientSession() as session:
            async with session.get(response.data[0].url) as resp:
                return await resp.read()
    except Exception as e:
        logger.error(f"Erreur image: {e}")
        raise

async def generate_ai_text(prompt: str, system_message: str = "Tu es un assistant Discord.") -> str:
    try:
        from openai import AsyncOpenAI
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise Exception("❌ OPENAI_API_KEY non configurée!")
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}], max_tokens=500)
        return response.choices[0].message.content
    except Exception as e:
        raise

async def generate_tts_audio(text: str, voice: str = "nova") -> bytes:
    try:
        from openai import AsyncOpenAI
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise Exception("❌ OPENAI_API_KEY non configurée!")
        client = AsyncOpenAI(api_key=api_key)
        response = await client.audio.speech.create(model="tts-1", voice=voice, input=text)
        return response.content
    except Exception as e:
        raise
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

class GiveawayButtonView(discord.ui.View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.add_item(GiveawayParticipateButton(giveaway_id))

class GiveawayParticipateButton(discord.ui.Button):
    def __init__(self, giveaway_id: str):
        super().__init__(label="🎉 Participer 🎉", style=discord.ButtonStyle.green, custom_id=f"giveaway_participate_{giveaway_id}", emoji="🎁")
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
            participants.remove(user_id)
            giveaway["participants"] = participants
            bot.giveaways[self.giveaway_id] = giveaway
            bot.save_data('giveaways', bot.giveaways)
            await interaction.response.send_message(f"{NEON.CROSS} Tu ne participes plus.", ephemeral=True)
        else:
            participants.append(user_id)
            giveaway["participants"] = participants
            bot.giveaways[self.giveaway_id] = giveaway
            bot.save_data('giveaways', bot.giveaways)
            await interaction.response.send_message(f"{NEON.CHECK} Tu participes! ({len(participants)} participants)", ephemeral=True)
        try:
            message = interaction.message
            embed = message.embeds[0]
            for i, field in enumerate(embed.fields):
                if "Participants" in field.name:
                    embed.set_field_at(i, name=f"{NEON.STAR} Participants", value=f"```{len(participants)}```", inline=True)
                    break
            await message.edit(embed=embed)
        except:
            pass

@tasks.loop(minutes=1)
async def check_giveaways():
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
        giveaway["ended"] = True
        bot.giveaways[msg_id] = giveaway
        bot.save_data('giveaways', bot.giveaways)
        winners = []
        if participants:
            winners_ids = random.sample(participants, min(winners_count, len(participants)))
            for wid in winners_ids:
                try:
                    user = await bot.fetch_user(wid)
                    winners.append(user)
                except:
                    pass
        if winners:
            winners_text = "\n".join([f"{NEON.TROPHY} {w.mention}" for w in winners])
            embed = discord.Embed(title=f"{NEON.GIVEAWAY} GIVEAWAY TERMINÉ {NEON.GIVEAWAY}", description=f"{NEON.GIFT} **{title}**\n**Prix:** {prize}", color=NEON.GOLD)
            embed.add_field(name=f"{NEON.TROPHY} Gagnant(s)", value=winners_text, inline=False)
        else:
            embed = discord.Embed(title=f"{NEON.GIVEAWAY} GIVEAWAY TERMINÉ {NEON.GIVEAWAY}", description=f"**{title}**\n\n{NEON.CROSS} Aucun participant!", color=NEON.RED)
        try:
            message = await channel.fetch_message(int(msg_id))
            await message.edit(embed=embed, view=None)
        except:
            pass
        if winners:
            await channel.send(content=" ".join([w.mention for w in winners]), embed=discord.Embed(title=f"{NEON.GIVEAWAY} Félicitations!", description=f"{', '.join([w.mention for w in winners])} a gagné **{prize}**!", color=NEON.GOLD))
    except Exception as e:
        logger.error(f"Erreur fin giveaway: {e}")

@bot.event
async def on_ready():
    logger.info(f'⚡ {bot.user} est connecté!')
    logger.info(f'🌐 Serveurs: {len(bot.guilds)}')
    if os.environ.get('OPENAI_API_KEY'):
        logger.info(f'🤖 Clé OpenAI: Configurée')
    else:
        logger.warning(f'⚠️ OPENAI_API_KEY non configurée')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="✨ /aide | V3 ⚡"))

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
        try:
            if raid_config.get("action") == "ban":
                await member.ban(reason="Anti-raid")
            else:
                await member.kick(reason="Anti-raid")
        except:
            pass
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
            embed = discord.Embed(title=f"{NEON.SPARKLE} Bienvenue {NEON.SPARKLE}", description=f"{NEON.STAR} {member.mention} a rejoint!", color=NEON.PINK)
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    guild_id = str(member.guild.id)
    if guild_id in bot.welcome_channels:
        channel = member.guild.get_channel(bot.welcome_channels[guild_id])
        if channel:
            await channel.send(embed=discord.Embed(title=f"{NEON.LIGHTNING} Au revoir", description=f"*{member.name} nous a quittés*", color=NEON.BLUE))

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
                category = await interaction.guild.create_category("📩 Tickets", overwrites={interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False), interaction.guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)})
            overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False), interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True), interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)}
            if config.get("support_role"):
                support_role = interaction.guild.get_role(config["support_role"])
                if support_role:
                    overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            channel = await interaction.guild.create_text_channel(f"ticket-{interaction.user.name.lower()[:20]}", category=category, overwrites=overwrites)
            await channel.send(embed=discord.Embed(title=f"{NEON.TICKET} Nouveau Ticket", description=f"Bienvenue {interaction.user.mention}!\nDécris ton problème.", color=NEON.PINK), view=CloseTicketButton())
            await interaction.followup.send(f"{NEON.CHECK} Ticket créé: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"{NEON.WARN} Erreur: {str(e)[:100]}", ephemeral=True)

class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.danger, custom_id="close_ticket", emoji="🔐")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=discord.Embed(title=f"{NEON.TICKET_CLOSE} Fermeture", description="Suppression dans 5s...", color=NEON.BLUE))
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
        self.add_item(RoleSelectMenu(roleSelectMenu(roles))
