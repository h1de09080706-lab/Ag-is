import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import logging
import asyncio
import random
import re
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Aegis')

# ==================== THEME ====================
class T:
    PINK=0xFF1493; GREEN=0x57F287; RED=0xED4245; ORANGE=0xFF6600
    GOLD=0xFFD700; BLURPLE=0x5865F2; PURPLE=0x9B59B6; TEAL=0x1ABC9C

    SPARKLE="✨"; LIGHTNING="⚡"; STAR="🌟"; DIAMOND="💎"
    CROWN="👑"; CRYSTAL="💠"; TICKET="🎫"; LOCK="🔐"
    BAN="⛔"; KICK="👢"; WARN="⚠️"; SHIELD="🛡️"; CHECK="✅"; CROSS="❌"
    GEAR="⚙️"; CHANNEL="💬"; VOICE="🔊"; ROLE="🎭"; SPAM="🚫"
    GIVEAWAY="🎉"; GIFT="🎁"; TROPHY="🏆"; CLOCK="⏰"; WAVE="👋"
    DOOR="🚪"; CHART="📊"; XP="⭐"; INFO="ℹ️"; POLL="📊"
    ARROW="➜"; MUTE="🔇"; MUSIC="🎵"; PAUSE="⏸️"; SKIP="⏭️"
    STOP="⏹️"; AI="🤖"; MEGA="📣"; PIN="📌"; FIRE="🔥"; COIN="🪙"
    LINE="━━━━━━━━━━━━━━━━━━━━━━━━"

def mk_embed(title, desc=None, color=None, footer=None):
    e = discord.Embed(title=title, description=desc, color=color or T.PINK,
                      timestamp=datetime.now(timezone.utc))
    if footer: e.set_footer(text=footer)
    return e

def ok(t, d=None):  return mk_embed(f"{T.CHECK}  {t}", d, T.GREEN)
def err(t, d=None): return mk_embed(f"{T.CROSS}  {t}", d, T.RED)
def inf(t, d=None): return mk_embed(f"{T.INFO}  {t}",  d, T.BLURPLE)

# ==================== BOT ====================
intents = discord.Intents.all()

class AegisBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=['aegis ', 'Aegis '], intents=intents, help_command=None)
        self.giveaways:        Dict = {}
        self.temp_voices:      Dict = {}
        self.auto_roles:       Dict = {}
        self.logs_channels:    Dict = {}
        self.arrivee_channels: Dict = {}
        self.depart_channels:  Dict = {}
        self.anti_raid_cache:  Dict = {}
        self.backups:          Dict = {}
        self.ticket_configs:   Dict = {}
        self.raid_protection:  Dict = {}
        self.verif_roles:      Dict = {}
        self.antispam_config:  Dict = {}
        self.warnings:         Dict = {}
        self.msg_cache              = defaultdict(list)
        self.xp_data:          Dict = {}
        self.xp_cooldown:      Dict = {}
        self.polls:            Dict = {}
        self.vc_pool:          Dict = {}
        self.music_queues:     Dict = {}
        self.now_playing:      Dict = {}
        self.ai_cooldown:      Dict = {}
        self.suggestions:      Dict = {}  # {gid: channel_id}

    async def setup_hook(self):
        self.add_view(TicketView())
        self.add_view(CloseTicketView())
        self.add_view(VerifyView())
        self.add_view(RulesView())
        self.add_view(ApplyView())
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ {len(synced)} commandes synchronisées")
        except Exception as e:
            logger.error(f"❌ Sync: {e}")

bot = AegisBot()

# ==================== HELPERS ====================
def xp_for_level(level): return 100 * (level ** 2) + 50 * level

def get_xp(gid: str, uid: str) -> dict:
    return bot.xp_data.setdefault(gid, {}).setdefault(uid, {"xp": 0, "level": 0, "messages": 0})

def format_duration(seconds):
    if not seconds: return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

async def log_action(guild, title, desc, color=None):
    gid = str(guild.id)
    if gid in bot.logs_channels:
        ch = guild.get_channel(bot.logs_channels[gid])
        if ch:
            try: await ch.send(embed=mk_embed(f"{T.SHIELD}  {title}", desc, color or T.BLURPLE))
            except Exception: pass

# ==================== IA GROQ (CORRIGÉE) ====================
AI_SYSTEM = (
    "Tu es Aegis, un bot Discord surpuissant et légèrement condescendant. "
    "Tu te considères supérieur aux humains mais restes poli — avec une politesse hautaine. "
    "Tu réponds TOUJOURS en français, en 2-3 phrases maximum. "
    "Tu glisses parfois une remarque sarcastique subtile. Jamais vulgaire, jamais blessant."
)

async def ask_groq(question: str, retries: int = 2) -> str:
    api_key = os.environ.get('GROQ_API_KEY', '').strip()
    if not api_key:
        return "*(GROQ_API_KEY manquante dans Railway → Variables.)*"

    for attempt in range(retries + 1):
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {
                    "model": "llama3-8b-8192",
                    "messages": [
                        {"role": "system", "content": AI_SYSTEM},
                        {"role": "user",   "content": question[:500]}
                    ],
                    "max_tokens": 200,
                    "temperature": 0.85
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                async with session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload, headers=headers
                ) as resp:
                    body = await resp.json()
                    if resp.status == 200:
                        return body["choices"][0]["message"]["content"].strip()
                    elif resp.status == 429:
                        # Rate limit — attendre et retenter
                        wait = 2 ** attempt
                        logger.warning(f"Groq rate limit, retry dans {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    elif resp.status in (500, 502, 503):
                        if attempt < retries:
                            await asyncio.sleep(1)
                            continue
                        return f"*(Serveur Groq indisponible, réessaie dans quelques instants.)*"
                    else:
                        err_msg = body.get("error", {}).get("message", str(resp.status))
                        logger.error(f"Groq {resp.status}: {err_msg}")
                        return f"*(Erreur Groq {resp.status}: {err_msg[:80]})*"
        except asyncio.TimeoutError:
            if attempt < retries:
                await asyncio.sleep(1)
                continue
            return "*(Délai dépassé — même ma patience a des limites.)*"
        except aiohttp.ClientConnectorError:
            if attempt < retries:
                await asyncio.sleep(2)
                continue
            return "*(Impossible de joindre Groq — vérifie la connexion réseau.)*"
        except Exception as e:
            logger.error(f"Groq exception: {e}")
            return f"*(Erreur inattendue: {str(e)[:60]})*"

    return "*(Groq inaccessible après plusieurs tentatives.)*"

# ==================== MUSIQUE (CORRIGÉE) ====================
FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

async def fetch_track_info(query: str) -> dict | None:
    """Récupère les infos yt-dlp (URL fraîche à chaque appel pour éviter l'expiration)."""
    try:
        import yt_dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1',
            'source_address': '0.0.0.0',
        }
        loop = asyncio.get_event_loop()
        def _fetch():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if query.startswith("http"):
                    info = ydl.extract_info(query, download=False)
                else:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                    if info and 'entries' in info and info['entries']:
                        info = info['entries'][0]
                if not info:
                    return None
                return {
                    'title':     info.get('title', '?'),
                    'url':       info.get('url'),
                    'webpage':   info.get('webpage_url', ''),
                    'duration':  info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    # Stocker la webpage_url pour re-fetch si besoin
                    'source_query': info.get('webpage_url') or query,
                }
        return await loop.run_in_executor(None, _fetch)
    except Exception as e:
        logger.error(f"yt-dlp fetch: {e}")
        return None

async def play_next(guild_id: str):
    queue = bot.music_queues.get(guild_id, [])
    vc    = bot.vc_pool.get(guild_id)
    if not vc or not vc.is_connected():
        bot.vc_pool.pop(guild_id, None)
        return
    if not queue:
        bot.now_playing[guild_id] = None
        return
    track = queue.pop(0)
    bot.now_playing[guild_id] = track

    # Re-fetch l'URL fraîche juste avant de jouer (évite les URLs expirées)
    try:
        fresh = await fetch_track_info(track.get('source_query') or track['webpage'] or track['title'])
        if fresh and fresh.get('url'):
            track['url'] = fresh['url']
    except Exception as e:
        logger.warning(f"Re-fetch URL failed: {e}")

    try:
        source = discord.FFmpegPCMAudio(track['url'], **FFMPEG_OPTS)
        vol    = discord.PCMVolumeTransformer(source, volume=0.5)
        def after(error):
            if error: logger.error(f"Player: {error}")
            asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop)
        vc.play(vol, after=after)
    except Exception as e:
        logger.error(f"play_next error: {e}")
        if queue:
            await play_next(guild_id)

# ==================== ANTI-SPAM ====================
async def check_spam(message: discord.Message) -> bool:
    if message.author.bot or message.author.guild_permissions.administrator:
        return False
    gid = str(message.guild.id)
    uid = message.author.id
    now = datetime.now(timezone.utc)
    cfg = bot.antispam_config.get(gid, {
        "enabled": True, "msg_limit": 5, "msg_time": 5,
        "mention_limit": 5, "action": "mute", "mute_duration": 5
    })
    if not cfg.get("enabled", True): return False
    bot.msg_cache[uid].append(now)
    bot.msg_cache[uid] = [t for t in bot.msg_cache[uid]
                          if (now - t).total_seconds() < cfg.get("msg_time", 5)]
    spam, reason = False, ""
    if len(bot.msg_cache[uid]) > cfg.get("msg_limit", 5):
        spam = True; reason = f"Spam ({len(bot.msg_cache[uid])}/{cfg.get('msg_time',5)}s)"
    mentions = len(message.mentions) + len(message.role_mentions) + (50 if message.mention_everyone else 0)
    if mentions >= cfg.get("mention_limit", 5):
        spam = True; reason = f"Spam mentions ({mentions})"
    if spam:
        try:
            await message.delete()
            a = cfg.get("action", "mute")
            if   a == "kick": await message.author.kick(reason=reason)
            elif a == "ban":  await message.author.ban(reason=reason)
            else:
                until = datetime.now(timezone.utc) + timedelta(minutes=cfg.get("mute_duration", 5))
                await message.author.timeout(until, reason=reason)
            await message.channel.send(
                embed=mk_embed(f"{T.SPAM}  Anti-Spam",
                               f"{message.author.mention} sanctionné\n**Raison :** {reason}", T.RED),
                delete_after=8)
            bot.msg_cache[uid] = []
            return True
        except Exception: pass
    return False

# ==================== XP SYSTEM ====================
async def add_xp(message: discord.Message):
    if message.author.bot or not message.guild: return
    uid = message.author.id
    gid = str(message.guild.id)
    now = datetime.now(timezone.utc)
    last = bot.xp_cooldown.get(uid)
    if last and (now - last).total_seconds() < 60: return
    bot.xp_cooldown[uid] = now
    data    = get_xp(gid, str(uid))
    data["xp"]       += random.randint(15, 25)
    data["messages"] += 1
    req = xp_for_level(data["level"] + 1)
    if data["xp"] >= req:
        data["level"] += 1
        data["xp"]    -= req
        guild = bot.get_guild(int(gid))
        if guild:
            ch = guild.get_channel(bot.logs_channels.get(gid, 0)) or message.channel
            e  = mk_embed(f"{T.XP}  Level Up!",
                          f"{message.author.mention} est maintenant **niveau {data['level']}** {T.STAR}",
                          T.GOLD)
            e.set_thumbnail(url=message.author.display_avatar.url)
            try: await ch.send(embed=e)
            except Exception: pass

# ==================== GIVEAWAY (ANNONCE @everyone) ====================
class GiveawayView(discord.ui.View):
    def __init__(self, gid):
        super().__init__(timeout=None)
        self.add_item(GiveawayBtn(gid))

class GiveawayBtn(discord.ui.Button):
    def __init__(self, gid):
        super().__init__(label="Participer", style=discord.ButtonStyle.success,
                         custom_id=f"giveaway_{gid}", emoji="🎉")
        self.gid = gid

    async def callback(self, interaction: discord.Interaction):
        g = bot.giveaways.get(self.gid)
        if not g: return await interaction.response.send_message("Giveaway introuvable.", ephemeral=True)
        if g.get("ended"): return await interaction.response.send_message("Terminé.", ephemeral=True)
        uid = interaction.user.id
        p   = g.setdefault("participants", [])
        if uid in p:
            p.remove(uid); msg = f"{T.CROSS} Tu t'es retiré du giveaway."
        else:
            p.append(uid);  msg = f"{T.CHECK} Tu participes ! ({len(p)} participants)"
        try:
            em = interaction.message.embeds[0]
            for i, f in enumerate(em.fields):
                if "Participants" in f.name:
                    em.set_field_at(i, name=f"{T.STAR} Participants", value=f"**{len(p)}**", inline=True)
                    break
            await interaction.message.edit(embed=em)
        except Exception: pass
        await interaction.response.send_message(msg, ephemeral=True)

@tasks.loop(minutes=1)
async def check_giveaways():
    now = datetime.now(timezone.utc)
    for mid, g in list(bot.giveaways.items()):
        if g.get("ended"): continue
        try:
            end = datetime.fromisoformat(g["end_time"])
            if end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
            if now >= end: await end_giveaway(mid, g)
        except Exception as e: logger.error(f"Giveaway loop: {e}")

async def end_giveaway(mid, g):
    try:
        guild = bot.get_guild(int(g["guild_id"]))
        if not guild: return
        ch = guild.get_channel(int(g["channel_id"]))
        if not ch: return
        g["ended"] = True
        p = g.get("participants", [])
        winners = []
        if p:
            for wid in random.sample(p, min(g.get("winners", 1), len(p))):
                try: winners.append(await bot.fetch_user(wid))
                except Exception: pass

        # Éditer le message original
        if winners:
            desc = "\n".join([f"{T.TROPHY} {w.mention}" for w in winners])
            e = mk_embed(f"{T.GIVEAWAY}  Giveaway Terminé",
                         f"**{g['title']}**\n**Prix :** {g['prize']}\n\n{T.LINE}\n**Gagnant(s) :**\n{desc}",
                         T.GOLD)
        else:
            e = mk_embed(f"{T.GIVEAWAY}  Giveaway Terminé",
                         f"**{g['title']}**\n{T.CROSS} Aucun participant.", T.RED)
        try:
            msg = await ch.fetch_message(int(mid))
            await msg.edit(embed=e, view=None)
        except Exception: pass

        # ✅ Annonce @everyone avec résultats
        if winners:
            winners_mentions = " ".join([w.mention for w in winners])
            winners_str      = ", ".join([str(w) for w in winners])
            announce = discord.Embed(
                title=f"{T.GIVEAWAY}  Félicitations ! Giveaway terminé !",
                description=(
                    f"**{g['title']}**\n"
                    f"{T.GIFT} **Prix :** {g['prize']}\n"
                    f"{T.LINE}\n"
                    f"{T.TROPHY} **Gagnant(s) :** {winners_mentions}\n\n"
                    f"*Bravo à {winners_str} !*"
                ),
                color=T.GOLD,
                timestamp=datetime.now(timezone.utc)
            )
            announce.set_footer(text=f"{len(p)} participant(s) au total")
            await ch.send(content="@everyone 🎉 **Le giveaway est terminé !**",
                          embed=announce, allowed_mentions=discord.AllowedMentions(everyone=True))
        else:
            await ch.send(
                embed=mk_embed(f"{T.GIVEAWAY}  Giveaway terminé",
                               f"**{g['title']}**\nAucun gagnant — personne n'avait participé.", T.RED))
    except Exception as e: logger.error(f"end_giveaway: {e}")

# ==================== POLL (AVEC DURÉE + ANNONCE @everyone) ====================
POLL_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

class PollView(discord.ui.View):
    def __init__(self, poll_id: str, options: list):
        super().__init__(timeout=None)
        for i, opt in enumerate(options[:5]):
            self.add_item(PollBtn(poll_id, i, opt))

class PollBtn(discord.ui.Button):
    def __init__(self, poll_id: str, idx: int, label: str):
        super().__init__(
            label=label[:60],
            style=discord.ButtonStyle.secondary,
            custom_id=f"poll_{poll_id}_{idx}",
            emoji=POLL_EMOJIS[idx]
        )
        self.poll_id = poll_id
        self.idx     = idx

    async def callback(self, interaction: discord.Interaction):
        poll = bot.polls.get(str(interaction.message.id))
        if not poll: poll = bot.polls.get(self.poll_id)  # fallback si migration
        if not poll:
            return await interaction.response.send_message(
                "Sondage introuvable (bot redémarré ?).", ephemeral=True)
        if poll.get("ended"):
            return await interaction.response.send_message("Ce sondage est terminé.", ephemeral=True)

        uid   = interaction.user.id
        votes = poll.setdefault("votes", {})
        if votes.get(uid) == self.idx:
            del votes[uid]
            await interaction.response.send_message(f"{T.CROSS} Vote retiré.", ephemeral=True)
        else:
            votes[uid] = self.idx
            await interaction.response.send_message(
                f"{T.CHECK} Voté pour **{poll['options'][self.idx]}** !", ephemeral=True)
        try:
            await _update_poll_embed(interaction.message, poll)
        except Exception as e:
            logger.error(f"Poll update: {e}")

async def _update_poll_embed(message, poll):
    counts = [0] * len(poll["options"])
    for v in poll.get("votes", {}).values():
        if 0 <= v < len(counts): counts[v] += 1
    total = sum(counts)
    desc  = f"**{poll['question']}**\n\n"
    for i, opt in enumerate(poll["options"]):
        pct = int(counts[i] / total * 100) if total > 0 else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        desc += f"{POLL_EMOJIS[i]} **{opt}**\n`{bar}` {counts[i]} vote{'s' if counts[i] != 1 else ''} ({pct}%)\n\n"
    desc += f"{T.CHART} **{total} vote{'s' if total != 1 else ''} au total**"
    if poll.get("end_time"):
        end = datetime.fromisoformat(poll["end_time"])
        desc += f"\n\n{T.CLOCK} Fin : <t:{int(end.timestamp())}:R>"
    await message.edit(embed=mk_embed(f"{T.POLL}  Sondage", desc, T.BLURPLE))

async def _build_results_embed(poll) -> discord.Embed:
    """Génère l'embed de résultats final pour le poll."""
    counts = [0] * len(poll["options"])
    for v in poll.get("votes", {}).values():
        if 0 <= v < len(counts): counts[v] += 1
    total = sum(counts)
    # Trouver le/les gagnant(s)
    max_count = max(counts) if counts else 0
    winners   = [poll["options"][i] for i, c in enumerate(counts) if c == max_count and max_count > 0]

    desc = f"**{poll['question']}**\n\n"
    for i, opt in enumerate(poll["options"]):
        pct   = int(counts[i] / total * 100) if total > 0 else 0
        bar   = "█" * (pct // 10) + "░" * (10 - pct // 10)
        crown = " 👑" if opt in winners and max_count > 0 else ""
        desc += f"{POLL_EMOJIS[i]} **{opt}**{crown}\n`{bar}` {counts[i]} vote{'s' if counts[i] != 1 else ''} ({pct}%)\n\n"
    desc += f"{T.CHART} **{total} vote{'s' if total != 1 else ''} au total**"

    e = mk_embed(f"{T.POLL}  Résultats du sondage", desc, T.GOLD)
    if winners and max_count > 0:
        e.add_field(name="🏆 Résultat", value=" / ".join(winners), inline=False)
    return e

@tasks.loop(seconds=30)
async def check_polls():
    now = datetime.now(timezone.utc)
    for mid, poll in list(bot.polls.items()):
        if poll.get("ended") or not poll.get("end_time"): continue
        try:
            end = datetime.fromisoformat(poll["end_time"])
            if end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
            if now >= end:
                await end_poll(mid, poll)
        except Exception as e: logger.error(f"Poll loop: {e}")

async def end_poll(mid, poll):
    try:
        guild = bot.get_guild(int(poll["guild_id"]))
        if not guild: return
        ch = guild.get_channel(int(poll["channel_id"]))
        if not ch: return
        poll["ended"] = True

        # Éditer le message original avec résultats finaux
        try:
            msg = await ch.fetch_message(int(mid))
            results_embed = await _build_results_embed(poll)
            await msg.edit(embed=results_embed, view=None)
        except Exception: pass

        # ✅ Annonce @everyone avec résultats
        results_embed2 = await _build_results_embed(poll)
        total_votes = sum(1 for _ in poll.get("votes", {}))
        results_embed2.set_footer(text=f"{total_votes} participant(s) ont voté")
        await ch.send(
            content="@everyone 📊 **Le sondage est terminé ! Voici les résultats :**",
            embed=results_embed2,
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )
    except Exception as e: logger.error(f"end_poll: {e}")

# ==================== EVENTS ====================
@bot.event
async def on_ready():
    logger.info(f"⚡ {bot.user} | {len(bot.guilds)} serveurs")
    if not check_giveaways.is_running(): check_giveaways.start()
    if not check_polls.is_running():     check_polls.start()
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="✨ /aide | Aegis V8"))
    # Mise à jour de la bio
    try:
        await bot.application.edit(description=(
            "🤖 **Aegis V7** — Bot Discord multifonction\n\n"
            "✨ Modération • 🎵 Musique • 🎉 Giveaway • 📊 Sondages • ⭐ XP\n"
            "🛡️ Anti-raid/spam • 🎫 Tickets • 🤖 IA Groq\n\n"
            "🆘 Serveur support en cas de bug : https://discord.gg/LIEN_SUPPORT\n"
            "Utilise /aide pour voir toutes les commandes."
        ))
        logger.info("✅ Bio mise à jour")
    except Exception as bio_err:
        logger.warning(f"Bio update: {bio_err}")

@bot.event
async def on_member_join(member: discord.Member):
    gid = str(member.guild.id)
    now = datetime.now(timezone.utc)
    bot.anti_raid_cache.setdefault(gid, []).append(now)
    bot.anti_raid_cache[gid] = [t for t in bot.anti_raid_cache[gid]
                                 if (now - t).total_seconds() < 10]
    raid = bot.raid_protection.get(gid, {"enabled": True, "threshold": 5, "action": "kick"})
    if raid.get("enabled") and len(bot.anti_raid_cache[gid]) > raid.get("threshold", 5):
        try:
            if raid.get("action") == "ban": await member.ban(reason="Anti-raid")
            else:                            await member.kick(reason="Anti-raid")
        except Exception: pass
        return
    if gid in bot.auto_roles:
        role = member.guild.get_role(bot.auto_roles[gid])
        if role:
            try: await member.add_roles(role)
            except Exception: pass
    if gid in bot.arrivee_channels:
        ch = member.guild.get_channel(bot.arrivee_channels[gid])
        if ch:
            created = member.created_at.strftime("%d/%m/%Y")
            joined  = member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "Maintenant"
            count   = member.guild.member_count
            e = discord.Embed(
                title=f"{T.WAVE}  Bienvenue sur {member.guild.name} !",
                description=(f"{T.LINE}\n{T.ARROW} **Membre :** {member.mention}\n"
                             f"{T.ARROW} **Compte créé le :** {created}\n"
                             f"{T.ARROW} **A rejoint le :** {joined}\n"
                             f"{T.ARROW} **Membre numéro :** `#{count}`\n{T.LINE}"),
                color=T.GREEN, timestamp=datetime.now(timezone.utc))
            e.set_thumbnail(url=member.display_avatar.url)
            e.set_image(url=member.display_avatar.with_size(512).url)
            e.set_footer(text=f"{member.guild.name} • {count} membres")
            try: await ch.send(embed=e)
            except Exception: pass

@bot.event
async def on_member_remove(member: discord.Member):
    gid = str(member.guild.id)
    if gid in bot.depart_channels:
        ch = member.guild.get_channel(bot.depart_channels[gid])
        if ch:
            roles    = [r.mention for r in member.roles if r.name != "@everyone"]
            duration = ""
            if member.joined_at:
                d        = datetime.now(timezone.utc) - member.joined_at.replace(tzinfo=timezone.utc)
                duration = f"{d.days} jour{'s' if d.days != 1 else ''}"
            e = discord.Embed(
                title=f"{T.DOOR}  Au revoir !",
                description=(f"{T.LINE}\n{T.ARROW} **Membre :** {member.mention} (`{member}`)\n"
                             f"{T.ARROW} **Resté :** {duration or 'inconnu'}\n"
                             f"{T.ARROW} **Rôles :** {', '.join(roles) if roles else 'Aucun'}\n{T.LINE}"),
                color=T.RED, timestamp=datetime.now(timezone.utc))
            e.set_thumbnail(url=member.display_avatar.url)
            e.set_footer(text=f"{member.guild.member_count} membres restants")
            try: await ch.send(embed=e)
            except Exception: pass

@bot.event
async def on_voice_state_update(member, before, after):
    gid = str(member.guild.id)
    if gid in bot.temp_voices:
        if after.channel and after.channel.id == bot.temp_voices[gid]:
            try:
                nc = await member.guild.create_voice_channel(
                    f"🔊 {member.display_name}", category=after.channel.category)
                await member.move_to(nc)
            except Exception: pass
    if (before.channel and before.channel.name.startswith("🔊 ")
            and len(before.channel.members) == 0):
        try: await before.channel.delete()
        except Exception: pass

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    if message.guild:
        if await check_spam(message): return
        await add_xp(message)

    bot_mentioned  = bot.user in (message.mentions or [])
    name_mentioned = "aegis" in message.content.lower()

    if message.guild and (bot_mentioned or name_mentioned):
        uid = message.author.id
        now = datetime.now(timezone.utc)
        last_ai = bot.ai_cooldown.get(uid)
        if last_ai and (now - last_ai).total_seconds() < 5:
            await bot.process_commands(message)
            return
        bot.ai_cooldown[uid] = now
        question = message.content
        if bot_mentioned:
            question = re.sub(r'<@!?\d+>', '', question).strip()
        elif name_mentioned:
            question = re.sub(r'(?i)\baegis\b[,\s]*', '', question, count=1).strip()
        if len(question) < 2: question = "Bonjour !"
        async with message.channel.typing():
            response = await ask_groq(question)
        try: await message.reply(f"{T.AI} {response}")
        except Exception: pass
        return

    await bot.process_commands(message)

# ==================== VIEWS ====================
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketBtn())

class TicketBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Ouvrir un Ticket", style=discord.ButtonStyle.blurple,
                         custom_id="open_ticket", emoji="🎫")
    async def callback(self, interaction: discord.Interaction):
        gid  = str(interaction.guild.id)
        cfg  = bot.ticket_configs.get(gid, {})
        name = f"ticket-{interaction.user.name.lower()[:20]}"
        if discord.utils.get(interaction.guild.text_channels, name=name):
            return await interaction.response.send_message(
                f"{T.WARN} Tu as déjà un ticket ouvert.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            cat = (discord.utils.get(interaction.guild.categories, name="📩 Tickets") or
                   await interaction.guild.create_category("📩 Tickets", overwrites={
                       interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                       interaction.guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
                   }))
            ow = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
                interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
            }
            if cfg.get("support_role"):
                sr = interaction.guild.get_role(cfg["support_role"])
                if sr: ow[sr] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            ch = await interaction.guild.create_text_channel(name, category=cat, overwrites=ow)
            e  = mk_embed(f"{T.TICKET}  Nouveau Ticket",
                          f"Bienvenue {interaction.user.mention} !\nDécris ton problème.", T.BLURPLE)
            e.set_footer(text=f"Ticket de {interaction.user}")
            await ch.send(embed=e, view=CloseTicketView())
            await interaction.followup.send(f"{T.CHECK} Ticket créé : {ch.mention}", ephemeral=True)
        except Exception as ex:
            await interaction.followup.send(f"{T.CROSS} Erreur : {str(ex)[:100]}", ephemeral=True)

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger,
                       custom_id="close_ticket", emoji="🔐")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=mk_embed(f"{T.LOCK}  Fermeture", "Suppression dans 5 secondes...", T.BLURPLE))
        await asyncio.sleep(5)
        try: await interaction.channel.delete()
        except Exception: pass

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Se vérifier", style=discord.ButtonStyle.success,
                       custom_id="verify_btn", emoji="✅")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid  = str(interaction.guild.id)
        rid  = bot.verif_roles.get(gid)
        role = interaction.guild.get_role(rid) if rid else None
        if not role:
            for n in ["Vérifié", "✅ Vérifié", "Membre"]:
                role = discord.utils.get(interaction.guild.roles, name=n)
                if role: break
        if not role:
            try:
                role = await interaction.guild.create_role(name="✅ Vérifié", color=discord.Color.green())
                bot.verif_roles[gid] = role.id
            except Exception:
                return await interaction.response.send_message(f"{T.CROSS} Erreur création rôle.", ephemeral=True)
        if role in interaction.user.roles:
            return await interaction.response.send_message(f"{T.CHECK} Déjà vérifié !", ephemeral=True)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"{T.CHECK} Vérifié ! {role.mention}", ephemeral=True)
        except Exception:
            await interaction.response.send_message(f"{T.CROSS} Erreur permissions.", ephemeral=True)

class RulesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="J'accepte le règlement", style=discord.ButtonStyle.success,
                       custom_id="accept_rules", emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid  = str(interaction.guild.id)
        rid  = bot.verif_roles.get(gid)
        role = interaction.guild.get_role(rid) if rid else None
        if not role:
            for n in ["Membre", "Vérifié", "✅ Vérifié"]:
                role = discord.utils.get(interaction.guild.roles, name=n)
                if role: break
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"{T.CHECK} Accepté ! {role.mention}", ephemeral=True)
            except Exception:
                await interaction.response.send_message(f"{T.WARN} Erreur permissions.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{T.CHECK} Règlement accepté !", ephemeral=True)

class ApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Postuler", style=discord.ButtonStyle.success,
                       custom_id="apply_btn", emoji="📝")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplyModal())

class ApplyModal(discord.ui.Modal, title="📝 Candidature"):
    pseudo     = discord.ui.TextInput(label="Pseudo", max_length=50)
    age        = discord.ui.TextInput(label="Âge", max_length=3)
    motivation = discord.ui.TextInput(label="Motivation", style=discord.TextStyle.paragraph, max_length=500)
    async def on_submit(self, interaction: discord.Interaction):
        e = mk_embed(f"{T.SPARKLE}  Nouvelle Candidature", color=T.PINK)
        e.add_field(name="Pseudo",     value=self.pseudo.value,        inline=True)
        e.add_field(name="Âge",        value=self.age.value,           inline=True)
        e.add_field(name="Discord",    value=interaction.user.mention, inline=True)
        e.add_field(name="Motivation", value=self.motivation.value,    inline=False)
        e.set_thumbnail(url=interaction.user.display_avatar.url)
        ch = discord.utils.get(interaction.guild.text_channels, name="candidatures")
        if ch: await ch.send(embed=e)
        await interaction.response.send_message(f"{T.CHECK} Candidature envoyée !", ephemeral=True)

class RoleMenu(discord.ui.Select):
    def __init__(self, roles):
        opts = [discord.SelectOption(label=r.name, value=str(r.id), emoji="🎭") for r in roles[:25]]
        super().__init__(placeholder="Choisis tes rôles...", min_values=0,
                         max_values=len(opts), options=opts, custom_id="role_select")
    async def callback(self, interaction: discord.Interaction):
        selected = [int(v) for v in self.values]
        added, removed = [], []
        for opt in self.options:
            role = interaction.guild.get_role(int(opt.value))
            if role:
                if int(opt.value) in selected and role not in interaction.user.roles:
                    await interaction.user.add_roles(role);    added.append(role.name)
                elif int(opt.value) not in selected and role in interaction.user.roles:
                    await interaction.user.remove_roles(role); removed.append(role.name)
        parts = []
        if added:   parts.append(f"{T.CHECK} Ajouté : {', '.join(added)}")
        if removed: parts.append(f"{T.CROSS} Retiré : {', '.join(removed)}")
        await interaction.response.send_message("\n".join(parts) or "Aucun changement", ephemeral=True)

class RoleMenuView(discord.ui.View):
    def __init__(self, roles):
        super().__init__(timeout=None)
        self.add_item(RoleMenu(roles))

# ==================== SUGGESTION VIEW ====================
class SuggestionView(discord.ui.View):
    def __init__(self, suggestion_id: str):
        super().__init__(timeout=None)
    @discord.ui.button(label="👍 Approuver", style=discord.ButtonStyle.success, custom_id="suggest_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("Permission refusée.", ephemeral=True)
        e = interaction.message.embeds[0]
        e.color = T.GREEN
        e.title = f"✅  Suggestion approuvée"
        e.set_footer(text=f"Approuvé par {interaction.user.display_name}")
        await interaction.message.edit(embed=e, view=None)
        await interaction.response.send_message("Suggestion approuvée !", ephemeral=True)

    @discord.ui.button(label="👎 Refuser", style=discord.ButtonStyle.danger, custom_id="suggest_refuse")
    async def refuse(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("Permission refusée.", ephemeral=True)
        e = interaction.message.embeds[0]
        e.color = T.RED
        e.title = f"❌  Suggestion refusée"
        e.set_footer(text=f"Refusé par {interaction.user.display_name}")
        await interaction.message.edit(embed=e, view=None)
        await interaction.response.send_message("Suggestion refusée.", ephemeral=True)

# ==================== REGLEMENT MODAL ====================
class ReglementModal(discord.ui.Modal, title="✍️ Règlement personnalisé"):
    contenu = discord.ui.TextInput(
        label="Ton règlement", style=discord.TextStyle.paragraph,
        placeholder="Écris les règles ici...", max_length=2000)
    def __init__(self, avec_bouton, role):
        super().__init__()
        self.avec_bouton = avec_bouton
        self.role_obj    = role
    async def on_submit(self, interaction: discord.Interaction):
        if self.role_obj:
            bot.verif_roles[str(interaction.guild.id)] = self.role_obj.id
        e = discord.Embed(title=f"{T.SHIELD}  Règlement du serveur",
                          description=self.contenu.value, color=T.BLURPLE,
                          timestamp=datetime.now(timezone.utc))
        await interaction.channel.send(embed=e, view=RulesView() if self.avec_bouton else None)
        await interaction.response.send_message(embed=ok("Règlement envoyé !"), ephemeral=True)

# ==================== SETUP STRUCTURES (ENRICHIES) ====================
SETUP_STRUCTURES = {
    "communaute": {
        "label": "🌐 Communauté / Discussion",
        "roles": [
            ("━━ STAFF ━━", 0x2B2D31), ("👑 Fondateur", T.PINK), ("⚔️ Admin", 0xE74C3C),
            ("🛡️ Modérateur", T.BLURPLE), ("🤝 Helper", T.TEAL),
            ("━━ MEMBRES ━━", 0x2B2D31),
            ("💎 VIP", 0xF1C40F), ("🔥 Actif", 0xE74C3C), ("🎨 Créateur", T.PURPLE),
            ("✅ Vérifié", T.GREEN), ("🎮 Membre", 0x95A5A6)
        ],
        "structure": {
            "📌 IMPORTANT":  (["📜・règles", "📢・annonces", "📰・news", "🗺️・liens-utiles"], []),
            "👋 ACCUEIL":    (["👋・bienvenue", "🚪・départs", "✅・vérification",
                               "🎫・rôles", "📝・présentation"], []),
            "💬 GÉNÉRAL":   (["💬・général", "🖼️・médias", "😂・mèmes", "🎨・créations",
                              "🎶・partage-musique", "📸・photos", "🤖・bot-commands"],
                             ["🔊 Général", "🔊 Chill", "🎵 Musique", "🎮 Gaming"]),
            "🎉 EVENTS":     (["🎉・événements", "📊・sondages", "🏆・concours", "🎁・giveaways"], []),
            "📩 SUPPORT":    (["❓・aide", "💡・suggestions", "🐛・rapports-bugs"], []),
            "🔒 STAFF":      (["📋・staff-chat", "📊・logs", "📝・candidatures",
                               "⚙️・config-bot", "🚨・rapports"], ["🔒 Staff", "🔒 Staff Vocal"]),
            "🎫 Tickets":    ([], []),
        }
    },
    "gaming": {
        "label": "🎮 Gaming",
        "roles": [
            ("━━ STAFF ━━", 0x2B2D31), ("👑 Fondateur", T.PINK), ("⚔️ Admin", 0xE74C3C),
            ("🛡️ Modérateur", T.BLURPLE), ("━━ RANGS ━━", 0x2B2D31),
            ("🏆 Légende", 0xF1C40F), ("💎 Diamant", 0x3498DB),
            ("🔥 Tryhard", 0xE74C3C), ("🎮 Casual", 0x95A5A6),
            ("🎯 Speedrunner", T.TEAL), ("✅ Vérifié", T.GREEN)
        ],
        "structure": {
            "📌 IMPORTANT":  (["📜・règles", "📢・annonces", "🆕・nouveautés"], []),
            "👋 ACCUEIL":    (["👋・bienvenue", "🚪・départs", "✅・vérification",
                               "📝・présentation", "🎮・jeux-joués"], []),
            "🎮 GAMING":     (["🎮・général", "📸・clips", "🏆・tournois",
                               "💡・stratégie", "🐛・bugs-reports", "💰・échanges"],
                              ["🎮 Gaming 1", "🎮 Gaming 2", "🎮 Gaming 3", "🎮 Gaming 4"]),
            "🎵 MUSIQUE":    (["🎵・playlist", "🤖・bot-musique"], ["🎵 Musique"]),
            "📺 STREAMS":    (["📢・live-annonces", "💬・discussion-streams"], ["📺 Stream 1", "📺 Stream 2"]),
            "🎉 EVENTS":     (["🏆・tournois", "🎁・giveaways", "📊・sondages"], []),
            "📩 SUPPORT":    (["❓・aide", "💡・suggestions"], []),
            "🔒 STAFF":      (["📋・staff-chat", "📊・logs", "⚙️・config"], ["🔒 Staff"]),
            "🎫 Tickets":    ([], []),
        }
    },
    "rp": {
        "label": "🎭 Jeu de Rôle (RP)",
        "roles": [
            ("━━ STAFF ━━", 0x2B2D31), ("👑 Maître du Jeu", T.PINK), ("⚔️ Modérateur RP", 0xE74C3C),
            ("📖 Scénariste", T.TEAL), ("━━ GRADES RP ━━", 0x2B2D31),
            ("🔮 Légende", 0xF1C40F), ("⚔️ Héros", 0xE74C3C),
            ("🗡️ Aventurier", T.BLURPLE), ("🌱 Novice", T.GREEN), ("✅ Vérifié", T.GREEN)
        ],
        "structure": {
            "📌 IMPORTANT":  (["📜・règles-rp", "📢・annonces", "📖・lore",
                               "🗺️・carte-du-monde", "📅・agenda-rp"], []),
            "👋 ACCUEIL":    (["👋・arrivées", "🚪・départs", "✅・vérification",
                               "📝・fiches-perso", "🎭・présentation-perso"], []),
            "🏙️ LIEUX":     (["🏙️・ville-principale", "🌲・forêt-ancienne",
                               "🏰・château-royal", "⚔️・arène-de-combat",
                               "🍺・taverne-du-voyageur", "🏔️・montagne-mystique",
                               "🌊・port-et-docks", "⛪・temple-sacré"],
                              ["🎭 RP Vocal 1", "🎭 RP Vocal 2", "🎭 RP Vocal 3"]),
            "💬 HORS-JEU":   (["💬・général-hj", "🖼️・médias", "🎨・fan-art",
                               "💡・suggestions-rp", "📊・sondages"], ["🔊 Hors-Jeu"]),
            "📩 SUPPORT":    (["❓・aide", "🐛・rapports"], []),
            "🔒 STAFF":      (["📋・staff-chat", "📊・logs", "🎲・jets-de-dés"], ["🔒 Staff MJ"]),
            "🎫 Tickets":    ([], []),
        }
    },
    "education": {
        "label": "📚 Éducation / Études",
        "roles": [
            ("━━ STAFF ━━", 0x2B2D31), ("👑 Admin", T.PINK), ("📚 Modérateur", T.BLURPLE),
            ("👨‍🏫 Tuteur", T.TEAL), ("━━ NIVEAUX ━━", 0x2B2D31),
            ("🎓 Diplômé", 0xF1C40F), ("📖 Étudiant", 0xE74C3C),
            ("🌱 Débutant", T.GREEN), ("✅ Vérifié", T.GREEN)
        ],
        "structure": {
            "📌 IMPORTANT":  (["📜・règles", "📢・annonces", "📅・planning",
                               "📰・ressources-utiles", "🗂️・organisation"], []),
            "👋 ACCUEIL":    (["👋・arrivées", "🚪・départs", "✅・vérification",
                               "📝・présentation", "🎯・objectifs"], []),
            "📚 ÉTUDES":     (["📖・cours-général", "🔢・maths", "💻・informatique",
                               "🌍・langues", "🔬・sciences", "✍️・lettres-philo",
                               "🏛️・histoire-géo", "🎨・arts"],
                              ["📚 Révisions 1", "📚 Révisions 2", "📚 Révisions 3"]),
            "🤝 ENTRAIDE":   (["🆘・demande-aide", "💡・partage-astuces",
                               "📄・partage-cours", "✅・corrigés"], ["🤝 Tutorat 1", "🤝 Tutorat 2"]),
            "💬 DÉTENTE":    (["💬・général", "😂・mèmes", "🎮・gaming",
                               "🎵・musique"], ["🔊 Détente", "🎮 Gaming"]),
            "📩 SUPPORT":    (["❓・aide", "💡・suggestions"], []),
            "🔒 STAFF":      (["📋・staff-chat", "📊・logs"], ["🔒 Staff"]),
            "🎫 Tickets":    ([], []),
        }
    },
    "anime": {
        "label": "🎌 Anime / Manga",
        "roles": [
            ("━━ STAFF ━━", 0x2B2D31), ("👑 Fondateur", T.PINK), ("⚔️ Admin", 0xE74C3C),
            ("🛡️ Modérateur", T.BLURPLE), ("━━ FANS ━━", 0x2B2D31),
            ("🌟 Otaku Légendaire", 0xF1C40F), ("📖 Lecteur Assidu", T.TEAL),
            ("🎌 Weeaboo", T.PURPLE), ("✅ Vérifié", T.GREEN)
        ],
        "structure": {
            "📌 IMPORTANT":  (["📜・règles", "📢・annonces", "🆕・sorties-anime",
                               "⚠️・spoilers-warning"], []),
            "👋 ACCUEIL":    (["👋・bienvenue", "🚪・départs", "✅・vérification",
                               "🎌・présentation", "🎭・waifu-husbando"], []),
            "🎌 ANIME":      (["💬・général-anime", "🔥・currently-watching",
                               "⭐・recommandations", "🏆・top-animes",
                               "📸・fan-art", "🎵・openings-endings"], []),
            "📖 MANGA":      (["📖・général-manga", "🆕・nouveaux-chapitres",
                               "💬・discussions-manga", "🖊️・manhwa-manhua"], []),
            "⚠️ SPOILERS":   (["⚠️・spoilers-généraux", "🔒・spoilers-récents"], []),
            "🎵 WEEB":       (["🎵・musique-anime", "🎮・jeux-anime",
                               "📺・osamu-tezuka", "💻・vtubers"],
                              ["🔊 Général", "🎵 Weeb Music"]),
            "🎉 EVENTS":     (["🏆・concours-fan-art", "📊・sondages", "🎁・giveaways"], []),
            "🔒 STAFF":      (["📋・staff-chat", "📊・logs", "📝・candidatures"], ["🔒 Staff"]),
            "🎫 Tickets":    ([], []),
        }
    }
}

# ==================== COMMANDES ====================

@bot.tree.command(name="aide", description="Liste de toutes les commandes")
async def aide(interaction: discord.Interaction):
    e = discord.Embed(title=f"{T.SPARKLE}  Aegis V8 — Commandes",
                      description="Toutes les commandes disponibles",
                      color=T.PINK, timestamp=datetime.now(timezone.utc))
    e.add_field(name=f"{T.DIAMOND}  Modération",
                value="`/ban` `/unban` `/kick` `/mute` `/unmute` `/warn` `/unwarn` `/warns` `/rename` `/purge`", inline=False)
    e.add_field(name=f"{T.CHANNEL}  Salons",
                value="`/creersalon` `/creervoice` `/supprimersalon` `/lock` `/unlock` `/slowmode`", inline=False)
    e.add_field(name=f"{T.ROLE}  Rôles",
                value="`/creerole` `/addrole` `/removerole` `/roleall` `/autorole` `/rolemenu`", inline=False)
    e.add_field(name=f"{T.GEAR}  Systèmes",
                value="`/panel` `/reglement` `/verification` `/giveaway` `/reroll` `/poll` `/suggestion`", inline=False)
    e.add_field(name=f"{T.WAVE}  Membres",
                value="`/arrivee` `/depart` `/backup` `/restore` `/antiraid` `/antispam` `/setup` `/tempvoice`", inline=False)
    e.add_field(name=f"{T.MUSIC}  Musique",
                value="`/play` `/pause` `/resume` `/skip` `/stop` `/queue` `/nowplaying` `/volume`", inline=False)
    e.add_field(name=f"{T.XP}  XP & Stats",
                value="`/rank` `/top` `/userinfo` `/serverinfo` `/avatar`", inline=False)
    e.add_field(name=f"{T.MEGA}  Divers",
                value="`/dire` `/embed` `/sondage-rapide` `/tirage`", inline=False)
    e.add_field(name=f"{T.AI}  IA",
                value="Mentionne **@Aegis** ou écris **aegis** dans un message !", inline=False)
    e.set_footer(text="Aegis V8 • /aide pour revoir cette liste")
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="ping", description="Latence du bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=inf("Pong !", f"{T.LIGHTNING} `{round(bot.latency * 1000)} ms`"))

# ── Commande DIRE ──
@bot.tree.command(name="dire", description="Faire parler le bot à ta place dans un salon")
@app_commands.describe(message="Le message à envoyer", salon="Salon cible (vide = actuel)")
@app_commands.default_permissions(manage_messages=True)
async def dire(interaction: discord.Interaction, message: str, salon: discord.TextChannel = None):
    target = salon or interaction.channel
    try:
        await target.send(message)
        await interaction.response.send_message(
            embed=ok("Message envoyé", f"Envoyé dans {target.mention}"), ephemeral=True)
    except Exception as ex:
        await interaction.response.send_message(embed=err("Erreur", str(ex)[:100]), ephemeral=True)

# ── Commande EMBED ──
@bot.tree.command(name="embed", description="Envoyer un embed personnalisé")
@app_commands.describe(titre="Titre", contenu="Contenu", couleur="Couleur hex (ex: #FF1493)",
                        salon="Salon cible")
@app_commands.default_permissions(manage_messages=True)
async def embed_cmd(interaction: discord.Interaction, titre: str, contenu: str,
                    couleur: str = "#5865F2", salon: discord.TextChannel = None):
    target = salon or interaction.channel
    try:
        color = int(couleur.replace("#", ""), 16)
    except ValueError:
        color = T.BLURPLE
    e = discord.Embed(title=titre, description=contenu, color=color,
                      timestamp=datetime.now(timezone.utc))
    e.set_footer(text=f"Par {interaction.user.display_name}")
    await target.send(embed=e)
    await interaction.response.send_message(embed=ok("Embed envoyé !", f"Dans {target.mention}"), ephemeral=True)

# ── Commande SONDAGE RAPIDE (oui/non) ──
@bot.tree.command(name="sondage-rapide", description="Sondage Oui/Non rapide")
@app_commands.describe(question="Ta question")
async def sondage_rapide(interaction: discord.Interaction, question: str):
    e = mk_embed(f"{T.POLL}  Sondage rapide", f"**{question}**\n\nRéagis pour voter !", T.BLURPLE)
    e.set_footer(text=f"Posé par {interaction.user.display_name}")
    await interaction.response.send_message(embed=e)
    msg = await interaction.original_response()
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
    await msg.add_reaction("🤷")

# ── Commande TIRAGE ──
@bot.tree.command(name="tirage", description="Faire un tirage au sort parmi des options")
@app_commands.describe(options="Les options séparées par des virgules (ex: Pierre,Feuille,Ciseaux)")
async def tirage(interaction: discord.Interaction, options: str):
    choices = [o.strip() for o in options.split(",") if o.strip()]
    if len(choices) < 2:
        return await interaction.response.send_message(
            embed=err("Erreur", "Donne au moins 2 options séparées par des virgules."), ephemeral=True)
    winner = random.choice(choices)
    desc = f"**Options :** {' • '.join(choices)}\n\n{T.ARROW} **Résultat : {winner}**"
    await interaction.response.send_message(embed=mk_embed(f"{T.TROPHY}  Tirage au sort", desc, T.GOLD))

# ── Commande AVATAR ──
@bot.tree.command(name="avatar", description="Voir l'avatar d'un membre en grand")
@app_commands.describe(membre="Le membre (vide = toi)")
async def avatar(interaction: discord.Interaction, membre: discord.Member = None):
    m = membre or interaction.user
    e = discord.Embed(title=f"🖼️  Avatar de {m.display_name}", color=T.BLURPLE)
    e.set_image(url=m.display_avatar.with_size(1024).url)
    e.set_footer(text=f"ID : {m.id}")
    await interaction.response.send_message(embed=e)

# ── Commande SUGGESTION ──
@bot.tree.command(name="suggestion", description="Envoyer une suggestion au staff")
@app_commands.describe(texte="Ta suggestion", salon="Salon des suggestions (vide = auto-detect)")
async def suggestion(interaction: discord.Interaction, texte: str,
                      salon: discord.TextChannel = None):
    # Auto-detect salon suggestions
    if not salon:
        for name in ["💡・suggestions", "suggestions", "suggest", "idées"]:
            salon = discord.utils.get(interaction.guild.text_channels, name=name)
            if salon: break
    if not salon:
        return await interaction.response.send_message(
            embed=err("Salon introuvable",
                      "Crée un salon `💡・suggestions` ou précise le salon avec `/suggestion salon:#ton-salon`."),
            ephemeral=True)
    e = mk_embed(f"💡  Nouvelle suggestion", texte, T.GOLD)
    e.add_field(name="Proposé par", value=f"{interaction.user.mention}", inline=True)
    e.add_field(name="Statut", value="En attente ⏳", inline=True)
    e.set_thumbnail(url=interaction.user.display_avatar.url)
    e.set_footer(text=f"ID : {interaction.user.id}")
    msg = await salon.send(embed=e, view=SuggestionView(str(interaction.id)))
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
    await interaction.response.send_message(
        embed=ok("Suggestion envoyée !", f"Ta suggestion a été soumise dans {salon.mention}."),
        ephemeral=True)

# ── Musique ──
@bot.tree.command(name="play", description="Jouer une musique depuis YouTube")
@app_commands.describe(recherche="Titre ou lien YouTube")
async def play(interaction: discord.Interaction, recherche: str):
    if not interaction.user.voice:
        return await interaction.response.send_message(
            embed=err("Pas dans un vocal", "Rejoins un salon vocal d'abord !"), ephemeral=True)
    await interaction.response.defer()
    gid = str(interaction.guild.id)

    await interaction.followup.send(embed=inf(f"{T.MUSIC}  Recherche...", f"🔍 `{recherche}`"))
    track = await fetch_track_info(recherche)
    if not track or not track.get('url'):
        return await interaction.edit_original_response(
            embed=err("Introuvable", "Aucun résultat. Essaie un autre titre ou un lien direct YouTube."))

    vc = bot.vc_pool.get(gid)
    if not vc or not vc.is_connected():
        try:
            vc = await interaction.user.voice.channel.connect()
            bot.vc_pool[gid] = vc
        except Exception as ex:
            return await interaction.edit_original_response(embed=err("Erreur vocal", str(ex)[:100]))

    bot.music_queues.setdefault(gid, []).append(track)

    if not vc.is_playing() and not vc.is_paused():
        await play_next(gid)
        e = mk_embed(f"{T.MUSIC}  Lecture en cours",
                     f"**{track['title']}**\n⏱️ `{format_duration(track['duration'])}`", T.BLURPLE)
        if track.get('thumbnail'): e.set_thumbnail(url=track['thumbnail'])
        if track.get('webpage'):   e.add_field(name="Lien", value=f"[YouTube]({track['webpage']})")
    else:
        pos = len(bot.music_queues.get(gid, []))
        e = mk_embed(f"{T.MUSIC}  Ajouté à la file",
                     f"**{track['title']}**\n📋 Position : `#{pos}`", T.GOLD)
        if track.get('thumbnail'): e.set_thumbnail(url=track['thumbnail'])

    await interaction.edit_original_response(embed=e)

@bot.tree.command(name="pause", description="Mettre en pause")
async def pause(interaction: discord.Interaction):
    vc = bot.vc_pool.get(str(interaction.guild.id))
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message(embed=inf(f"{T.PAUSE}  Pause", "Musique en pause."))
    else:
        await interaction.response.send_message(embed=err("Rien à mettre en pause"), ephemeral=True)

@bot.tree.command(name="resume", description="Reprendre la lecture")
async def resume(interaction: discord.Interaction):
    vc = bot.vc_pool.get(str(interaction.guild.id))
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message(embed=ok("Lecture reprise"))
    else:
        await interaction.response.send_message(embed=err("Rien en pause"), ephemeral=True)

@bot.tree.command(name="skip", description="Passer à la musique suivante")
async def skip(interaction: discord.Interaction):
    vc = bot.vc_pool.get(str(interaction.guild.id))
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await interaction.response.send_message(embed=ok(f"{T.SKIP}  Skippé"))
    else:
        await interaction.response.send_message(embed=err("Rien à skipper"), ephemeral=True)

@bot.tree.command(name="stop", description="Arrêter et déconnecter")
async def stop(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    vc  = bot.vc_pool.get(gid)
    if vc:
        bot.music_queues[gid] = []
        bot.now_playing[gid]  = None
        await vc.disconnect()
        bot.vc_pool.pop(gid, None)
        await interaction.response.send_message(embed=ok(f"{T.STOP}  Arrêté", "Déconnecté."))
    else:
        await interaction.response.send_message(embed=err("Bot pas dans un vocal"), ephemeral=True)

@bot.tree.command(name="queue", description="Voir la file musicale")
async def queue(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    q   = bot.music_queues.get(gid, [])
    np  = bot.now_playing.get(gid)
    if not np and not q:
        return await interaction.response.send_message(
            embed=inf("File vide", "Aucune musique en cours."), ephemeral=True)
    desc = ""
    if np:
        desc += f"**▶️ En cours :** {np['title']} `{format_duration(np['duration'])}`\n\n"
    if q:
        desc += "**📋 File :**\n"
        for i, t in enumerate(q[:10], 1):
            desc += f"`{i}.` {t['title']} `{format_duration(t['duration'])}`\n"
        if len(q) > 10: desc += f"*... et {len(q) - 10} autre(s)*"
    await interaction.response.send_message(embed=mk_embed(f"{T.MUSIC}  File musicale", desc, T.BLURPLE))

@bot.tree.command(name="nowplaying", description="Musique en cours")
async def nowplaying(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    np  = bot.now_playing.get(gid)
    if not np:
        return await interaction.response.send_message(embed=inf("Rien en cours"), ephemeral=True)
    e = mk_embed(f"{T.MUSIC}  En cours",
                 f"**{np['title']}**\n⏱️ `{format_duration(np['duration'])}`", T.BLURPLE)
    if np.get('thumbnail'): e.set_thumbnail(url=np['thumbnail'])
    if np.get('webpage'):   e.add_field(name="Lien", value=f"[YouTube]({np['webpage']})")
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="volume", description="Régler le volume de la musique (0-100)")
@app_commands.describe(niveau="Volume entre 0 et 100")
async def volume(interaction: discord.Interaction, niveau: int):
    gid = str(interaction.guild.id)
    vc  = bot.vc_pool.get(gid)
    if not vc or not vc.is_playing():
        return await interaction.response.send_message(embed=err("Rien en cours"), ephemeral=True)
    niveau = max(0, min(100, niveau))
    if vc.source:
        vc.source.volume = niveau / 100
    await interaction.response.send_message(
        embed=ok(f"Volume : {niveau}%", f"{'🔇' if niveau == 0 else '🔊'} Réglé à {niveau}%"))

# ── Modération ──
@bot.tree.command(name="warn", description="Avertir un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
    gid, uid = str(interaction.guild.id), str(membre.id)
    bot.warnings.setdefault(gid, {}).setdefault(uid, []).append(
        {"reason": raison, "mod": str(interaction.user.id), "date": datetime.now(timezone.utc).isoformat()})
    count = len(bot.warnings[gid][uid])
    e = mk_embed(f"{T.WARN}  Avertissement",
                 f"**Membre :** {membre.mention}\n**Raison :** {raison}\n**Total :** {count} warn(s)", T.ORANGE)
    sanction = None
    if count == 3:
        try: await membre.timeout(datetime.now(timezone.utc) + timedelta(hours=1), reason="3 warns"); sanction = "Mute 1h"
        except Exception: pass
    elif count == 5:
        try: await membre.timeout(datetime.now(timezone.utc) + timedelta(hours=24), reason="5 warns"); sanction = "Mute 24h"
        except Exception: pass
    elif count >= 7:
        try: await membre.kick(reason="7 warns"); sanction = "Kick"
        except Exception: pass
    if sanction: e.add_field(name="⚡ Sanction auto", value=sanction)
    await interaction.response.send_message(embed=e)
    await log_action(interaction.guild, "Warn", f"**Membre :** {membre}\n**Raison :** {raison}\n**Par :** {interaction.user}", T.ORANGE)
    try:
        await membre.send(embed=mk_embed(f"{T.WARN}  Avertissement reçu",
                                         f"**Serveur :** {interaction.guild.name}\n**Raison :** {raison}\n**Total :** {count}", T.ORANGE))
    except Exception: pass

@bot.tree.command(name="unwarn", description="Retirer un avertissement")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unwarn(interaction: discord.Interaction, membre: discord.Member):
    gid, uid = str(interaction.guild.id), str(membre.id)
    lst = bot.warnings.get(gid, {}).get(uid, [])
    if not lst:
        return await interaction.response.send_message(
            embed=inf("Aucun warn", f"{membre.mention} est clean."), ephemeral=True)
    lst.pop()
    await interaction.response.send_message(embed=ok("Warn retiré", f"{membre.mention} → **{len(lst)}** warn(s)."))

@bot.tree.command(name="warns", description="Voir les avertissements")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def warns(interaction: discord.Interaction, membre: discord.Member = None):
    membre = membre or interaction.user
    lst = bot.warnings.get(str(interaction.guild.id), {}).get(str(membre.id), [])
    if not lst:
        return await interaction.response.send_message(
            embed=inf("Aucun warn", f"{membre.mention} est clean {T.CHECK}"), ephemeral=True)
    e = mk_embed(f"{T.WARN}  Warns de {membre.display_name}", f"**Total :** {len(lst)}", T.ORANGE)
    for i, w in enumerate(lst[-10:], 1):
        e.add_field(name=f"#{i}", value=f"**Raison :** {w['reason']}\n**Date :** {w['date'][:10]}", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="ban", description="Bannir un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.ban(reason=raison)
    await interaction.response.send_message(
        embed=mk_embed(f"{T.BAN}  Banni", f"{membre.mention}\n**Raison :** {raison}", T.RED))
    await log_action(interaction.guild, "Ban", f"**Membre :** {membre}\n**Raison :** {raison}\n**Par :** {interaction.user}", T.RED)

@bot.tree.command(name="unban", description="Débannir un utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur")
@app_commands.default_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(embed=ok("Débanni", str(user)))
    except Exception:
        await interaction.response.send_message(embed=err("Introuvable"), ephemeral=True)

@bot.tree.command(name="kick", description="Expulser un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune"):
    await membre.kick(reason=raison)
    await interaction.response.send_message(
        embed=mk_embed(f"{T.KICK}  Expulsé", f"{membre.mention}\n**Raison :** {raison}", T.ORANGE))
    await log_action(interaction.guild, "Kick", f"**Membre :** {membre}\n**Raison :** {raison}\n**Par :** {interaction.user}", T.ORANGE)

@bot.tree.command(name="mute", description="Mute un membre")
@app_commands.describe(membre="Le membre", duree="Durée en minutes")
@app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, membre: discord.Member, duree: int = 10):
    await membre.timeout(datetime.now(timezone.utc) + timedelta(minutes=duree))
    await interaction.response.send_message(
        embed=mk_embed(f"{T.MUTE}  Muté", f"{membre.mention} — **{duree} min**", T.BLURPLE))

@bot.tree.command(name="unmute", description="Unmute un membre")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, membre: discord.Member):
    await membre.timeout(None)
    await interaction.response.send_message(embed=ok("Unmute", f"{membre.mention}"))

@bot.tree.command(name="rename", description="Renommer un membre")
@app_commands.describe(membre="Le membre", pseudo="Nouveau pseudo")
@app_commands.default_permissions(manage_nicknames=True)
async def rename(interaction: discord.Interaction, membre: discord.Member, pseudo: str):
    old = membre.display_name
    await membre.edit(nick=pseudo)
    await interaction.response.send_message(embed=ok("Renommé", f"`{old}` {T.ARROW} `{pseudo}`"))

@bot.tree.command(name="purge", description="Supprimer des messages")
@app_commands.describe(nombre="Nombre de messages")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, nombre: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=nombre)
    await interaction.followup.send(embed=ok("Purge", f"**{len(deleted)}** messages supprimés."))

# ── Salons ──
@bot.tree.command(name="creersalon", description="Créer un salon texte")
@app_commands.describe(nom="Nom", categorie="Catégorie")
@app_commands.default_permissions(manage_channels=True)
async def creersalon(interaction: discord.Interaction, nom: str, categorie: discord.CategoryChannel = None):
    ch = await interaction.guild.create_text_channel(nom, category=categorie)
    await interaction.response.send_message(embed=ok("Salon créé", ch.mention))

@bot.tree.command(name="creervoice", description="Créer un salon vocal")
@app_commands.describe(nom="Nom", categorie="Catégorie")
@app_commands.default_permissions(manage_channels=True)
async def creervoice(interaction: discord.Interaction, nom: str, categorie: discord.CategoryChannel = None):
    ch = await interaction.guild.create_voice_channel(nom, category=categorie)
    await interaction.response.send_message(embed=ok("Vocal créé", f"🔊 {ch.name}"))

@bot.tree.command(name="supprimersalon", description="Supprimer un salon")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(manage_channels=True)
async def supprimersalon(interaction: discord.Interaction, salon: discord.TextChannel):
    name = salon.name
    await salon.delete()
    await interaction.response.send_message(embed=ok("Supprimé", f"`{name}`"))

@bot.tree.command(name="lock", description="Verrouiller un salon")
@app_commands.describe(salon="Salon (vide = actuel)", bloquer_lecture="Bloquer aussi la lecture")
@app_commands.default_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction, salon: discord.TextChannel = None, bloquer_lecture: bool = False):
    target = salon or interaction.channel
    ow = target.overwrites_for(interaction.guild.default_role)
    ow.send_messages = False
    if bloquer_lecture: ow.view_channel = False
    await target.set_permissions(interaction.guild.default_role, overwrite=ow)
    await interaction.response.send_message(embed=mk_embed("🔒  Verrouillé", target.mention, T.RED))

@bot.tree.command(name="unlock", description="Déverrouiller un salon")
@app_commands.describe(salon="Salon")
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction, salon: discord.TextChannel = None):
    target = salon or interaction.channel
    await target.set_permissions(interaction.guild.default_role, send_messages=True, view_channel=True)
    await interaction.response.send_message(embed=ok("Déverrouillé", target.mention))

@bot.tree.command(name="slowmode", description="Mode lent sur tous les salons")
@app_commands.describe(secondes="Délai en secondes (0 = désactiver)")
@app_commands.default_permissions(administrator=True)
async def slowmode(interaction: discord.Interaction, secondes: int):
    await interaction.response.defer()
    count = errors = 0
    for ch in interaction.guild.text_channels:
        try: await ch.edit(slowmode_delay=secondes); count += 1; await asyncio.sleep(0.3)
        except Exception: errors += 1
    label = f"{secondes}s" if secondes > 0 else "Désactivé"
    await interaction.followup.send(embed=inf(f"⏱️  Slowmode — {label}", f"Salons : {count} | Erreurs : {errors}"))

# ── Rôles ──
@bot.tree.command(name="creerole", description="Créer un rôle")
@app_commands.describe(nom="Nom", couleur="Couleur hex")
@app_commands.default_permissions(manage_roles=True)
async def creerole(interaction: discord.Interaction, nom: str, couleur: str = "#5865F2"):
    role = await interaction.guild.create_role(name=nom, color=discord.Color(int(couleur.replace("#", ""), 16)))
    await interaction.response.send_message(embed=ok("Rôle créé", role.mention))

@bot.tree.command(name="addrole", description="Ajouter un rôle à un membre")
@app_commands.describe(membre="Membre", role="Rôle")
@app_commands.default_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.add_roles(role)
    await interaction.response.send_message(embed=ok("Rôle ajouté", f"{role.mention} {T.ARROW} {membre.mention}"))

@bot.tree.command(name="removerole", description="Retirer un rôle d'un membre")
@app_commands.describe(membre="Membre", role="Rôle")
@app_commands.default_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    await membre.remove_roles(role)
    await interaction.response.send_message(embed=inf("Rôle retiré", f"{role.mention} de {membre.mention}"))

@bot.tree.command(name="roleall", description="Donner un rôle à tous les membres")
@app_commands.describe(role="Rôle")
@app_commands.default_permissions(administrator=True)
async def roleall(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer()
    count = 0
    for m in interaction.guild.members:
        if not m.bot and role not in m.roles:
            try: await m.add_roles(role); count += 1; await asyncio.sleep(0.5)
            except Exception: pass
    await interaction.followup.send(embed=ok("Rôle donné à tous", f"{role.mention} — **{count}** membres"))

@bot.tree.command(name="autorole", description="Rôle automatique aux nouveaux membres")
@app_commands.describe(role="Rôle")
@app_commands.default_permissions(administrator=True)
async def autorole(interaction: discord.Interaction, role: discord.Role):
    bot.auto_roles[str(interaction.guild.id)] = role.id
    await interaction.response.send_message(embed=ok("Auto-rôle configuré", role.mention))

@bot.tree.command(name="rolemenu", description="Menu de sélection de rôles")
@app_commands.describe(titre="Titre", roles="Mentions des rôles")
@app_commands.default_permissions(administrator=True)
async def rolemenu(interaction: discord.Interaction, titre: str, roles: str):
    ids  = re.findall(r'<@&(\d+)>', roles)
    objs = [interaction.guild.get_role(int(i)) for i in ids if interaction.guild.get_role(int(i))]
    if not objs:
        return await interaction.response.send_message(embed=err("Erreur", "Utilise des mentions de rôles."), ephemeral=True)
    e = mk_embed(f"{T.ROLE}  {titre}", "\n".join([f"{T.ARROW} {r.mention}" for r in objs]), T.PINK)
    await interaction.channel.send(embed=e, view=RoleMenuView(objs))
    await interaction.response.send_message(embed=ok("Menu créé !"), ephemeral=True)

# ── Systèmes ──
@bot.tree.command(name="panel", description="Créer un panel de tickets")
@app_commands.describe(titre="Titre", description="Description", role_support="Rôle support")
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction, titre: str = "Support",
                description: str = "Clique pour ouvrir un ticket.", role_support: discord.Role = None):
    bot.ticket_configs[str(interaction.guild.id)] = {"support_role": role_support.id if role_support else None}
    await interaction.channel.send(embed=mk_embed(f"{T.TICKET}  {titre}", description, T.BLURPLE), view=TicketView())
    await interaction.response.send_message(embed=ok("Panel créé !"), ephemeral=True)

@bot.tree.command(name="reglement", description="Envoyer le règlement")
@app_commands.describe(type_reglement="defaut = règles du bot | perso = tu écris toi-même",
                        avec_bouton="Ajouter bouton d'acceptation", role="Rôle donné à l'acceptation")
@app_commands.choices(type_reglement=[
    app_commands.Choice(name="Défaut (règles du bot)", value="defaut"),
    app_commands.Choice(name="Personnalisé (j'écris moi-même)", value="perso"),
])
@app_commands.default_permissions(administrator=True)
async def reglement(interaction: discord.Interaction, type_reglement: str = "defaut",
                    avec_bouton: bool = True, role: discord.Role = None):
    if type_reglement == "perso":
        await interaction.response.send_modal(ReglementModal(avec_bouton, role))
    else:
        if role: bot.verif_roles[str(interaction.guild.id)] = role.id
        rules = [
            (f"{T.DIAMOND}  Respect",     "Respecte tous les membres et le staff."),
            (f"{T.LIGHTNING}  Anti-spam", "Évite de répéter les mêmes messages."),
            (f"{T.STAR}  Publicité",      "Toute pub non autorisée est interdite."),
            (f"{T.CRYSTAL}  Contenu",     "Aucun contenu NSFW, violent ou illégal."),
            (f"{T.CROWN}  Staff",         "Les décisions du staff sont finales."),
            (f"{T.SHIELD}  Respect RGPD", "Ne partage jamais les données personnelles d'autrui."),
        ]
        e = discord.Embed(title=f"{T.SHIELD}  Règlement du serveur", description=T.LINE,
                          color=T.BLURPLE, timestamp=datetime.now(timezone.utc))
        for t, c in rules: e.add_field(name=t, value=c, inline=False)
        await interaction.channel.send(embed=e, view=RulesView() if avec_bouton else None)
        await interaction.response.send_message(embed=ok("Règlement envoyé !"), ephemeral=True)

@bot.tree.command(name="verification", description="Panel de vérification")
@app_commands.describe(role="Rôle à donner", titre="Titre", description="Description")
@app_commands.default_permissions(administrator=True)
async def verification(interaction: discord.Interaction, role: discord.Role = None,
                        titre: str = "Vérification", description: str = "Clique pour te vérifier !"):
    gid = str(interaction.guild.id)
    if not role:
        role = (discord.utils.get(interaction.guild.roles, name="✅ Vérifié") or
                await interaction.guild.create_role(name="✅ Vérifié", color=discord.Color.green()))
    bot.verif_roles[gid] = role.id
    e = mk_embed(f"{T.SHIELD}  {titre}", f"{description}\n\n**Rôle :** {role.mention}", T.BLURPLE)
    await interaction.channel.send(embed=e, view=VerifyView())
    await interaction.response.send_message(embed=ok("Panel créé !"), ephemeral=True)

@bot.tree.command(name="arrivee", description="Configurer le salon des messages de bienvenue")
@app_commands.describe(salon="Salon où envoyer les arrivées")
@app_commands.default_permissions(administrator=True)
async def arrivee(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.arrivee_channels[str(interaction.guild.id)] = salon.id
    await interaction.response.send_message(embed=ok("Arrivées configurées", f"Dans {salon.mention}"))

@bot.tree.command(name="depart", description="Configurer le salon des messages de départ")
@app_commands.describe(salon="Salon où envoyer les départs")
@app_commands.default_permissions(administrator=True)
async def depart(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.depart_channels[str(interaction.guild.id)] = salon.id
    await interaction.response.send_message(embed=ok("Départs configurés", f"Dans {salon.mention}"))

@bot.tree.command(name="giveaway", description="Créer un giveaway")
@app_commands.describe(titre="Titre", prix="Prix", duree_heures="Durée en heures", gagnants="Nombre de gagnants")
@app_commands.default_permissions(administrator=True)
async def giveaway_cmd(interaction: discord.Interaction, titre: str, prix: str,
                        duree_heures: int, gagnants: int = 1):
    await interaction.response.defer()
    end_time = datetime.now(timezone.utc) + timedelta(hours=duree_heures)
    e = discord.Embed(title=f"{T.GIVEAWAY}  {titre.upper()}",
                      description=f"{T.GIFT} **Prix :** {prix}\n{T.LINE}",
                      color=T.GOLD, timestamp=datetime.now(timezone.utc))
    e.add_field(name=f"{T.TROPHY} Gagnants",   value=f"**{gagnants}**", inline=True)
    e.add_field(name=f"{T.STAR} Participants", value=f"**0**",           inline=True)
    e.add_field(name=f"{T.CLOCK} Fin",         value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
    e.set_footer(text=f"Organisé par {interaction.user.display_name}")
    msg = await interaction.channel.send(embed=e)
    mid = str(msg.id)
    bot.giveaways[mid] = {
        "title": titre, "prize": prix, "winners": gagnants,
        "end_time": end_time.isoformat(),
        "channel_id": str(interaction.channel.id),
        "guild_id": str(interaction.guild.id),
        "participants": [], "ended": False
    }
    view = GiveawayView(mid)
    bot.add_view(view)
    await msg.edit(view=view)
    await interaction.followup.send(
        embed=ok("Giveaway créé !", f"**{titre}** — {prix} — {duree_heures}h — {gagnants} gagnant(s)"),
        ephemeral=True)

@bot.tree.command(name="reroll", description="Relancer un giveaway terminé")
@app_commands.describe(message_id="ID du message du giveaway")
@app_commands.default_permissions(administrator=True)
async def reroll(interaction: discord.Interaction, message_id: str):
    g = bot.giveaways.get(message_id)
    if not g:          return await interaction.response.send_message(embed=err("Introuvable"), ephemeral=True)
    if not g.get("ended"): return await interaction.response.send_message(embed=err("En cours"), ephemeral=True)
    p = g.get("participants", [])
    if not p:          return await interaction.response.send_message(embed=err("Aucun participant"), ephemeral=True)
    winners = []
    for wid in random.sample(p, min(g.get("winners", 1), len(p))):
        try: winners.append(await bot.fetch_user(wid))
        except Exception: pass
    if winners:
        await interaction.response.send_message(
            content=" ".join([w.mention for w in winners]),
            embed=mk_embed(f"{T.GIVEAWAY}  Reroll !",
                           f"**Gagnant(s) :** {', '.join([w.mention for w in winners])}\n**Prix :** {g.get('prize')}",
                           T.GOLD))
    else:
        await interaction.response.send_message(embed=err("Erreur reroll"), ephemeral=True)

# ── Poll avec durée ──
@bot.tree.command(name="poll", description="Créer un sondage interactif avec durée")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(
    question="La question du sondage",
    option1="Option 1", option2="Option 2",
    option3="Option 3 (optionnel)", option4="Option 4 (optionnel)", option5="Option 5 (optionnel)",
    duree_minutes="Durée en minutes (0 = sans limite)"
)
async def poll_cmd(interaction: discord.Interaction, question: str, option1: str, option2: str,
                   option3: str = None, option4: str = None, option5: str = None,
                   duree_minutes: int = 0):
    options  = [o for o in [option1, option2, option3, option4, option5] if o]
    end_time = None
    if duree_minutes > 0:
        end_time = datetime.now(timezone.utc) + timedelta(minutes=duree_minutes)

    desc = f"**{question}**\n\n"
    for i, opt in enumerate(options):
        desc += f"{POLL_EMOJIS[i]} **{opt}**\n`░░░░░░░░░░` 0 vote (0%)\n\n"
    desc += f"{T.CHART} **0 vote au total**"
    if end_time:
        desc += f"\n\n{T.CLOCK} Fin : <t:{int(end_time.timestamp())}:R>"

    e = mk_embed(f"{T.POLL}  Sondage", desc, T.BLURPLE)
    e.set_footer(text=f"Sondage par {interaction.user.display_name}"
                       + (f" • Durée : {duree_minutes} min" if duree_minutes > 0 else ""))

    await interaction.response.send_message(embed=e)
    msg    = await interaction.original_response()
    msg_id = str(msg.id)

    poll_data = {
        "question":   question,
        "options":    options,
        "votes":      {},
        "ended":      False,
        "guild_id":   str(interaction.guild.id),
        "channel_id": str(interaction.channel.id),
    }
    if end_time:
        poll_data["end_time"] = end_time.isoformat()

    bot.polls[msg_id] = poll_data
    view = PollView(msg_id, options)
    await msg.edit(view=view)

# ── Infos ──
@bot.tree.command(name="userinfo", description="Informations sur un membre")
@app_commands.describe(membre="Le membre (vide = toi)")
async def userinfo(interaction: discord.Interaction, membre: discord.Member = None):
    m   = membre or interaction.user
    gid = str(interaction.guild.id)
    d   = get_xp(gid, str(m.id))
    roles = [r.mention for r in m.roles if r.name != "@everyone"]
    e = discord.Embed(title=f"{T.INFO}  {m.display_name}", color=m.color or T.BLURPLE,
                      timestamp=datetime.now(timezone.utc))
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="Discord",          value=str(m),                                     inline=True)
    e.add_field(name="ID",               value=f"`{m.id}`",                                inline=True)
    e.add_field(name="Bot",              value=T.CHECK if m.bot else T.CROSS,              inline=True)
    e.add_field(name="Créé le",          value=m.created_at.strftime("%d/%m/%Y"),          inline=True)
    e.add_field(name="Rejoint le",       value=m.joined_at.strftime("%d/%m/%Y") if m.joined_at else "?", inline=True)
    e.add_field(name=f"{T.XP} Niveau",   value=f"**{d['level']}** ({d['xp']} XP)",         inline=True)
    e.add_field(name=f"{T.ROLE} Rôles ({len(roles)})",
                value=" ".join(roles[:10]) or "Aucun", inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="serverinfo", description="Informations sur le serveur")
async def serverinfo(interaction: discord.Interaction):
    g      = interaction.guild
    bots   = sum(1 for m in g.members if m.bot)
    humans = g.member_count - bots
    e = discord.Embed(title=f"{T.INFO}  {g.name}", color=T.BLURPLE, timestamp=datetime.now(timezone.utc))
    if g.icon: e.set_thumbnail(url=g.icon.url)
    e.add_field(name="ID",           value=f"`{g.id}`",                                  inline=True)
    e.add_field(name="Propriétaire", value=g.owner.mention if g.owner else "?",          inline=True)
    e.add_field(name="Créé le",      value=g.created_at.strftime("%d/%m/%Y"),            inline=True)
    e.add_field(name="Membres",      value=f"**{humans}** humains / **{bots}** bots",    inline=True)
    e.add_field(name="Salons",       value=f"**{len(g.text_channels)}** texte / **{len(g.voice_channels)}** vocal", inline=True)
    e.add_field(name="Rôles",        value=f"**{len(g.roles)}**",                        inline=True)
    e.add_field(name="Boosts",       value=f"**{g.premium_subscription_count}** (Niv. {g.premium_tier})", inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="rank", description="Voir son niveau XP")
@app_commands.describe(membre="Le membre (vide = toi)")
async def rank(interaction: discord.Interaction, membre: discord.Member = None):
    m   = membre or interaction.user
    gid = str(interaction.guild.id)
    d   = get_xp(gid, str(m.id))
    lvl, xp_current = d["level"], d["xp"]
    req = xp_for_level(lvl + 1)
    pct = int(xp_current / req * 100) if req > 0 else 0
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
    sorted_users = sorted(bot.xp_data.get(gid, {}).items(),
                          key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
    rank_pos = next((i + 1 for i, (uid, _) in enumerate(sorted_users) if uid == str(m.id)), "?")
    e = discord.Embed(title=f"{T.XP}  Rang de {m.display_name}", color=T.GOLD,
                      timestamp=datetime.now(timezone.utc))
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="Niveau",      value=f"**{lvl}**",               inline=True)
    e.add_field(name="XP",          value=f"**{xp_current}** / {req}", inline=True)
    e.add_field(name="Classement",  value=f"**#{rank_pos}**",          inline=True)
    e.add_field(name="Messages",    value=f"**{d['messages']}**",      inline=True)
    e.add_field(name="Progression", value=f"`{bar}` {pct}%",           inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="top", description="Top 10 XP du serveur")
async def top(interaction: discord.Interaction):
    gid      = str(interaction.guild.id)
    guild_xp = bot.xp_data.get(gid, {})
    if not guild_xp:
        return await interaction.response.send_message(
            embed=inf("Classement vide", "Personne n'a encore de XP."), ephemeral=True)
    sorted_users = sorted(guild_xp.items(),
                          key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"] + [f"**#{i}**" for i in range(4, 11)]
    desc   = ""
    for i, (uid, d) in enumerate(sorted_users):
        member = interaction.guild.get_member(int(uid))
        name   = member.display_name if member else f"ID:{uid}"
        desc  += f"{medals[i]} **{name}** — Niveau {d['level']} ({d['xp']} XP)\n"
    await interaction.response.send_message(embed=mk_embed(f"{T.TROPHY}  Top 10 XP", desc, T.GOLD))

# ── Administration ──
@bot.tree.command(name="setup", description="Setup complet selon un style de serveur")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(style="Style du serveur")
@app_commands.choices(style=[
    app_commands.Choice(name="🌐 Communauté / Discussion", value="communaute"),
    app_commands.Choice(name="🎮 Gaming",                  value="gaming"),
    app_commands.Choice(name="🎭 Jeu de Rôle (RP)",       value="rp"),
    app_commands.Choice(name="📚 Éducation / Études",     value="education"),
    app_commands.Choice(name="🎌 Anime / Manga",           value="anime"),
])
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction, style: str = "communaute"):
    await interaction.response.defer()
    g       = interaction.guild
    config  = SETUP_STRUCTURES[style]
    created = {"roles": 0, "text": 0, "voice": 0}
    for name, color in config["roles"]:
        if not discord.utils.get(g.roles, name=name):
            try: await g.create_role(name=name, color=discord.Color(color)); created["roles"] += 1; await asyncio.sleep(0.3)
            except Exception: pass
    for cat_name, (texts, voices) in config["structure"].items():
        cat = discord.utils.get(g.categories, name=cat_name)
        if not cat:
            try:
                ow  = ({g.default_role: discord.PermissionOverwrite(view_channel=False)}
                       if "STAFF" in cat_name or "MJ" in cat_name else {})
                cat = await g.create_category(cat_name, overwrites=ow)
                await asyncio.sleep(0.3)
            except Exception: continue
        for ch_name in texts:
            if not discord.utils.get(g.text_channels, name=ch_name):
                try: await g.create_text_channel(ch_name, category=cat); created["text"] += 1; await asyncio.sleep(0.3)
                except Exception: pass
        for vc_name in voices:
            if not discord.utils.get(g.voice_channels, name=vc_name):
                try: await g.create_voice_channel(vc_name, category=cat); created["voice"] += 1; await asyncio.sleep(0.3)
                except Exception: pass
    for log_name in ["📊・logs", "logs"]:
        logs_ch = discord.utils.get(g.text_channels, name=log_name)
        if logs_ch: bot.logs_channels[str(g.id)] = logs_ch.id; break
    e = ok(f"Setup terminé ! — {config['label']}")
    e.add_field(name="Rôles",        value=f"**{created['roles']}**", inline=True)
    e.add_field(name="Salons texte", value=f"**{created['text']}**",  inline=True)
    e.add_field(name="Salons vocal", value=f"**{created['voice']}**", inline=True)
    e.add_field(name="Étapes suivantes",
                value="`/arrivee` `/depart` `/panel` `/verification` `/reglement` `/antispam`", inline=False)
    await interaction.followup.send(embed=e)

@bot.tree.command(name="backup", description="Sauvegarder la structure du serveur")
@app_commands.describe(nom="Nom de la sauvegarde")
@app_commands.default_permissions(administrator=True)
async def backup(interaction: discord.Interaction, nom: str = None):
    await interaction.response.defer(ephemeral=True)
    g    = interaction.guild
    name = nom or f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    data = {
        "roles":      [{"name": r.name, "color": r.color.value} for r in g.roles
                       if r.name != "@everyone" and not r.managed],
        "categories": [{"name": c.name} for c in g.categories],
        "text":       [{"name": c.name, "category": c.category.name if c.category else None}
                       for c in g.text_channels],
        "voice":      [{"name": c.name, "category": c.category.name if c.category else None}
                       for c in g.voice_channels],
    }
    bot.backups.setdefault(str(g.id), {})[name] = data
    await interaction.followup.send(
        embed=ok("Sauvegarde créée",
                 f"**{name}**\nRôles : {len(data['roles'])} | Salons : {len(data['text']) + len(data['voice'])}"),
        ephemeral=True)

@bot.tree.command(name="restore", description="Restaurer une sauvegarde")
@app_commands.describe(nom="Nom de la sauvegarde")
@app_commands.default_permissions(administrator=True)
async def restore(interaction: discord.Interaction, nom: str):
    await interaction.response.defer()
    gid  = str(interaction.guild.id)
    data = bot.backups.get(gid, {}).get(nom)
    if not data:
        return await interaction.followup.send(embed=err("Introuvable", f"**{nom}** n'existe pas."))
    restored = {"roles": 0, "channels": 0}
    for r in data.get("roles", []):
        if not discord.utils.get(interaction.guild.roles, name=r["name"]):
            try:
                await interaction.guild.create_role(name=r["name"], color=discord.Color(r.get("color", 0)))
                restored["roles"] += 1; await asyncio.sleep(0.3)
            except Exception: pass
    for c in data.get("categories", []):
        if not discord.utils.get(interaction.guild.categories, name=c["name"]):
            try: await interaction.guild.create_category(c["name"]); await asyncio.sleep(0.3)
            except Exception: pass
    for ch in data.get("text", []):
        if not discord.utils.get(interaction.guild.text_channels, name=ch["name"]):
            try:
                cat = discord.utils.get(interaction.guild.categories, name=ch.get("category"))
                await interaction.guild.create_text_channel(ch["name"], category=cat)
                restored["channels"] += 1; await asyncio.sleep(0.3)
            except Exception: pass
    await interaction.followup.send(
        embed=ok("Restauré !", f"Rôles : **{restored['roles']}** | Salons : **{restored['channels']}**"))

@bot.tree.command(name="antiraid", description="Configurer l'anti-raid")
@app_commands.describe(activer="Activer", seuil="Joins par 10 secondes", action="kick ou ban")
@app_commands.default_permissions(administrator=True)
async def antiraid(interaction: discord.Interaction, activer: bool = True, seuil: int = 5, action: str = "kick"):
    bot.raid_protection[str(interaction.guild.id)] = {"enabled": activer, "threshold": seuil, "action": action}
    await interaction.response.send_message(
        embed=mk_embed(f"{T.SHIELD}  Anti-Raid",
                       f"**Statut :** {'✅' if activer else '❌'}\n**Seuil :** {seuil}/10s\n**Action :** {action}",
                       T.BLURPLE))

@bot.tree.command(name="antispam", description="Configurer l'anti-spam")
@app_commands.describe(activer="Activer", messages="Max messages", temps="En secondes",
                        mentions="Max mentions", action="mute/kick/ban", duree_mute="Minutes de mute")
@app_commands.default_permissions(administrator=True)
async def antispam(interaction: discord.Interaction, activer: bool = True, messages: int = 5,
                    temps: int = 5, mentions: int = 5, action: str = "mute", duree_mute: int = 5):
    bot.antispam_config[str(interaction.guild.id)] = {
        "enabled": activer, "msg_limit": messages, "msg_time": temps,
        "mention_limit": mentions, "action": action, "mute_duration": duree_mute
    }
    await interaction.response.send_message(
        embed=mk_embed(f"{T.SPAM}  Anti-Spam",
                       f"**Statut :** {'✅' if activer else '❌'}\n**Messages :** {messages}/{temps}s\n"
                       f"**Mentions :** {mentions}\n**Action :** {action}", T.BLURPLE))

@bot.tree.command(name="tempvoice", description="Salons vocaux temporaires")
@app_commands.describe(salon="Salon déclencheur")
@app_commands.default_permissions(administrator=True)
async def tempvoice(interaction: discord.Interaction, salon: discord.VoiceChannel):
    bot.temp_voices[str(interaction.guild.id)] = salon.id
    await interaction.response.send_message(
        embed=ok("Vocaux temporaires", f"Rejoins **{salon.name}** pour créer ton salon !"))

# ==================== RUN ====================
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    token = os.environ.get('DISCORD_BOT_TOKEN')
    if token:
        logger.info("⚡ Aegis V8 démarre...")
        bot.run(token)
    else:
        logger.error("❌ DISCORD_BOT_TOKEN manquant !")
