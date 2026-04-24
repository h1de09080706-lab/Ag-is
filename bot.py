"""
╔══════════════════════════════════════════════╗
║           AEGIS V2.1 — Bot Discord           ║
║   Design néon • Anti-protection auto         ║
╚══════════════════════════════════════════════╝
Variables Railway :
  DISCORD_BOT_TOKEN  → token du bot
  GROQ_API_KEY       → clé API groq (gsk_...)
  BOT_OWNER_ID       → ton ID Discord (optionnel)
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, logging, asyncio, random, re, aiohttp
from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import defaultdict

# Lock global anti-doublon (bloque Railway overlap)
_event_lock = asyncio.Lock()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('Aegis')

BOT_OWNER_ID = int(os.environ.get('BOT_OWNER_ID', '0'))

# ══════════════════════════════════════════════
#  THÈME NÉON / GLADOS
# ══════════════════════════════════════════════
class C:
    # Couleurs néon
    NEON_CYAN   = 0x00FFFF
    NEON_PINK   = 0xFF00FF
    NEON_GREEN  = 0x00FF41
    NEON_ORANGE = 0xFF6600
    NEON_RED    = 0xFF0040
    NEON_BLUE   = 0x0080FF
    NEON_GOLD   = 0xFFD700
    DARK        = 0x0D0D0D
    # Aliases
    OK    = NEON_GREEN
    ERR   = NEON_RED
    INFO  = NEON_CYAN
    WARN  = NEON_ORANGE
    MOD   = NEON_PINK
    SYS   = NEON_BLUE

class E:
    OK="✅"; KO="❌"; INFO="◈"; WARN="⚠️"; NUKE="☢️"
    BAN="⛔"; KICK="⚡"; MUTE="🔇"; ROLE="◉"; CHAN="▣"
    MUSIC="♪"; XP="◆"; GOLD="◈"; GIFT="◎"; POLL="▸"
    TICKET="⊠"; AI="◉"; WAVE="◈"; DOOR="◉"; ARROW="►"
    SHIELD="◈"; GEAR="◈"; MEGA="▶"; LINE="─────────────────────"

def emb(title: str, desc: str=None, color: int=C.NEON_CYAN, footer: str=None) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color,
                      timestamp=datetime.now(timezone.utc))
    e.set_footer(text=footer or "AEGIS V2.1  ◈  discord.gg/6rN8pneGdy")
    return e

def ok(t, d=None):   return emb(f"✅  {t}", d, C.NEON_GREEN)
def er(t, d=None):   return emb(f"❌  {t}", d, C.NEON_RED)
def inf(t, d=None):  return emb(f"◈  {t}", d, C.NEON_CYAN)
def warn(t, d=None): return emb(f"⚠️  {t}", d, C.NEON_ORANGE)
def sys_emb(t, d=None): return emb(f"☢️  {t}", d, C.NEON_PINK)

# ══════════════════════════════════════════════
#  BOT
# ══════════════════════════════════════════════
intents = discord.Intents.all()

class Aegis(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!_', intents=intents, help_command=None)
        # Données par serveur
        self.giveaways   = {}
        self.polls       = {}
        self.warnings    = {}
        self.xp_data     = {}
        self.xp_cd       = {}
        self.ai_cd       = {}
        self.vc_pool     = {}
        self.queues      = {}
        self.now_playing = {}
        self.msg_cache   = defaultdict(list)
        self.arrivee     = {}
        self.depart_ch   = {}
        self.auto_roles  = {}
        self.verif_roles = {}
        self.logs_ch     = {}
        self.ticket_cfg  = {}
        self.temp_voices = {}
        self.raid_cfg    = {}
        self.raid_cache  = {}
        self.spam_cfg    = {}
        self.nuke_cfg    = {}
        self.nuke_track  = {}
        self.backups     = {}
        # Guard anti-doublon pour on_member_join/remove
        self._join_cache   = {}   # {gid-uid: timestamp}
        self._remove_cache = {}

    async def setup_hook(self):
        for v in [TicketView(), CloseView(), VerifyView(), RulesView(), ApplyView()]:
            self.add_view(v)
        try:
            n = await self.tree.sync()
            logger.info(f"✅ {len(n)} commandes sync")
        except Exception as e:
            logger.error(f"Sync: {e}")

bot = Aegis()

# ══════════════════════════════════════════════
#  ERROR HANDLER GLOBAL
# ══════════════════════════════════════════════
@bot.tree.error
async def on_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        e = er("Permission refusée", "Tu n'as pas la permission nécessaire pour cette commande.")
    elif isinstance(error, app_commands.BotMissingPermissions):
        e = er("Permission manquante (bot)", f"Le bot manque de permissions.\n`{str(error)[:100]}`")
    else:
        logger.error(f"[{getattr(interaction.command,'name','?')}] {error}")
        e = er("Erreur", f"`{str(error)[:200]}`")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=e, ephemeral=True)
        else:
            await interaction.response.send_message(embed=e, ephemeral=True)
    except Exception:
        pass

# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════
def xp_req(lv): return 100*(lv**2) + 50*lv

def get_xp(gid, uid):
    return bot.xp_data.setdefault(gid, {}).setdefault(uid, {"xp":0,"level":0,"messages":0})

def fmt(s):
    if not s: return "?"
    m, s = divmod(int(s), 60); h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def can_target(actor: discord.Member, target: discord.Member) -> bool:
    if not actor or not target: return False
    if target.id == actor.guild.owner_id: return False
    if target.id == actor.guild.me.id: return False
    ar = getattr(actor, 'top_role', None)
    tr = getattr(target, 'top_role', None)
    if ar is None or tr is None: return True
    return ar > tr

async def log(guild, title, desc, color=C.NEON_CYAN):
    gid = str(guild.id)
    if gid in bot.logs_ch:
        ch = guild.get_channel(bot.logs_ch[gid])
        if ch:
            try: await ch.send(embed=emb(f"◈  {title}", desc, color))
            except: pass

def check_perms(channel, guild_me) -> bool:
    """Vérifie que le bot peut envoyer un embed dans ce salon."""
    perms = channel.permissions_for(guild_me)
    return perms.view_channel and perms.send_messages and perms.embed_links

def default_raid_cfg():  return {"enabled": True,  "threshold": 5,  "action": "kick"}
def default_spam_cfg():  return {"enabled": True,  "limit": 5, "window": 5, "mentions": 5, "action": "mute", "dur": 5}
def default_nuke_cfg():  return {"enabled": True,  "threshold": 5,  "action": "kick", "whitelist": []}

# ══════════════════════════════════════════════
#  GROQ IA  (modèle llama-3.3-70b-versatile)
# ══════════════════════════════════════════════
AI_SYS = (
    "Tu es AEGIS, une IA de bot Discord. Style GLaDOS : intelligent, légèrement sarcastique, "
    "condescendant avec subtilité, mais toujours utile. Tu réponds TOUJOURS en français, "
    "2-3 phrases maximum. Jamais vulgaire."
)

async def ask_groq(q: str) -> str:
    key = os.environ.get('GROQ_API_KEY', '').strip()
    if not key:
        return "*(Configure `GROQ_API_KEY` dans Railway → Variables)*"
    # Modèles à essayer dans l'ordre (en cas de décommission)
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]
    for model in models:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
                r = await s.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={"model": model,
                          "messages": [{"role":"system","content":AI_SYS},
                                       {"role":"user","content":q[:500]}],
                          "max_tokens": 200},
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
                body = await r.json()
                if r.status == 200:
                    return body["choices"][0]["message"]["content"].strip()
                elif r.status == 400 and "decommissioned" in str(body):
                    continue  # Essayer le modèle suivant
                elif r.status == 429:
                    await asyncio.sleep(2); continue
                else:
                    err_msg = body.get('error', {}).get('message', str(r.status))
                    return f"*(Erreur Groq: {err_msg[:80]})*"
        except asyncio.TimeoutError:
            return "*(Délai dépassé)*"
        except Exception as e:
            return f"*(Erreur: {str(e)[:50]})*"
    return "*(Tous les modèles Groq sont indisponibles)*"

# ══════════════════════════════════════════════
#  MUSIQUE
# ══════════════════════════════════════════════
FF = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

async def fetch_track(query: str):
    try:
        import yt_dlp
        opts = {'format':'bestaudio/best','noplaylist':True,'quiet':True,'no_warnings':True,
                'default_search':'ytsearch1','source_address':'0.0.0.0','extractor_retries':3,
                'http_headers':{'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}}
        def _get():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    query if query.startswith('http') else f"ytsearch1:{query}", download=False)
                if info and 'entries' in info:
                    info = info['entries'][0] if info['entries'] else None
                if not info: return None
                return {'title':info.get('title','?'), 'url':info.get('url'),
                        'webpage':info.get('webpage_url',''), 'duration':info.get('duration',0),
                        'thumb':info.get('thumbnail',''), 'src':info.get('webpage_url') or query}
        return await asyncio.get_event_loop().run_in_executor(None, _get)
    except Exception as e:
        logger.error(f"yt-dlp: {e}"); return None

async def next_track(gid: str):
    vc = bot.vc_pool.get(gid)
    q  = bot.queues.get(gid, [])
    if not vc or not vc.is_connected(): bot.vc_pool.pop(gid, None); return
    if not q: bot.now_playing[gid] = None; return
    track = q.pop(0); bot.now_playing[gid] = track
    try:
        fresh = await fetch_track(track.get('src') or track.get('webpage') or track.get('title',''))
        if fresh and fresh.get('url'): track['url'] = fresh['url']
    except: pass
    try:
        src = discord.FFmpegPCMAudio(track['url'], **FF)
        vc.play(discord.PCMVolumeTransformer(src, 0.5),
                after=lambda e: asyncio.run_coroutine_threadsafe(next_track(gid), bot.loop))
    except Exception as e:
        logger.error(f"next_track: {e}")
        if bot.queues.get(gid): await next_track(gid)

# ══════════════════════════════════════════════
#  ANTI-SPAM
# ══════════════════════════════════════════════
async def check_spam(msg: discord.Message) -> bool:
    if msg.author.bot or msg.author.guild_permissions.administrator: return False
    gid = str(msg.guild.id); uid = msg.author.id; now = datetime.now(timezone.utc)
    cfg = bot.spam_cfg.get(gid) or default_spam_cfg()
    if not cfg.get("enabled", True): return False
    bot.msg_cache[uid].append(now)
    bot.msg_cache[uid] = [t for t in bot.msg_cache[uid]
                          if (now - t).total_seconds() < cfg["window"]]
    spam = False; reason = ""
    if len(bot.msg_cache[uid]) > cfg["limit"]:
        spam = True; reason = "Spam messages"
    ments = len(msg.mentions) + len(msg.role_mentions) + (50 if msg.mention_everyone else 0)
    if ments >= cfg["mentions"]:
        spam = True; reason = f"Spam mentions ({ments})"
    if spam:
        try:
            await msg.delete()
            a = cfg["action"]
            if   a == "kick": await msg.author.kick(reason=reason)
            elif a == "ban":  await msg.author.ban(reason=reason)
            else: await msg.author.timeout(now + timedelta(minutes=cfg["dur"]), reason=reason)
            await msg.channel.send(
                embed=warn("Anti-Spam", f"{msg.author.mention} sanctionné — {reason}"),
                delete_after=8)
            bot.msg_cache[uid] = []
            return True
        except: pass
    return False

# ══════════════════════════════════════════════
#  XP
# ══════════════════════════════════════════════
async def add_xp(msg: discord.Message):
    if msg.author.bot or not msg.guild: return
    uid = msg.author.id; gid = str(msg.guild.id); now = datetime.now(timezone.utc)
    last = bot.xp_cd.get(uid)
    if last and (now - last).total_seconds() < 60: return
    bot.xp_cd[uid] = now
    d = get_xp(gid, str(uid))
    d["xp"] += random.randint(15, 25); d["messages"] += 1
    if d["xp"] >= xp_req(d["level"] + 1):
        d["level"] += 1; d["xp"] -= xp_req(d["level"])
        guild = bot.get_guild(int(gid))
        if guild:
            ch = guild.get_channel(bot.logs_ch.get(gid, 0)) or msg.channel
            e = emb(f"◆  Level Up!", f"{msg.author.mention} atteint le **niveau {d['level']}** ◆", C.NEON_GOLD)
            e.set_thumbnail(url=msg.author.display_avatar.url)
            try: await ch.send(embed=e)
            except: pass

# ══════════════════════════════════════════════
#  ANTI-NUKE
# ══════════════════════════════════════════════
async def nuke_check(guild: discord.Guild, uid: int, action: str):
    gid = str(guild.id)
    cfg = bot.nuke_cfg.get(gid) or default_nuke_cfg()
    if not cfg.get("enabled", True): return
    if uid == guild.owner_id: return
    if uid in cfg.get("whitelist", []): return
    if uid == BOT_OWNER_ID: return
    try:
        if uid == guild.me.id: return
    except: pass
    now = datetime.now(timezone.utc)
    tr  = bot.nuke_track.setdefault(gid, {})
    ud  = tr.setdefault(str(uid), {})
    last = ud.get("t")
    if not last or (now - last).total_seconds() > 10:
        ud.clear(); ud["t"] = now
    ud[action] = ud.get(action, 0) + 1
    total = sum(v for k, v in ud.items() if k != "t")
    if total >= cfg.get("threshold", 5):
        member = guild.get_member(uid)
        if member:
            try:
                reason = f"Anti-nuke: {total} actions/10s ({action})"
                if cfg.get("action") == "ban": await guild.ban(member, reason=reason)
                else: await guild.kick(member, reason=reason)
                desc = (f"**Membre :** {member} (`{member.id}`)\n"
                        f"**Déclencheur :** {action} × {total} en 10s\n"
                        f"**Sanction :** {cfg.get('action','kick')}")
                await log(guild, "☢️ Anti-Nuke déclenché", desc, C.NEON_RED)
                tr.pop(str(uid), None)
            except Exception as e: logger.error(f"nuke_check: {e}")

# ══════════════════════════════════════════════
#  GIVEAWAY
# ══════════════════════════════════════════════
class GAView(discord.ui.View):
    def __init__(self, mid): super().__init__(timeout=None); self.add_item(GABtn(mid))

class GABtn(discord.ui.Button):
    def __init__(self, mid):
        super().__init__(label="Participer", style=discord.ButtonStyle.success,
                         custom_id=f"ga_{mid}", emoji="🎉")
        self.mid = mid
    async def callback(self, i: discord.Interaction):
        g = bot.giveaways.get(self.mid)
        if not g: return await i.response.send_message("Introuvable.", ephemeral=True)
        if g.get("ended"): return await i.response.send_message("Terminé.", ephemeral=True)
        uid = i.user.id; p = g.setdefault("p", [])
        if uid in p: p.remove(uid); msg = "❌ Retiré."
        else: p.append(uid); msg = f"✅ Tu participes ! ({len(p)})"
        try:
            em = i.message.embeds[0]
            for idx, f in enumerate(em.fields):
                if "Participants" in f.name:
                    em.set_field_at(idx, name="◎ Participants", value=f"**{len(p)}**", inline=True)
                    break
            await i.message.edit(embed=em)
        except: pass
        await i.response.send_message(msg, ephemeral=True)

@tasks.loop(minutes=1)
async def ga_loop():
    now = datetime.now(timezone.utc)
    for mid, g in list(bot.giveaways.items()):
        if g.get("ended"): continue
        try:
            end = datetime.fromisoformat(g["end"])
            if end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
            if now >= end: await end_ga(mid, g)
        except Exception as e: logger.error(f"ga_loop: {e}")

async def end_ga(mid, g):
    try:
        guild = bot.get_guild(int(g["gid"]))
        if not guild: return
        ch = guild.get_channel(int(g["cid"]))
        if not ch: return
        g["ended"] = True; p = g.get("p", [])
        winners = []
        for wid in (random.sample(p, min(g.get("winners",1), len(p))) if p else []):
            try: winners.append(await bot.fetch_user(wid))
            except: pass
        if winners:
            desc = "\n".join([f"◈ {w.mention}" for w in winners])
            e = emb(f"🎉  Giveaway Terminé",
                    f"**{g['title']}**\n**Prix :** {g['prize']}\n\n{desc}", C.NEON_GOLD)
            ann = discord.Embed(title="🎉  Félicitations !",
                description=f"**{g['title']}**\n**Prix :** {g['prize']}\n**Gagnant(s) :** {' '.join([w.mention for w in winners])}",
                color=C.NEON_GOLD, timestamp=datetime.now(timezone.utc))
        else:
            e = emb(f"🎉  Giveaway Terminé", f"**{g['title']}**\nAucun participant.", C.NEON_RED)
        try:
            msg = await ch.fetch_message(int(mid)); await msg.edit(embed=e, view=None)
        except: pass
        if winners:
            await ch.send(content="@everyone 🎉", embed=ann,
                          allowed_mentions=discord.AllowedMentions(everyone=True))
    except Exception as e: logger.error(f"end_ga: {e}")

# ══════════════════════════════════════════════
#  POLL
# ══════════════════════════════════════════════
PE = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]

class PollView(discord.ui.View):
    def __init__(self, pid, opts):
        super().__init__(timeout=None)
        for i, o in enumerate(opts[:5]): self.add_item(PollBtn(pid, i, o))

class PollBtn(discord.ui.Button):
    def __init__(self, pid, idx, label):
        super().__init__(label=label[:60], style=discord.ButtonStyle.secondary,
                         custom_id=f"poll_{pid}_{idx}", emoji=PE[idx])
        self.idx = idx
    async def callback(self, i: discord.Interaction):
        poll = bot.polls.get(str(i.message.id))
        if not poll: return await i.response.send_message("Sondage introuvable.", ephemeral=True)
        if poll.get("ended"): return await i.response.send_message("Sondage terminé.", ephemeral=True)
        uid = str(i.user.id); votes = poll.setdefault("v", {})
        if votes.get(uid) == self.idx: del votes[uid]; msg = "❌ Vote retiré."
        else: votes[uid] = self.idx; msg = f"✅ Voté pour **{poll['opts'][self.idx]}** !"
        await i.response.send_message(msg, ephemeral=True)
        try: await _poll_update(i.message, poll)
        except Exception as e: logger.error(f"poll: {e}")

async def _poll_update(msg, poll):
    opts = poll["opts"]; c = [0] * len(opts)
    for v in poll.get("v", {}).values():
        try:
            v = int(v)
            if 0 <= v < len(c): c[v] += 1
        except: pass
    tot = sum(c); desc = f"**{poll['q']}**\n\n"
    for idx, o in enumerate(opts):
        pct = int(c[idx]/tot*100) if tot > 0 else 0
        bar = "█"*(pct//10) + "░"*(10-pct//10)
        desc += f"{PE[idx]} **{o}**\n`{bar}` {c[idx]} vote{'s' if c[idx]!=1 else ''} ({pct}%)\n\n"
    desc += f"▸ **{tot} vote{'s' if tot!=1 else ''} au total**"
    if poll.get("end"):
        end = datetime.fromisoformat(poll["end"])
        desc += f"\n\n⏰ Fin : <t:{int(end.timestamp())}:R>"
    await msg.edit(embed=emb(f"▸  Sondage", desc, C.NEON_CYAN))

async def _poll_results(poll):
    opts = poll["opts"]; c = [0] * len(opts)
    for v in poll.get("v", {}).values():
        try:
            v = int(v)
            if 0 <= v < len(c): c[v] += 1
        except: pass
    tot = sum(c); mx = max(c) if c else 0
    win = [opts[idx] for idx, x in enumerate(c) if x == mx and mx > 0]
    desc = f"**{poll['q']}**\n\n"
    for idx, o in enumerate(opts):
        pct = int(c[idx]/tot*100) if tot > 0 else 0
        bar = "█"*(pct//10) + "░"*(10-pct//10)
        crown = " 👑" if o in win else ""
        desc += f"{PE[idx]} **{o}**{crown}\n`{bar}` {c[idx]} vote{'s' if c[idx]!=1 else ''} ({pct}%)\n\n"
    desc += f"▸ **{tot} vote{'s' if tot!=1 else ''} au total**"
    e = emb(f"▸  Résultats du sondage", desc, C.NEON_GOLD)
    if win and mx > 0: e.add_field(name="🏆 Gagnant(s)", value=" / ".join(win))
    return e

@tasks.loop(seconds=30)
async def poll_loop():
    now = datetime.now(timezone.utc)
    for mid, poll in list(bot.polls.items()):
        if poll.get("ended") or not poll.get("end"): continue
        try:
            end = datetime.fromisoformat(poll["end"])
            if end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
            if now >= end: await end_poll(mid, poll)
        except Exception as e: logger.error(f"poll_loop: {e}")

async def end_poll(mid, poll):
    try:
        guild = bot.get_guild(int(poll["gid"]))
        if not guild: return
        ch = guild.get_channel(int(poll["cid"]))
        if not ch: return
        poll["ended"] = True
        try:
            msg = await ch.fetch_message(int(mid))
            await msg.edit(embed=await _poll_results(poll), view=None)
        except: pass
        res = await _poll_results(poll)
        res.set_footer(text=f"{len(poll.get('v',{}))} votant(s)  ◈  AEGIS V2.1")
        await ch.send(content="@everyone ▸ **Sondage terminé !**", embed=res,
                      allowed_mentions=discord.AllowedMentions(everyone=True))
    except Exception as e: logger.error(f"end_poll: {e}")

# ══════════════════════════════════════════════
#  VIEWS PERSISTANTES
# ══════════════════════════════════════════════
class TicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(TicketBtn())

class TicketBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Ouvrir un ticket", style=discord.ButtonStyle.blurple,
                         custom_id="ticket_open", emoji="🎫")
    async def callback(self, i: discord.Interaction):
        gid = str(i.guild.id); cfg = bot.ticket_cfg.get(gid, {})
        name = f"ticket-{i.user.name.lower()[:20]}"
        if discord.utils.get(i.guild.text_channels, name=name):
            return await i.response.send_message("Tu as déjà un ticket ouvert.", ephemeral=True)
        await i.response.defer(ephemeral=True)
        try:
            cat = discord.utils.get(i.guild.categories, name="⊠ Tickets") or \
                  await i.guild.create_category("⊠ Tickets", overwrites={
                      i.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                      i.guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)})
            ow = {i.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                  i.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
                  i.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)}
            if cfg.get("sr"):
                sr = i.guild.get_role(cfg["sr"])
                if sr: ow[sr] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            ch = await i.guild.create_text_channel(name, category=cat, overwrites=ow)
            e = emb(f"⊠  Ticket", f"Bienvenue {i.user.mention}\nDécris ton problème.", C.NEON_CYAN)
            await ch.send(embed=e, view=CloseView())
            await i.followup.send(f"✅ Ticket créé : {ch.mention}", ephemeral=True)
        except Exception as ex:
            await i.followup.send(f"❌ Erreur : {str(ex)[:100]}", ephemeral=True)

class CloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.danger,
                       custom_id="ticket_close", emoji="🔐")
    async def close(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.send_message("Fermeture dans 5 secondes...")
        await asyncio.sleep(5)
        try: await i.channel.delete()
        except: pass

class VerifyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Se vérifier", style=discord.ButtonStyle.success,
                       custom_id="verify", emoji="✅")
    async def verify(self, i: discord.Interaction, b: discord.ui.Button):
        gid = str(i.guild.id); rid = bot.verif_roles.get(gid)
        role = i.guild.get_role(rid) if rid else None
        if not role:
            for n in ["Vérifié","✅ Vérifié","Membre"]:
                role = discord.utils.get(i.guild.roles, name=n)
                if role: break
        if not role:
            try:
                role = await i.guild.create_role(name="✅ Vérifié", color=discord.Color(C.NEON_GREEN))
                bot.verif_roles[gid] = role.id
            except:
                return await i.response.send_message("❌ Erreur création rôle.", ephemeral=True)
        if role in i.user.roles:
            return await i.response.send_message("Déjà vérifié !", ephemeral=True)
        try:
            await i.user.add_roles(role)
            await i.response.send_message(f"✅ Vérifié ! Rôle {role.mention} attribué.", ephemeral=True)
        except:
            await i.response.send_message("❌ Erreur permissions.", ephemeral=True)

class RulesView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="J'accepte", style=discord.ButtonStyle.success,
                       custom_id="rules_accept", emoji="✅")
    async def accept(self, i: discord.Interaction, b: discord.ui.Button):
        gid = str(i.guild.id); rid = bot.verif_roles.get(gid)
        role = i.guild.get_role(rid) if rid else None
        if not role:
            for n in ["Membre","Vérifié","✅ Vérifié"]:
                role = discord.utils.get(i.guild.roles, name=n)
                if role: break
        if role:
            try:
                await i.user.add_roles(role)
                await i.response.send_message(f"✅ Règlement accepté ! {role.mention}", ephemeral=True)
            except:
                await i.response.send_message("⚠️ Erreur permissions.", ephemeral=True)
        else:
            await i.response.send_message("✅ Règlement accepté !", ephemeral=True)

class ApplyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Postuler", style=discord.ButtonStyle.success,
                       custom_id="apply")
    async def apply(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.send_modal(ApplyModal())

class ApplyModal(discord.ui.Modal, title="📝 Candidature"):
    pseudo = discord.ui.TextInput(label="Pseudo", max_length=50)
    age    = discord.ui.TextInput(label="Âge", max_length=3)
    motiv  = discord.ui.TextInput(label="Motivation", style=discord.TextStyle.paragraph, max_length=500)
    async def on_submit(self, i: discord.Interaction):
        e = emb("✨  Candidature", color=C.NEON_PINK)
        e.add_field(name="Pseudo", value=self.pseudo.value, inline=True)
        e.add_field(name="Âge",    value=self.age.value,    inline=True)
        e.add_field(name="Discord",value=i.user.mention,    inline=True)
        e.add_field(name="Motivation", value=self.motiv.value, inline=False)
        e.set_thumbnail(url=i.user.display_avatar.url)
        ch = discord.utils.get(i.guild.text_channels, name="candidatures")
        if ch: await ch.send(embed=e)
        await i.response.send_message("✅ Candidature envoyée !", ephemeral=True)

class SuggView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="👍 Approuver", style=discord.ButtonStyle.success, custom_id="sugg_ok")
    async def approve(self, i: discord.Interaction, b: discord.ui.Button):
        if not i.user.guild_permissions.manage_messages:
            return await i.response.send_message("Permission refusée.", ephemeral=True)
        e = i.message.embeds[0]; e.color = C.NEON_GREEN; e.title = "✅  Approuvée"
        e.set_footer(text=f"Approuvé par {i.user.display_name}")
        await i.message.edit(embed=e, view=None)
        await i.response.send_message("Approuvée !", ephemeral=True)
    @discord.ui.button(label="👎 Refuser", style=discord.ButtonStyle.danger, custom_id="sugg_ko")
    async def refuse(self, i: discord.Interaction, b: discord.ui.Button):
        if not i.user.guild_permissions.manage_messages:
            return await i.response.send_message("Permission refusée.", ephemeral=True)
        e = i.message.embeds[0]; e.color = C.NEON_RED; e.title = "❌  Refusée"
        e.set_footer(text=f"Refusé par {i.user.display_name}")
        await i.message.edit(embed=e, view=None)
        await i.response.send_message("Refusée.", ephemeral=True)

class RoleMenu(discord.ui.Select):
    def __init__(self, roles):
        opts = [discord.SelectOption(label=r.name, value=str(r.id), emoji="📝") for r in roles[:25]]
        super().__init__(placeholder="Choisis tes rôles...", min_values=0,
                         max_values=len(opts), options=opts, custom_id="rolemenu")
    async def callback(self, i: discord.Interaction):
        sel = [int(v) for v in self.values]; added = []; removed = []
        for o in self.options:
            r = i.guild.get_role(int(o.value))
            if r:
                if int(o.value) in sel and r not in i.user.roles:
                    await i.user.add_roles(r); added.append(r.name)
                elif int(o.value) not in sel and r in i.user.roles:
                    await i.user.remove_roles(r); removed.append(r.name)
        parts = []
        if added:   parts.append(f"✅ Ajouté : {', '.join(added)}")
        if removed: parts.append(f"❌ Retiré : {', '.join(removed)}")
        await i.response.send_message("\n".join(parts) or "Aucun changement", ephemeral=True)

class RoleMenuView(discord.ui.View):
    def __init__(self, roles): super().__init__(timeout=None); self.add_item(RoleMenu(roles))

class ReglModal(discord.ui.Modal, title="✍️ Règlement"):
    contenu = discord.ui.TextInput(label="Règlement", style=discord.TextStyle.paragraph, max_length=2000)
    def __init__(self, btn, role): super().__init__(); self.btn = btn; self.role = role
    async def on_submit(self, i: discord.Interaction):
        if self.role: bot.verif_roles[str(i.guild.id)] = self.role.id
        e = discord.Embed(title="◈  Règlement", description=self.contenu.value,
                          color=C.NEON_CYAN, timestamp=datetime.now(timezone.utc))
        await i.response.defer(ephemeral=True)
        await i.channel.send(embed=e, view=RulesView() if self.btn else None)
        await i.followup.send(embed=ok("Règlement envoyé !"), ephemeral=True)

# ══════════════════════════════════════════════
#  SETUPS
# ══════════════════════════════════════════════
SETUPS = {
    "communaute": {"label":"🌐 Communauté","roles":[
        ("━━ STAFF ━━",0x2B2D31),("👑 Fondateur",C.NEON_PINK),("⚔️ Admin",0xE74C3C),
        ("🛡️ Modérateur",C.NEON_CYAN),("🤝 Helper",C.NEON_GREEN),("━━ MEMBRES ━━",0x2B2D31),
        ("💎 VIP",C.NEON_GOLD),("🔥 Actif",0xE74C3C),("✅ Vérifié",C.NEON_GREEN),("🎮 Membre",0x95A5A6)],
    "struct":{"📌 IMPORTANT":(["📜・règles","📢・annonces"],[]),
              "👋 ACCUEIL":(["👋・bienvenue","🚪・départs","✅・vérification","📝・présentation"],[]),
              "💬 GÉNÉRAL":(["💬・général","🖼️・médias","🤖・bot-commands"],["🔊 Général","🎵 Musique"]),
              "🎉 EVENTS":(["📊・sondages","🎁・giveaways"],[]),
              "📩 SUPPORT":(["❓・aide","💡・suggestions"],[]),
              "🔒 STAFF":(["📋・staff-chat","📊・logs"],["🔒 Staff"]),
              "🎫 Tickets":([],[])}},
    "gaming": {"label":"🎮 Gaming","roles":[
        ("━━ STAFF ━━",0x2B2D31),("👑 Fondateur",C.NEON_PINK),("⚔️ Admin",0xE74C3C),
        ("🛡️ Modérateur",C.NEON_CYAN),("━━ RANGS ━━",0x2B2D31),
        ("🏆 Légende",C.NEON_GOLD),("🔥 Tryhard",0xE74C3C),("🎮 Casual",0x95A5A6),("✅ Vérifié",C.NEON_GREEN)],
    "struct":{"📌 IMPORTANT":(["📜・règles","📢・annonces"],[]),
              "👋 ACCUEIL":(["👋・bienvenue","🚪・départs","✅・vérification"],[]),
              "🎮 GAMING":(["🎮・général","📸・clips","🏆・tournois"],["🎮 Gaming 1","🎮 Gaming 2","🎮 Gaming 3"]),
              "🎵 MUSIQUE":(["🎵・playlist"],["🎵 Musique"]),
              "🎉 EVENTS":(["🎁・giveaways","📊・sondages"],[]),
              "📩 SUPPORT":(["❓・aide","💡・suggestions"],[]),
              "🔒 STAFF":(["📋・staff-chat","📊・logs"],["🔒 Staff"]),
              "🎫 Tickets":([],[])}},
    "rp": {"label":"🎭 Jeu de Rôle","roles":[
        ("━━ STAFF ━━",0x2B2D31),("👑 Maître du Jeu",C.NEON_PINK),("⚔️ Modo RP",0xE74C3C),
        ("━━ GRADES ━━",0x2B2D31),("🔮 Légende",C.NEON_GOLD),("⚔️ Héros",0xE74C3C),
        ("🗡️ Aventurier",C.NEON_CYAN),("🌱 Novice",C.NEON_GREEN),("✅ Vérifié",C.NEON_GREEN)],
    "struct":{"📌 IMPORTANT":(["📜・règles-rp","📢・annonces","📖・lore"],[]),
              "👋 ACCUEIL":(["👋・arrivées","🚪・départs","✅・vérification","📝・fiches-perso"],[]),
              "🏙️ LIEUX":(["🏙️・ville","🌲・forêt","🏰・château","🍺・taverne"],["🎭 RP Vocal 1","🎭 RP Vocal 2"]),
              "💬 HORS-JEU":(["💬・général-hj","💡・suggestions"],["🔊 Hors-Jeu"]),
              "🔒 STAFF":(["📋・staff-chat","📊・logs"],["🔒 Staff MJ"]),
              "🎫 Tickets":([],[])}},
    "education": {"label":"📚 Éducation","roles":[
        ("━━ STAFF ━━",0x2B2D31),("👑 Admin",C.NEON_PINK),("📚 Modérateur",C.NEON_CYAN),
        ("━━ NIVEAUX ━━",0x2B2D31),("🎓 Diplômé",C.NEON_GOLD),("📖 Étudiant",0xE74C3C),
        ("🌱 Débutant",C.NEON_GREEN),("✅ Vérifié",C.NEON_GREEN)],
    "struct":{"📌 IMPORTANT":(["📜・règles","📢・annonces"],[]),
              "👋 ACCUEIL":(["👋・arrivées","🚪・départs","✅・vérification"],[]),
              "📚 ÉTUDES":(["📖・général","🔢・maths","💻・info","🌍・langues","🔬・sciences"],["📚 Révisions 1","📚 Révisions 2"]),
              "🤝 ENTRAIDE":(["🆘・aide","💡・astuces"],["🤝 Tutorat"]),
              "💬 DÉTENTE":(["💬・général"],["🔊 Détente"]),
              "🔒 STAFF":(["📋・staff-chat","📊・logs"],["🔒 Staff"]),
              "🎫 Tickets":([],[])}},
    "anime": {"label":"🎌 Anime/Manga","roles":[
        ("━━ STAFF ━━",0x2B2D31),("👑 Fondateur",C.NEON_PINK),("⚔️ Admin",0xE74C3C),
        ("🛡️ Modérateur",C.NEON_CYAN),("━━ FANS ━━",0x2B2D31),
        ("🌟 Otaku Légendaire",C.NEON_GOLD),("📖 Lecteur",C.NEON_GREEN),
        ("🎌 Weeaboo",C.NEON_PINK),("✅ Vérifié",C.NEON_GREEN)],
    "struct":{"📌 IMPORTANT":(["📜・règles","📢・annonces"],[]),
              "👋 ACCUEIL":(["👋・bienvenue","🚪・départs","✅・vérification"],[]),
              "🎌 ANIME":(["💬・général","🔥・watching","⭐・recommandations","📸・fan-art"],[]),
              "📖 MANGA":(["📖・manga","🆕・chapitres"],[]),
              "🎵 WEEB":(["🎵・musique"],["🔊 Général","🎵 Weeb Music"]),
              "🎉 EVENTS":(["📊・sondages","🎁・giveaways"],[]),
              "🔒 STAFF":(["📋・staff-chat","📊・logs"],["🔒 Staff"]),
              "🎫 Tickets":([],[])}},
}

# ══════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════
@bot.event
async def on_ready():
    logger.info(f"⚡ {bot.user} | {len(bot.guilds)} serveurs")
    if not ga_loop.is_running():   ga_loop.start()
    if not poll_loop.is_running(): poll_loop.start()
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="◈ /aide | AEGIS V2.1"))
    try:
        await bot.application.edit(description=(
            "AEGIS V2.1 — Bot Discord multifonction\n\n"
            "Protection : Anti-nuke, Anti-raid, Anti-spam\n"
            "Fonctions : XP, Musique, IA Groq, Tickets, Giveaway, Sondages\n\n"
            "Support : https://discord.gg/6rN8pneGdy\n\n"
            "Pour m'ajouter a votre serveur, utilisez ce lien :\n"
            "https://discord.com/oauth2/authorize?client_id=1405641065989406773&permissions=8&integration_type=0&scope=bot"
        ))
    except Exception as e: logger.warning(f"Bio: {e}")

# Guard pour on_guild_join (anti-doublon Railway)
_joined_guilds: dict = {}  # {guild_id: timestamp}

@bot.event
async def on_guild_join(guild: discord.Guild):
    """Message de bienvenue + activation automatique des protections quand Aegis rejoint un serveur."""
    now = datetime.now(timezone.utc)
    last = _joined_guilds.get(guild.id)
    if last and (now - last).total_seconds() < 60: return  # 60s de cooldown
    _joined_guilds[guild.id] = now
    gid = str(guild.id)
    # Activer automatiquement les protections par défaut
    if gid not in bot.raid_cfg:  bot.raid_cfg[gid]  = default_raid_cfg()
    if gid not in bot.spam_cfg:  bot.spam_cfg[gid]  = default_spam_cfg()
    if gid not in bot.nuke_cfg:  bot.nuke_cfg[gid]  = default_nuke_cfg()
    # Trouver un salon où envoyer le message
    ch = None
    if guild.system_channel: ch = guild.system_channel
    if not ch:
        for c in guild.text_channels:
            perms = c.permissions_for(guild.me)
            if perms.send_messages and perms.embed_links:
                ch = c; break
    if not ch: return
    e = discord.Embed(
        title="◈  AEGIS — Système en ligne",
        description=(
            "Bonjour. Je suis **AEGIS**, votre système de sécurité et de gestion Discord.\n\n"
            f"{E.LINE}\n\n"
            "**Ce que je peux faire :**\n"
            "▸ **Modération** — ban, kick, mute, warn, purge...\n"
            "▸ **Protection** — anti-raid, anti-spam, anti-nuke\n"
            "▸ **Systèmes** — tickets, vérification, giveaway, sondages\n"
            "▸ **XP & Stats** — niveaux, classement, profils\n"
            "▸ **Musique** — lecture YouTube, file d'attente\n"
            "▸ **IA** — parle-moi en écrivant **aegis** dans un message\n\n"
            f"{E.LINE}\n\n"
            "**☢️ Protections activées automatiquement :**\n"
            "▸ **Anti-raid** — kicks/bans en masse détectés et neutralisés\n"
            "▸ **Anti-spam** — messages répétitifs bloqués\n"
            "▸ **Anti-nuke** — tentatives de destruction du serveur stoppées\n\n"
            "⚠️ Pour configurer : `/antiraid` `/antispam` `/antinuke`\n"
            "Pour tout voir : `/aide`\n\n"
            f"{E.LINE}\n"
            "*Le protocole de sécurité est en ligne. Bonne chance.*"
        ),
        color=C.NEON_CYAN,
        timestamp=datetime.now(timezone.utc)
    )
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.set_footer(text="AEGIS V2.1  ◈  discord.gg/6rN8pneGdy")
    try: await ch.send(embed=e)
    except: pass

@bot.event
async def on_member_join(member: discord.Member):
    gid = str(member.guild.id); now = datetime.now(timezone.utc)
    # Guard anti-doublon strict (Railway overlap)
    key = f"join-{gid}-{member.id}"
    async with _event_lock:
        last = bot._join_cache.get(key)
        if last and (now - last).total_seconds() < 30: return
        bot._join_cache[key] = now
    if len(bot._join_cache) > 500:
        bot._join_cache.clear()
    # Anti-raid
    bot.raid_cache.setdefault(gid, []).append(now)
    bot.raid_cache[gid] = [t for t in bot.raid_cache[gid] if (now-t).total_seconds() < 10]
    raid = bot.raid_cfg.get(gid) or default_raid_cfg()
    if raid.get("enabled") and len(bot.raid_cache[gid]) > raid.get("threshold", 5):
        try:
            if raid.get("action") == "ban": await member.ban(reason="Anti-raid")
            else: await member.kick(reason="Anti-raid")
        except: pass
        return
    # Auto-roles
    rids = bot.auto_roles.get(gid, [])
    if isinstance(rids, int): rids = [rids]
    for rid in rids:
        r = member.guild.get_role(rid)
        if r:
            try: await member.add_roles(r)
            except: pass
    # Message bienvenue
    if gid in bot.arrivee:
        ch = member.guild.get_channel(bot.arrivee[gid])
        if ch:
            count = member.guild.member_count or 0
            e = discord.Embed(
                title=f"◈  Bienvenue sur {member.guild.name}",
                description=(
                    f"▸ **Membre :** {member.mention}\n"
                    f"▸ **Compte créé le :** {member.created_at.strftime('%d/%m/%Y')}\n"
                    f"▸ **Membre numéro :** `#{count}`"
                ),
                color=C.NEON_CYAN, timestamp=now)
            e.set_thumbnail(url=member.display_avatar.url)
            e.set_footer(text=f"{member.guild.name}  ◈  {count} membres")
            try: await ch.send(embed=e)
            except: pass

@bot.event
async def on_member_remove(member: discord.Member):
    gid = str(member.guild.id); now = datetime.now(timezone.utc)
    key = f"remove-{gid}-{member.id}"
    async with _event_lock:
        last = bot._remove_cache.get(key)
        if last and (now - last).total_seconds() < 30: return
        bot._remove_cache[key] = now
    if len(bot._remove_cache) > 500:
        bot._remove_cache.clear()
    if gid in bot.depart_ch:
        ch = member.guild.get_channel(bot.depart_ch[gid])
        if ch:
            roles = [r.mention for r in member.roles if r.name != "@everyone"]
            dur = ""
            if member.joined_at:
                d = datetime.now(timezone.utc) - member.joined_at.replace(tzinfo=timezone.utc)
                dur = f"{d.days} jour{'s' if d.days!=1 else ''}"
            e = discord.Embed(
                title=f"◈  Au revoir",
                description=(
                    f"▸ **Membre :** {member.mention} (`{member}`)\n"
                    f"▸ **Resté :** {dur or '?'}\n"
                    f"▸ **Rôles :** {', '.join(roles) if roles else 'Aucun'}"
                ),
                color=C.NEON_RED, timestamp=now)
            e.set_thumbnail(url=member.display_avatar.url)
            e.set_footer(text=f"{member.guild.member_count} membres restants  ◈  AEGIS V2.1")
            try: await ch.send(embed=e)
            except: pass

@bot.event
async def on_voice_state_update(member, before, after):
    gid = str(member.guild.id)
    if gid in bot.temp_voices:
        if after.channel and after.channel.id == bot.temp_voices[gid]:
            try:
                nc = await member.guild.create_voice_channel(
                    f"◈ {member.display_name}", category=after.channel.category)
                await member.move_to(nc)
            except: pass
    if (before.channel and before.channel.name.startswith("◈ ")
            and len(before.channel.members) == 0):
        try: await before.channel.delete()
        except: pass

@bot.event
async def on_member_ban(guild, user):
    try:
        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                await nuke_check(guild, entry.user.id, "ban"); break
    except: pass

@bot.event
async def on_guild_channel_delete(channel):
    try:
        await asyncio.sleep(0.5)
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            await nuke_check(channel.guild, entry.user.id, "ch_del"); break
    except: pass

@bot.event
async def on_guild_role_delete(role):
    try:
        await asyncio.sleep(0.5)
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            await nuke_check(role.guild, entry.user.id, "role_del"); break
    except: pass

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    if message.guild:
        if await check_spam(message): return
        await add_xp(message)
    # IA — une seule condition (bot_mentioned exclut name_mentioned)
    bot_mentioned  = bot.user in (message.mentions or [])
    name_mentioned = "aegis" in message.content.lower() and not bot_mentioned
    if message.guild and (bot_mentioned or name_mentioned):
        uid = message.author.id; now = datetime.now(timezone.utc)
        last = bot.ai_cd.get(uid)
        if last and (now - last).total_seconds() < 5:
            await bot.process_commands(message); return
        bot.ai_cd[uid] = now
        q = message.content
        if bot_mentioned:    q = re.sub(r'<@!?\d+>', '', q).strip()
        elif name_mentioned: q = re.sub(r'(?i)\baegis\b[,\s]*', '', q, count=1).strip()
        if len(q) < 2: q = "Bonjour !"
        async with message.channel.typing():
            rep = await ask_groq(q)
        try: await message.reply(f"◉ {rep}")
        except: pass
        return
    await bot.process_commands(message)

# ══════════════════════════════════════════════
#  COMMANDES
# ══════════════════════════════════════════════

@bot.tree.command(name="aide", description="Liste de toutes les commandes")
async def aide(i: discord.Interaction):
    e = discord.Embed(
        title="◈  AEGIS V2.1 — Commandes",
        description="Système de bot Discord avancé",
        color=C.NEON_CYAN, timestamp=datetime.now(timezone.utc))
    e.add_field(name="⛔  Modération",   value="`/ban` `/unban` `/kick` `/mute` `/unmute` `/warn` `/unwarn` `/warns` `/rename` `/purge`", inline=False)
    e.add_field(name="▣  Salons",        value="`/creersalon` `/creervoice` `/supprimersalon` `/lock` `/unlock` `/slowmode`", inline=False)
    e.add_field(name="◉  Rôles",         value="`/creerole` `/addrole` `/removerole` `/roleall` `/autorole` `/rolemenu`", inline=False)
    e.add_field(name="⚙️  Systèmes",     value="`/panel` `/reglement` `/verification` `/giveaway` `/reroll` `/poll` `/suggestion`", inline=False)
    e.add_field(name="◈  Membres",       value="`/arrivee` `/depart` `/backup` `/restore` `/antiraid` `/antispam` `/antinuke` `/setup` `/tempvoice`", inline=False)
    e.add_field(name="♪  Musique",       value="`/play` `/pause` `/resume` `/skip` `/stop` `/queue` `/nowplaying` `/volume`", inline=False)
    e.add_field(name="◆  XP & Stats",    value="`/rank` `/top` `/userinfo` `/serverinfo` `/avatar`", inline=False)
    e.add_field(name="▶  Divers",        value="`/dire` `/embed` `/sondage-rapide` `/tirage` `/dmall`", inline=False)
    e.add_field(name="◉  IA",            value="Écris **aegis** dans un message ou mentionne **@Aegis**", inline=False)
    e.set_footer(text="AEGIS V2.1  ◈  discord.gg/6rN8pneGdy")
    await i.response.send_message(embed=e)

@bot.tree.command(name="ping", description="Latence du bot")
async def ping(i: discord.Interaction):
    await i.response.send_message(embed=inf("Pong !", f"⚡ `{round(bot.latency*1000)} ms`"))

@bot.tree.command(name="dire", description="Faire parler le bot")
@app_commands.describe(message="Le message", salon="Salon cible (vide = actuel)")
@app_commands.default_permissions(manage_messages=True)
async def dire(i: discord.Interaction, message: str, salon: Optional[discord.TextChannel]=None):
    target = salon or i.channel
    perms  = target.permissions_for(i.guild.me)
    if not perms.view_channel or not perms.send_messages:
        return await i.response.send_message(
            embed=er("Accès refusé", f"Je n'ai pas accès à {target.mention}."), ephemeral=True)
    await i.response.defer(ephemeral=True)
    await target.send(message)
    await i.followup.send(embed=ok("Envoyé", f"Dans {target.mention}"), ephemeral=True)

@bot.tree.command(name="embed", description="Envoyer un embed personnalisé")
@app_commands.describe(
    titre="Titre de l'embed",
    contenu="Contenu de l'embed",
    couleur="Couleur hex (ex: #FF00FF)",
    salon="Salon cible (vide = actuel)",
    image="URL d'une image ou GIF à afficher (optionnel)",
    miniature="URL d'une miniature en haut à droite (optionnel)")
@app_commands.default_permissions(manage_messages=True)
async def embed_cmd(i: discord.Interaction, titre: str, contenu: str,
                    couleur: str="#00FFFF", salon: Optional[discord.TextChannel]=None,
                    image: Optional[str]=None, miniature: Optional[str]=None):
    target = salon or i.channel
    perms  = target.permissions_for(i.guild.me)
    if not perms.view_channel or not perms.send_messages or not perms.embed_links:
        return await i.response.send_message(
            embed=er("Accès refusé", f"Je n'ai pas accès à {target.mention}."), ephemeral=True)
    try: color = int(couleur.replace("#",""), 16)
    except: color = C.NEON_CYAN
    await i.response.defer(ephemeral=True)
    e = discord.Embed(title=titre, description=contenu, color=color, timestamp=datetime.now(timezone.utc))
    e.set_footer(text=f"Par {i.user.display_name}  ◈  AEGIS V2.1")
    if image:      e.set_image(url=image)
    if miniature:  e.set_thumbnail(url=miniature)
    await target.send(embed=e)
    await i.followup.send(embed=ok("Envoyé !", f"Dans {target.mention}"), ephemeral=True)

@bot.tree.command(name="sondage-rapide", description="Sondage Oui/Non rapide")
@app_commands.describe(question="Ta question")
async def sondage_rapide(i: discord.Interaction, question: str):
    e = emb(f"▸  Sondage rapide", f"**{question}**", C.NEON_CYAN)
    e.set_footer(text=f"Posé par {i.user.display_name}  ◈  AEGIS V2.1")
    await i.response.send_message(embed=e)
    msg = await i.original_response()
    await msg.add_reaction("👍"); await msg.add_reaction("👎"); await msg.add_reaction("🤷")

@bot.tree.command(name="tirage", description="Tirage au sort")
@app_commands.describe(options="Options séparées par des virgules")
async def tirage(i: discord.Interaction, options: str):
    choices = [o.strip() for o in options.split(",") if o.strip()]
    if len(choices) < 2:
        return await i.response.send_message(
            embed=er("Erreur", "Donne au moins 2 options séparées par des virgules."), ephemeral=True)
    winner = random.choice(choices)
    await i.response.send_message(embed=emb(
        f"◈  Tirage au sort",
        f"**Options :** {' ◈ '.join(choices)}\n\n► **Résultat : {winner}**", C.NEON_GOLD))

@bot.tree.command(name="avatar", description="Voir l'avatar d'un membre")
@app_commands.describe(membre="Le membre (vide = toi)")
async def avatar(i: discord.Interaction, membre: Optional[discord.Member]=None):
    m = membre or i.user
    e = discord.Embed(title=f"◈  Avatar de {m.display_name}", color=C.NEON_CYAN)
    e.set_image(url=m.display_avatar.with_size(1024).url)
    e.set_footer(text=f"ID : {m.id}  ◈  AEGIS V2.1")
    await i.response.send_message(embed=e)

@bot.tree.command(name="suggestion", description="Envoyer une suggestion")
@app_commands.describe(texte="Ta suggestion", salon="Salon suggestions")
async def suggestion(i: discord.Interaction, texte: str, salon: Optional[discord.TextChannel]=None):
    if not salon:
        for n in ["💡・suggestions","suggestions","suggest"]:
            salon = discord.utils.get(i.guild.text_channels, name=n)
            if salon: break
    if not salon:
        return await i.response.send_message(
            embed=er("Salon introuvable", "Crée un salon `suggestions` ou précise-le."), ephemeral=True)
    e = emb("💡  Suggestion", texte, C.NEON_GOLD)
    e.add_field(name="Par", value=i.user.mention, inline=True)
    e.add_field(name="Statut", value="⏳ En attente", inline=True)
    e.set_thumbnail(url=i.user.display_avatar.url)
    await i.response.defer(ephemeral=True)
    msg = await salon.send(embed=e, view=SuggView())
    await msg.add_reaction("👍"); await msg.add_reaction("👎")
    await i.followup.send(embed=ok("Suggestion envoyée !", f"Dans {salon.mention}."), ephemeral=True)

@bot.tree.command(name="dmall", description="Envoyer un DM à tous les membres du serveur")
@app_commands.describe(message="Le message à envoyer")
@app_commands.default_permissions(administrator=True)
async def dmall(i: discord.Interaction, message: str):
    await i.response.defer(ephemeral=True)
    members = [m for m in i.guild.members if not m.bot]
    total   = len(members)
    if total == 0:
        return await i.followup.send(
            embed=er("Aucun membre trouvé",
                     "Active **Server Members Intent** sur discord.com/developers → Bot → Privileged Gateway Intents."),
            ephemeral=True)
    await i.followup.send(embed=inf("📨  DM en cours...", f"Envoi à **{total}** membres..."), ephemeral=True)
    e_dm = discord.Embed(title=f"◈  Message de {i.guild.name}", description=message,
                         color=C.NEON_CYAN, timestamp=datetime.now(timezone.utc))
    e_dm.set_footer(text=f"Envoyé depuis {i.guild.name}  ◈  AEGIS V2.1")
    if i.guild.icon: e_dm.set_thumbnail(url=i.guild.icon.url)
    sent = failed = 0
    for m in members:
        try: await m.send(embed=e_dm); sent += 1
        except: failed += 1
        await asyncio.sleep(1.2)
    await i.edit_original_response(embed=ok("Terminé !",
        f"✅ Envoyés : {sent}\n❌ Échoués : {failed}\n📊 Total : {total}"))

# ── Musique ─────────────────────────────────────────────────────────────
@bot.tree.command(name="play", description="Jouer une musique depuis YouTube")
@app_commands.describe(recherche="Titre ou lien YouTube")
async def play(i: discord.Interaction, recherche: str):
    if not i.user.voice:
        return await i.response.send_message(
            embed=er("Pas dans un vocal", "Rejoins un salon vocal d'abord !"), ephemeral=True)
    vc_ch = i.user.voice.channel
    perms = vc_ch.permissions_for(i.guild.me)
    if not perms.connect or not perms.speak:
        return await i.response.send_message(
            embed=er("Permission manquante", "Je n'ai pas la permission de rejoindre ce salon."), ephemeral=True)
    await i.response.defer()
    gid = str(i.guild.id)
    await i.followup.send(embed=inf(f"♪  Recherche...", f"🔍 `{recherche}`"))
    track = await fetch_track(recherche)
    if not track or not track.get('url'):
        return await i.edit_original_response(
            embed=er("Introuvable", "Aucun résultat. Vérifie que le **Dockerfile** est bien sur GitHub (requis pour ffmpeg)."))
    vc = bot.vc_pool.get(gid)
    if not vc or not vc.is_connected():
        try: vc = await vc_ch.connect(); bot.vc_pool[gid] = vc
        except Exception as ex:
            return await i.edit_original_response(embed=er("Erreur vocal", str(ex)[:100]))
    bot.queues.setdefault(gid, []).append(track)
    if not vc.is_playing() and not vc.is_paused():
        await next_track(gid)
        e = emb(f"♪  Lecture", f"**{track['title']}**\n⏱️ `{fmt(track['duration'])}`", C.NEON_CYAN)
        if track.get('thumb'): e.set_thumbnail(url=track['thumb'])
        if track.get('webpage'): e.add_field(name="Lien", value=f"[YouTube]({track['webpage']})")
    else:
        pos = len(bot.queues.get(gid, []))
        e = emb(f"♪  Ajouté", f"**{track['title']}**\n📋 Position #{pos}", C.NEON_GOLD)
        if track.get('thumb'): e.set_thumbnail(url=track['thumb'])
    await i.edit_original_response(embed=e)

@bot.tree.command(name="pause", description="Mettre en pause")
async def pause(i: discord.Interaction):
    vc = bot.vc_pool.get(str(i.guild.id))
    if vc and vc.is_playing():
        vc.pause(); await i.response.send_message(embed=inf("♪  Pause", "Musique en pause."))
    else:
        await i.response.send_message(embed=er("Rien à mettre en pause"), ephemeral=True)

@bot.tree.command(name="resume", description="Reprendre la lecture")
async def resume(i: discord.Interaction):
    vc = bot.vc_pool.get(str(i.guild.id))
    if vc and vc.is_paused():
        vc.resume(); await i.response.send_message(embed=ok("♪  Lecture reprise"))
    else:
        await i.response.send_message(embed=er("Rien en pause"), ephemeral=True)

@bot.tree.command(name="skip", description="Passer à la suivante")
async def skip(i: discord.Interaction):
    vc = bot.vc_pool.get(str(i.guild.id))
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop(); await i.response.send_message(embed=ok("⏭️  Skippé"))
    else:
        await i.response.send_message(embed=er("Rien à skipper"), ephemeral=True)

@bot.tree.command(name="stop", description="Arrêter et déconnecter")
async def stop(i: discord.Interaction):
    gid = str(i.guild.id); vc = bot.vc_pool.get(gid)
    if vc:
        bot.queues[gid] = []; bot.now_playing[gid] = None
        await vc.disconnect(); bot.vc_pool.pop(gid, None)
        await i.response.send_message(embed=ok("⏹️  Arrêté", "Déconnecté."))
    else:
        await i.response.send_message(embed=er("Bot pas dans un vocal"), ephemeral=True)

@bot.tree.command(name="queue", description="Voir la file musicale")
async def queue(i: discord.Interaction):
    gid = str(i.guild.id); q = bot.queues.get(gid, []); np = bot.now_playing.get(gid)
    if not np and not q:
        return await i.response.send_message(embed=inf("File vide"), ephemeral=True)
    desc = ""
    if np: desc += f"**▶ En cours :** {np['title']} `{fmt(np['duration'])}`\n\n"
    if q:
        desc += "**▸ File :**\n"
        for idx, t in enumerate(q[:10], 1): desc += f"`{idx}.` {t['title']} `{fmt(t['duration'])}`\n"
        if len(q) > 10: desc += f"*... et {len(q)-10} autre(s)*"
    await i.response.send_message(embed=emb("♪  File musicale", desc, C.NEON_CYAN))

@bot.tree.command(name="nowplaying", description="Musique en cours")
async def nowplaying(i: discord.Interaction):
    np = bot.now_playing.get(str(i.guild.id))
    if not np: return await i.response.send_message(embed=inf("Rien en cours"), ephemeral=True)
    e = emb(f"♪  En cours", f"**{np['title']}**\n⏱️ `{fmt(np['duration'])}`", C.NEON_CYAN)
    if np.get('thumb'): e.set_thumbnail(url=np['thumb'])
    if np.get('webpage'): e.add_field(name="Lien", value=f"[YouTube]({np['webpage']})")
    await i.response.send_message(embed=e)

@bot.tree.command(name="volume", description="Régler le volume (0-100)")
@app_commands.describe(niveau="Volume entre 0 et 100")
async def volume(i: discord.Interaction, niveau: int):
    vc = bot.vc_pool.get(str(i.guild.id))
    if not vc or not vc.is_playing():
        return await i.response.send_message(embed=er("Rien en cours"), ephemeral=True)
    n = max(0, min(100, niveau))
    if vc.source: vc.source.volume = n/100
    await i.response.send_message(embed=ok(f"Volume : {n}%", f"{'🔇' if n==0 else '🔊'} Réglé à {n}%"))

# ── Modération ───────────────────────────────────────────────────────────
@bot.tree.command(name="warn", description="Avertir un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(moderate_members=True)
async def warn(i: discord.Interaction, membre: discord.Member, raison: str="Aucune raison"):
    if not can_target(i.user, membre):
        return await i.response.send_message(
            embed=er("Impossible", "Tu ne peux pas agir sur ce membre."), ephemeral=True)
    gid, uid = str(i.guild.id), str(membre.id)
    bot.warnings.setdefault(gid, {}).setdefault(uid, []).append(
        {"r": raison, "by": str(i.user.id), "at": datetime.now(timezone.utc).isoformat()})
    count = len(bot.warnings[gid][uid])
    e = emb(f"⚠️  Avertissement",
            f"**Membre :** {membre.mention}\n**Raison :** {raison}\n**Total :** {count}", C.NEON_ORANGE)
    sanction = None
    if count == 3:
        try: await membre.timeout(datetime.now(timezone.utc)+timedelta(hours=1),reason="3 warns"); sanction="Mute 1h"
        except: pass
    elif count == 5:
        try: await membre.timeout(datetime.now(timezone.utc)+timedelta(hours=24),reason="5 warns"); sanction="Mute 24h"
        except: pass
    elif count >= 7:
        try: await membre.kick(reason="7 warns"); sanction="Kick"
        except: pass
    if sanction: e.add_field(name="⚡ Sanction auto", value=sanction)
    await i.response.send_message(embed=e)
    await log(i.guild, "Warn", f"**Membre :** {membre}\n**Raison :** {raison}\n**Par :** {i.user}", C.NEON_ORANGE)
    try: await membre.send(embed=emb(f"⚠️  Avertissement reçu",
        f"**Serveur :** {i.guild.name}\n**Raison :** {raison}\n**Total :** {count}", C.NEON_ORANGE))
    except: pass

@bot.tree.command(name="unwarn", description="Retirer un avertissement")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unwarn(i: discord.Interaction, membre: discord.Member):
    gid, uid = str(i.guild.id), str(membre.id)
    lst = bot.warnings.get(gid, {}).get(uid, [])
    if not lst:
        return await i.response.send_message(embed=inf("Aucun warn", f"{membre.mention} est clean."), ephemeral=True)
    lst.pop()
    await i.response.send_message(embed=ok("Warn retiré", f"{membre.mention} → **{len(lst)}** warn(s)."))

@bot.tree.command(name="warns", description="Voir les avertissements")
@app_commands.describe(membre="Le membre (vide = toi)")
@app_commands.default_permissions(moderate_members=True)
async def warns(i: discord.Interaction, membre: Optional[discord.Member]=None):
    m = membre or i.user
    lst = bot.warnings.get(str(i.guild.id), {}).get(str(m.id), [])
    if not lst:
        return await i.response.send_message(embed=inf("Aucun warn", f"{m.mention} est clean ✅"), ephemeral=True)
    e = emb(f"⚠️  Warns de {m.display_name}", f"**Total :** {len(lst)}", C.NEON_ORANGE)
    for idx, w in enumerate(lst[-10:], 1):
        e.add_field(name=f"#{idx}", value=f"**Raison :** {w['r']}\n**Date :** {w['at'][:10]}", inline=True)
    await i.response.send_message(embed=e)

@bot.tree.command(name="ban", description="Bannir un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(ban_members=True)
async def ban(i: discord.Interaction, membre: discord.Member, raison: str="Aucune"):
    if not can_target(i.user, membre):
        return await i.response.send_message(
            embed=er("Impossible", "Tu ne peux pas bannir ce membre."), ephemeral=True)
    try:
        await membre.ban(reason=raison)
        await i.response.send_message(
            embed=emb(f"⛔  Banni", f"{membre.mention}\n**Raison :** {raison}", C.NEON_RED))
        await log(i.guild, "Ban", f"**Membre :** {membre}\n**Raison :** {raison}\n**Par :** {i.user}", C.NEON_RED)
    except discord.Forbidden:
        await i.response.send_message(embed=er("Permission manquante","Mon rôle doit être plus haut que celui du membre."),ephemeral=True)

@bot.tree.command(name="unban", description="Débannir un utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur")
@app_commands.default_permissions(ban_members=True)
async def unban(i: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await i.guild.unban(user)
        await i.response.send_message(embed=ok("Débanni", f"{user}"))
    except:
        await i.response.send_message(embed=er("Introuvable", "Vérifie l'ID."), ephemeral=True)

@bot.tree.command(name="kick", description="Expulser un membre")
@app_commands.describe(membre="Le membre", raison="Raison")
@app_commands.default_permissions(kick_members=True)
async def kick(i: discord.Interaction, membre: discord.Member, raison: str="Aucune"):
    if not can_target(i.user, membre):
        return await i.response.send_message(
            embed=er("Impossible", "Tu ne peux pas kick ce membre."), ephemeral=True)
    try:
        await membre.kick(reason=raison)
        await i.response.send_message(
            embed=emb(f"⚡  Expulsé", f"{membre.mention}\n**Raison :** {raison}", C.NEON_ORANGE))
        await log(i.guild, "Kick", f"**Membre :** {membre}\n**Raison :** {raison}\n**Par :** {i.user}", C.NEON_ORANGE)
    except discord.Forbidden:
        await i.response.send_message(embed=er("Permission manquante","Mon rôle doit être plus haut."),ephemeral=True)

@bot.tree.command(name="mute", description="Mute un membre")
@app_commands.describe(membre="Le membre", duree="Durée en minutes")
@app_commands.default_permissions(moderate_members=True)
async def mute(i: discord.Interaction, membre: discord.Member, duree: int=10):
    if not can_target(i.user, membre):
        return await i.response.send_message(
            embed=er("Impossible", "Tu ne peux pas mute ce membre."), ephemeral=True)
    try:
        await membre.timeout(datetime.now(timezone.utc)+timedelta(minutes=duree))
        await i.response.send_message(
            embed=emb(f"🔇  Muté", f"{membre.mention} — **{duree} min**", C.NEON_BLUE))
    except discord.Forbidden:
        await i.response.send_message(embed=er("Permission manquante","Mon rôle doit être plus haut."),ephemeral=True)

@bot.tree.command(name="unmute", description="Unmute un membre")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unmute(i: discord.Interaction, membre: discord.Member):
    await membre.timeout(None)
    await i.response.send_message(embed=ok("Unmute", f"{membre.mention}"))

@bot.tree.command(name="rename", description="Renommer un membre")
@app_commands.describe(membre="Le membre", pseudo="Nouveau pseudo")
@app_commands.default_permissions(manage_nicknames=True)
async def rename(i: discord.Interaction, membre: discord.Member, pseudo: str):
    old = membre.display_name
    try:
        await membre.edit(nick=pseudo)
        await i.response.send_message(embed=ok("Renommé", f"`{old}` → `{pseudo}`"))
    except discord.Forbidden:
        await i.response.send_message(embed=er("Permission manquante","Je ne peux pas renommer ce membre."),ephemeral=True)

@bot.tree.command(name="purge", description="Supprimer des messages")
@app_commands.describe(nombre="Nombre de messages (max 100)")
@app_commands.default_permissions(manage_messages=True)
async def purge(i: discord.Interaction, nombre: int):
    await i.response.defer(ephemeral=True)
    deleted = await i.channel.purge(limit=min(nombre, 100))
    await i.followup.send(embed=ok("Purge", f"**{len(deleted)}** messages supprimés."))

# ── Salons ────────────────────────────────────────────────────────────────
@bot.tree.command(name="creersalon", description="Créer un salon texte")
@app_commands.describe(nom="Nom du salon", categorie="Catégorie (optionnel)")
@app_commands.default_permissions(manage_channels=True)
async def creersalon(i: discord.Interaction, nom: str, categorie: Optional[discord.CategoryChannel]=None):
    try:
        ch = await i.guild.create_text_channel(nom, category=categorie)
        await i.response.send_message(embed=ok("Salon créé", ch.mention))
    except discord.Forbidden:
        await i.response.send_message(embed=er("Permission manquante","Monte le rôle du bot plus haut dans les paramètres du serveur."),ephemeral=True)

@bot.tree.command(name="creervoice", description="Créer un salon vocal")
@app_commands.describe(nom="Nom du salon", categorie="Catégorie (optionnel)")
@app_commands.default_permissions(manage_channels=True)
async def creervoice(i: discord.Interaction, nom: str, categorie: Optional[discord.CategoryChannel]=None):
    try:
        ch = await i.guild.create_voice_channel(nom, category=categorie)
        await i.response.send_message(embed=ok("Vocal créé", f"🔊 {ch.name}"))
    except discord.Forbidden:
        await i.response.send_message(embed=er("Permission manquante","Monte le rôle du bot plus haut."),ephemeral=True)

@bot.tree.command(name="supprimersalon", description="Supprimer un salon")
@app_commands.describe(salon="Le salon à supprimer")
@app_commands.default_permissions(manage_channels=True)
async def supprimersalon(i: discord.Interaction, salon: discord.TextChannel):
    name = salon.name
    try:
        await salon.delete()
        await i.response.send_message(embed=ok("Supprimé", f"`{name}`"))
    except discord.Forbidden:
        await i.response.send_message(embed=er("Permission manquante"),ephemeral=True)

@bot.tree.command(name="lock", description="Verrouiller un salon")
@app_commands.describe(salon="Salon à verrouiller (vide = actuel)", lecture="Bloquer aussi la lecture")
@app_commands.default_permissions(manage_channels=True)
async def lock(i: discord.Interaction, salon: Optional[discord.TextChannel]=None, lecture: bool=False):
    target = salon or i.channel
    await i.response.defer(ephemeral=True)
    try:
        overwrite = target.overwrites_for(i.guild.default_role)
        overwrite.update(send_messages=False)
        if lecture: overwrite.update(view_channel=False)
        await target.set_permissions(i.guild.default_role, overwrite=overwrite)
        await i.followup.send(embed=emb("🔒  Verrouillé", target.mention, C.NEON_RED))
    except discord.Forbidden:
        await i.followup.send(embed=er("Permission manquante", "Je n'ai pas la permission de modifier ce salon."))
    except Exception as e:
        await i.followup.send(embed=er("Erreur", str(e)[:100]))

@bot.tree.command(name="unlock", description="Déverrouiller un salon")
@app_commands.describe(salon="Salon (vide = actuel)")
@app_commands.default_permissions(manage_channels=True)
async def unlock(i: discord.Interaction, salon: Optional[discord.TextChannel]=None):
    target = salon or i.channel
    await i.response.defer(ephemeral=True)
    try:
        overwrite = target.overwrites_for(i.guild.default_role)
        overwrite.update(send_messages=True, view_channel=True)
        await target.set_permissions(i.guild.default_role, overwrite=overwrite)
        await i.followup.send(embed=ok("🔓  Déverrouillé", target.mention))
    except discord.Forbidden:
        await i.followup.send(embed=er("Permission manquante", "Je n'ai pas la permission de modifier ce salon."))

@bot.tree.command(name="slowmode", description="Mode lent sur un salon")
@app_commands.describe(secondes="Délai en secondes (0 = désactiver)", salon="Salon cible (vide = actuel)")
@app_commands.default_permissions(manage_channels=True)
async def slowmode(i: discord.Interaction, secondes: int, salon: Optional[discord.TextChannel]=None):
    target = salon or i.channel
    await i.response.defer(ephemeral=True)
    try:
        await target.edit(slowmode_delay=secondes)
        label = f"{secondes}s" if secondes > 0 else "Désactivé"
        await i.followup.send(embed=ok(f"Slowmode — {label}", f"Appliqué sur {target.mention}"))
    except discord.Forbidden:
        await i.followup.send(embed=er("Permission manquante", "Je ne peux pas modifier ce salon."))

# ── Rôles ─────────────────────────────────────────────────────────────────
@bot.tree.command(name="creerole", description="Créer un rôle")
@app_commands.describe(nom="Nom du rôle", couleur="Couleur hex (ex: #FF00FF)")
@app_commands.default_permissions(manage_roles=True)
async def creerole(i: discord.Interaction, nom: str, couleur: str="#00FFFF"):
    try:
        color = discord.Color(int(couleur.replace("#",""), 16))
        role = await i.guild.create_role(name=nom, color=color)
        await i.response.send_message(embed=ok("Rôle créé", role.mention))
    except discord.Forbidden:
        await i.response.send_message(embed=er("Permission manquante","Monte le rôle du bot plus haut dans les paramètres."),ephemeral=True)

@bot.tree.command(name="addrole", description="Ajouter un rôle à un membre")
@app_commands.describe(membre="Le membre", role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def addrole(i: discord.Interaction, membre: discord.Member, role: discord.Role):
    try:
        await membre.add_roles(role)
        await i.response.send_message(embed=ok("Rôle ajouté", f"{role.mention} → {membre.mention}"))
    except discord.Forbidden:
        await i.response.send_message(embed=er("Permission manquante","Mon rôle doit être plus haut que le rôle à attribuer."),ephemeral=True)

@bot.tree.command(name="removerole", description="Retirer un rôle d'un membre")
@app_commands.describe(membre="Le membre", role="Le rôle")
@app_commands.default_permissions(manage_roles=True)
async def removerole(i: discord.Interaction, membre: discord.Member, role: discord.Role):
    try:
        await membre.remove_roles(role)
        await i.response.send_message(embed=inf("Rôle retiré", f"{role.mention} retiré de {membre.mention}"))
    except discord.Forbidden:
        await i.response.send_message(embed=er("Permission manquante"),ephemeral=True)

@bot.tree.command(name="roleall", description="Donner un rôle à tous les membres")
@app_commands.describe(role="Le rôle")
@app_commands.default_permissions(administrator=True)
async def roleall(i: discord.Interaction, role: discord.Role):
    await i.response.defer()
    count = 0
    for m in i.guild.members:
        if not m.bot and role not in m.roles:
            try: await m.add_roles(role); count += 1; await asyncio.sleep(0.5)
            except: pass
    await i.followup.send(embed=ok("Rôle donné à tous", f"{role.mention} — **{count}** membres"))

@bot.tree.command(name="autorole", description="Gérer les rôles automatiques pour les nouveaux membres")
@app_commands.describe(action="Ajouter ou retirer", role="Le rôle", reset="Supprimer tous les auto-rôles")
@app_commands.choices(action=[
    app_commands.Choice(name="Ajouter", value="add"),
    app_commands.Choice(name="Retirer", value="rem")])
@app_commands.default_permissions(administrator=True)
async def autorole(i: discord.Interaction, action: str="add",
                   role: Optional[discord.Role]=None, reset: bool=False):
    gid = str(i.guild.id)
    current = bot.auto_roles.get(gid, [])
    if isinstance(current, int): current = [current]
    if reset:
        bot.auto_roles[gid] = []
        return await i.response.send_message(embed=ok("Auto-rôles supprimés"))
    if not role:
        if not current:
            return await i.response.send_message(
                embed=inf("Aucun auto-rôle", "Utilise `/autorole action:Ajouter role:@role`"), ephemeral=True)
        names = [i.guild.get_role(rid) for rid in current]
        desc  = "\n".join([f"◈ {r.mention}" for r in names if r]) or "Aucun"
        return await i.response.send_message(embed=inf(f"Auto-rôles ({len(current)})", desc), ephemeral=True)
    if action == "add":
        if role.id not in current:
            current.append(role.id); bot.auto_roles[gid] = current
            await i.response.send_message(embed=ok("Auto-rôle ajouté", f"{role.mention} — {len(current)} rôle(s)"))
        else:
            await i.response.send_message(embed=inf("Déjà présent", f"{role.mention}"), ephemeral=True)
    else:
        if role.id in current:
            current.remove(role.id); bot.auto_roles[gid] = current
            await i.response.send_message(embed=ok("Auto-rôle retiré", f"{role.mention} — {len(current)} rôle(s)"))
        else:
            await i.response.send_message(embed=inf("Pas trouvé", f"{role.mention}"), ephemeral=True)

@bot.tree.command(name="rolemenu", description="Créer un menu de sélection de rôles")
@app_commands.describe(titre="Titre du menu", roles="Mentions des rôles")
@app_commands.default_permissions(administrator=True)
async def rolemenu(i: discord.Interaction, titre: str, roles: str):
    # Accepter mentions <@&123> ET IDs bruts
    ids = re.findall(r'<@&(\d+)>', roles) or re.findall(r'\b(\d{17,20})\b', roles)
    objs = [i.guild.get_role(int(x)) for x in ids if i.guild.get_role(int(x))]
    # Si toujours vide, chercher par nom
    if not objs:
        for word in roles.split():
            word = word.strip().lstrip('@')
            r = discord.utils.get(i.guild.roles, name=word)
            if r and r not in objs: objs.append(r)
    if not objs:
        return await i.response.send_message(
            embed=er("Erreur", "Aucun rôle trouvé. Essaie de mentionner le rôle directement avec @Rôle dans le champ."), ephemeral=True)
    e = emb(f"◉  {titre}", "\n".join([f"◈ {r.mention}" for r in objs]), C.NEON_PINK)
    if not check_perms(i.channel, i.guild.me):
        return await i.response.send_message(embed=er("Accès refusé",
            f"Je n'ai pas accès à {i.channel.mention}. Vérifie les permissions du rôle Aegis."), ephemeral=True)
    await i.response.defer(ephemeral=True)
    await i.channel.send(embed=e, view=RoleMenuView(objs))
    await i.followup.send(embed=ok("Menu créé !"), ephemeral=True)

# ── Systèmes ──────────────────────────────────────────────────────────────
@bot.tree.command(name="panel", description="Créer un panel de tickets")
@app_commands.describe(
    titre="Titre du panel",
    description="Description du panel",
    role_support="Rôle support (optionnel)",
    image="URL d'une image ou GIF à afficher dans le panel (optionnel)")
@app_commands.default_permissions(administrator=True)
async def panel(i: discord.Interaction, titre: str="Support",
                description: str="Clique pour ouvrir un ticket.",
                role_support: Optional[discord.Role]=None,
                image: Optional[str]=None):
    bot.ticket_cfg[str(i.guild.id)] = {"sr": role_support.id if role_support else None}
    if not check_perms(i.channel, i.guild.me):
        return await i.response.send_message(embed=er("Acces refuse","Je n'ai pas acces a ce salon. Verifie les permissions du role Aegis."),ephemeral=True)
    await i.response.defer(ephemeral=True)
    e = emb(f"🎫  {titre}", description, C.NEON_CYAN)
    if image:
        # Accepter URL directe ou lien Discord/tenor/giphy
        e.set_image(url=image)
    await i.channel.send(embed=e, view=TicketView())
    await i.followup.send(embed=ok("Panel créé !"), ephemeral=True)

@bot.tree.command(name="reglement", description="Envoyer le règlement")
@app_commands.describe(type_reglement="Type", avec_bouton="Ajouter bouton d'acceptation", role="Rôle à l'acceptation")
@app_commands.choices(type_reglement=[
    app_commands.Choice(name="Défaut", value="def"),
    app_commands.Choice(name="Personnalisé", value="custom")])
@app_commands.default_permissions(administrator=True)
async def reglement(i: discord.Interaction, type_reglement: str="def",
                    avec_bouton: bool=True, role: Optional[discord.Role]=None):
    if type_reglement == "custom":
        return await i.response.send_modal(ReglModal(avec_bouton, role))
    if role: bot.verif_roles[str(i.guild.id)] = role.id
    if not check_perms(i.channel, i.guild.me):
        return await i.response.send_message(embed=er("Accès refusé",
            f"Je n'ai pas accès à {i.channel.mention}. Vérifie les permissions du rôle Aegis."), ephemeral=True)
    rules = [
        ("◈  Respect",    "Respecte tous les membres et le staff."),
        ("◈  Anti-spam",  "Évite de répéter les mêmes messages."),
        ("◈  Publicité",  "Toute publicité non autorisée est interdite."),
        ("◈  Contenu",    "Aucun contenu NSFW, violent ou illégal."),
        ("◈  Staff",      "Les décisions du staff sont définitives."),
    ]
    e = discord.Embed(title="◈  Règlement", description="─────────────────────",
                      color=C.NEON_CYAN, timestamp=datetime.now(timezone.utc))
    for t, c in rules: e.add_field(name=t, value=c, inline=False)
    await i.response.defer(ephemeral=True)
    await i.channel.send(embed=e, view=RulesView() if avec_bouton else None)
    await i.followup.send(embed=ok("Règlement envoyé !"), ephemeral=True)

@bot.tree.command(name="verification", description="Créer un panel de vérification")
@app_commands.describe(role="Rôle à donner", titre="Titre", description="Description")
@app_commands.default_permissions(administrator=True)
async def verification(i: discord.Interaction, role: Optional[discord.Role]=None,
                        titre: str="Vérification", description: str="Clique pour te vérifier !"):
    gid = str(i.guild.id)
    if not role:
        role = discord.utils.get(i.guild.roles, name="✅ Vérifié")
        if not role:
            try: role = await i.guild.create_role(name="✅ Vérifié", color=discord.Color(C.NEON_GREEN))
            except:
                return await i.response.send_message(
                    embed=er("Erreur", "Je n'ai pas pu créer le rôle. Vérifie mes permissions."), ephemeral=True)
    bot.verif_roles[gid] = role.id
    if not check_perms(i.channel, i.guild.me):
        return await i.response.send_message(embed=er("Accès refusé",
            f"Je n'ai pas accès à {i.channel.mention}. Vérifie les permissions du rôle Aegis."), ephemeral=True)
    e = emb(f"◈  {titre}", f"{description}\n\n**Rôle :** {role.mention}", C.NEON_CYAN)
    await i.response.defer(ephemeral=True)
    await i.channel.send(embed=e, view=VerifyView())
    await i.followup.send(embed=ok("Panel créé !"), ephemeral=True)

@bot.tree.command(name="arrivee", description="Configurer le salon des messages de bienvenue")
@app_commands.describe(salon_id="ID du salon (Mode dev → clic droit sur le salon → Copier l'identifiant)")
@app_commands.default_permissions(administrator=True)
async def arrivee(i: discord.Interaction, salon_id: str):
    clean = salon_id.strip().replace("<#","").replace(">","").strip()
    try:
        cid = int(clean)
        ch  = i.guild.get_channel(cid) or await i.guild.fetch_channel(cid)
        if not ch: raise ValueError("Salon introuvable")
        bot.arrivee[str(i.guild.id)] = ch.id
        await i.response.send_message(embed=ok("Arrivées configurées", f"Salon : {ch.mention}"))
    except Exception:
        await i.response.send_message(embed=er("ID invalide",
            "Active le **Mode développeur** (Paramètres Discord → Avancé)\n"
            "puis clic droit sur le salon → **Copier l'identifiant**."), ephemeral=True)

@bot.tree.command(name="depart", description="Configurer le salon des messages de départ")
@app_commands.describe(salon_id="ID du salon (Mode dev → clic droit sur le salon → Copier l'identifiant)")
@app_commands.default_permissions(administrator=True)
async def depart(i: discord.Interaction, salon_id: str):
    clean = salon_id.strip().replace("<#","").replace(">","").strip()
    try:
        cid = int(clean)
        ch  = i.guild.get_channel(cid) or await i.guild.fetch_channel(cid)
        if not ch: raise ValueError("Salon introuvable")
        bot.depart_ch[str(i.guild.id)] = ch.id
        await i.response.send_message(embed=ok("Départs configurés", f"Salon : {ch.mention}"))
    except Exception:
        await i.response.send_message(embed=er("ID invalide",
            "Active le **Mode développeur** (Paramètres Discord → Avancé)\n"
            "puis clic droit sur le salon → **Copier l'identifiant**."), ephemeral=True)

@bot.tree.command(name="giveaway", description="Créer un giveaway")
@app_commands.describe(titre="Titre", prix="Prix", heures="Durée en heures", gagnants="Nb gagnants")
@app_commands.default_permissions(administrator=True)
async def giveaway(i: discord.Interaction, titre: str, prix: str, heures: int, gagnants: int=1):
    perms = i.channel.permissions_for(i.guild.me)
    if not perms.view_channel or not perms.send_messages or not perms.embed_links:
        return await i.response.send_message(embed=er("Accès refusé","Je n'ai pas accès à ce salon."),ephemeral=True)
    await i.response.defer()
    end = datetime.now(timezone.utc) + timedelta(hours=heures)
    e = discord.Embed(title=f"🎉  {titre.upper()}",
                      description=f"◎ **Prix :** {prix}\n─────────────────────",
                      color=C.NEON_GOLD, timestamp=datetime.now(timezone.utc))
    e.add_field(name="◈ Gagnants",    value=f"**{gagnants}**",                   inline=True)
    e.add_field(name="◎ Participants", value=f"**0**",                            inline=True)
    e.add_field(name="⏰ Fin",         value=f"<t:{int(end.timestamp())}:R>",     inline=True)
    e.set_footer(text=f"Organisé par {i.user.display_name}  ◈  AEGIS V2.1")
    msg = await i.channel.send(embed=e)
    mid = str(msg.id)
    bot.giveaways[mid] = {"title":titre,"prize":prix,"winners":gagnants,"end":end.isoformat(),
                          "cid":str(i.channel.id),"gid":str(i.guild.id),"p":[],"ended":False}
    v = GAView(mid); bot.add_view(v); await msg.edit(view=v)
    await i.followup.send(embed=ok("Giveaway créé !",
        f"**{titre}** — {prix} — {heures}h — {gagnants} gagnant(s)"), ephemeral=True)

@bot.tree.command(name="reroll", description="Relancer un giveaway terminé")
@app_commands.describe(message_id="ID du message du giveaway")
@app_commands.default_permissions(administrator=True)
async def reroll(i: discord.Interaction, message_id: str):
    g = bot.giveaways.get(message_id)
    if not g:              return await i.response.send_message(embed=er("Introuvable"),ephemeral=True)
    if not g.get("ended"): return await i.response.send_message(embed=er("Encore en cours"),ephemeral=True)
    p = g.get("p", [])
    if not p:              return await i.response.send_message(embed=er("Aucun participant"),ephemeral=True)
    winners = []
    for wid in random.sample(p, min(g.get("winners",1), len(p))):
        try: winners.append(await bot.fetch_user(wid))
        except: pass
    if winners:
        await i.response.send_message(
            content=" ".join([w.mention for w in winners]),
            embed=emb("🎉  Reroll !",
                f"**Gagnant(s) :** {', '.join([w.mention for w in winners])}\n**Prix :** {g.get('prize')}",
                C.NEON_GOLD))
    else:
        await i.response.send_message(embed=er("Erreur reroll"), ephemeral=True)

@bot.tree.command(name="poll", description="Créer un sondage interactif")
@app_commands.describe(question="La question", option1="Option 1", option2="Option 2",
                        option3="Option 3", option4="Option 4", option5="Option 5",
                        duree="Durée en minutes (0 = sans limite)")
@app_commands.default_permissions(manage_messages=True)
async def poll_cmd(i: discord.Interaction, question: str, option1: str, option2: str,
                   option3: Optional[str]=None, option4: Optional[str]=None,
                   option5: Optional[str]=None, duree: int=0):
    opts = [o for o in [option1,option2,option3,option4,option5] if o]
    end  = None
    if duree > 0: end = datetime.now(timezone.utc) + timedelta(minutes=duree)
    desc = f"**{question}**\n\n"
    for idx, o in enumerate(opts):
        desc += f"{PE[idx]} **{o}**\n`░░░░░░░░░░` 0 vote (0%)\n\n"
    desc += f"▸ **0 vote au total**"
    if end: desc += f"\n\n⏰ Fin : <t:{int(end.timestamp())}:R>"
    e = emb(f"▸  Sondage", desc, C.NEON_CYAN)
    e.set_footer(text=f"Par {i.user.display_name}" + (f" ◈ {duree} min" if duree > 0 else "") + "  ◈  AEGIS V2.1")
    await i.response.send_message(embed=e)
    msg = await i.original_response(); mid = str(msg.id)
    poll_data = {"q":question,"opts":opts,"v":{},"ended":False,
                 "gid":str(i.guild.id),"cid":str(i.channel.id)}
    if end: poll_data["end"] = end.isoformat()
    bot.polls[mid] = poll_data
    await msg.edit(view=PollView(mid, opts))

# ── Infos ─────────────────────────────────────────────────────────────────
@bot.tree.command(name="userinfo", description="Informations sur un membre")
@app_commands.describe(membre="Le membre (vide = toi)")
async def userinfo(i: discord.Interaction, membre: Optional[discord.Member]=None):
    m = membre or i.user; gid = str(i.guild.id); d = get_xp(gid, str(m.id))
    roles = [r.mention for r in m.roles if r.name != "@everyone"]
    e = discord.Embed(title=f"◈  {m.display_name}", color=C.NEON_CYAN, timestamp=datetime.now(timezone.utc))
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="Discord",    value=str(m),                                       inline=True)
    e.add_field(name="ID",         value=f"`{m.id}`",                                  inline=True)
    e.add_field(name="Bot",        value="✅" if m.bot else "❌",                       inline=True)
    e.add_field(name="Créé le",    value=m.created_at.strftime("%d/%m/%Y"),            inline=True)
    e.add_field(name="Rejoint le", value=m.joined_at.strftime("%d/%m/%Y") if m.joined_at else "?", inline=True)
    e.add_field(name="◆ Niveau",   value=f"**{d['level']}** ({d['xp']} XP)",           inline=True)
    e.add_field(name=f"◉ Rôles ({len(roles)})", value=" ".join(roles[:10]) or "Aucun", inline=False)
    e.set_footer(text="AEGIS V2.1  ◈  discord.gg/6rN8pneGdy")
    await i.response.send_message(embed=e)

@bot.tree.command(name="serverinfo", description="Informations sur le serveur")
async def serverinfo(i: discord.Interaction):
    g     = i.guild
    total = g.member_count or len(g.members) or 0
    bots  = sum(1 for m in g.members if m.bot)
    humans = max(0, total - bots)
    e = discord.Embed(title=f"◈  {g.name}", color=C.NEON_CYAN, timestamp=datetime.now(timezone.utc))
    if g.icon: e.set_thumbnail(url=g.icon.url)
    e.add_field(name="ID",           value=f"`{g.id}`",                              inline=True)
    e.add_field(name="Propriétaire", value=g.owner.mention if g.owner else "?",      inline=True)
    e.add_field(name="Créé le",      value=g.created_at.strftime("%d/%m/%Y"),        inline=True)
    e.add_field(name="Membres",      value=f"**{humans}** humains / **{bots}** bots",inline=True)
    e.add_field(name="Salons",       value=f"**{len(g.text_channels)}** texte / **{len(g.voice_channels)}** vocal", inline=True)
    e.add_field(name="Rôles",        value=f"**{len(g.roles)}**",                    inline=True)
    e.add_field(name="Boosts",       value=f"**{g.premium_subscription_count}** (Niv. {g.premium_tier})", inline=True)
    e.set_footer(text="AEGIS V2.1  ◈  discord.gg/6rN8pneGdy")
    await i.response.send_message(embed=e)

@bot.tree.command(name="rank", description="Voir son niveau XP")
@app_commands.describe(membre="Le membre (vide = toi)")
async def rank(i: discord.Interaction, membre: Optional[discord.Member]=None):
    m = membre or i.user; gid = str(i.guild.id); d = get_xp(gid, str(m.id))
    lv, xp = d["level"], d["xp"]; req = xp_req(lv+1)
    pct = int(xp/req*100) if req > 0 else 0
    bar = "█"*(pct//10) + "░"*(10-pct//10)
    su  = sorted(bot.xp_data.get(gid,{}).items(), key=lambda x:(x[1]["level"],x[1]["xp"]), reverse=True)
    rk  = next((idx+1 for idx,(uid,_) in enumerate(su) if uid==str(m.id)), "?")
    e = discord.Embed(title=f"◆  Rang de {m.display_name}", color=C.NEON_GOLD, timestamp=datetime.now(timezone.utc))
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="Niveau",       value=f"**{lv}**",           inline=True)
    e.add_field(name="XP",           value=f"**{xp}** / {req}",   inline=True)
    e.add_field(name="Classement",   value=f"**#{rk}**",           inline=True)
    e.add_field(name="Messages",     value=f"**{d['messages']}**", inline=True)
    e.add_field(name="Progression",  value=f"`{bar}` {pct}%",      inline=False)
    e.set_footer(text="AEGIS V2.1  ◈  discord.gg/6rN8pneGdy")
    await i.response.send_message(embed=e)

@bot.tree.command(name="top", description="Top 10 XP du serveur")
async def top(i: discord.Interaction):
    gid = str(i.guild.id); gxp = bot.xp_data.get(gid, {})
    if not gxp:
        return await i.response.send_message(
            embed=inf("Classement vide", "Personne n'a encore de XP."), ephemeral=True)
    su     = sorted(gxp.items(), key=lambda x:(x[1]["level"],x[1]["xp"]), reverse=True)[:10]
    medals = ["🥇","🥈","🥉"] + [f"**#{idx}**" for idx in range(4,11)]
    desc   = ""
    for idx, (uid, d) in enumerate(su):
        m    = i.guild.get_member(int(uid))
        name = m.display_name if m else f"ID:{uid}"
        desc += f"{medals[idx]} **{name}** — Niveau {d['level']} ({d['xp']} XP)\n"
    await i.response.send_message(embed=emb("◆  Top 10 XP", desc, C.NEON_GOLD))

# ── Administration ────────────────────────────────────────────────────────
@bot.tree.command(name="setup", description="Setup complet du serveur")
@app_commands.describe(style="Style du serveur")
@app_commands.choices(style=[
    app_commands.Choice(name="🌐 Communauté",  value="communaute"),
    app_commands.Choice(name="🎮 Gaming",      value="gaming"),
    app_commands.Choice(name="🎭 Jeu de Rôle", value="rp"),
    app_commands.Choice(name="📚 Éducation",   value="education"),
    app_commands.Choice(name="🎌 Anime/Manga", value="anime")])
@app_commands.default_permissions(administrator=True)
async def setup(i: discord.Interaction, style: str="communaute"):
    await i.response.defer()
    g = i.guild; cfg = SETUPS[style]; created = {"roles":0,"text":0,"voice":0}
    for name, color in cfg["roles"]:
        if not discord.utils.get(g.roles, name=name):
            try: await g.create_role(name=name,color=discord.Color(color)); created["roles"]+=1; await asyncio.sleep(0.4)
            except: pass
    for cat_name, (texts, voices) in cfg["struct"].items():
        cat = discord.utils.get(g.categories, name=cat_name)
        if not cat:
            try:
                ow  = {g.default_role:discord.PermissionOverwrite(view_channel=False)} if "STAFF" in cat_name or "MJ" in cat_name else {}
                cat = await g.create_category(cat_name, overwrites=ow); await asyncio.sleep(0.4)
            except: continue
        for cn in texts:
            if not discord.utils.get(g.text_channels, name=cn):
                try: await g.create_text_channel(cn,category=cat); created["text"]+=1; await asyncio.sleep(0.4)
                except: pass
        for vn in voices:
            if not discord.utils.get(g.voice_channels, name=vn):
                try: await g.create_voice_channel(vn,category=cat); created["voice"]+=1; await asyncio.sleep(0.4)
                except: pass
    for ln in ["📊・logs","logs"]:
        lc = discord.utils.get(g.text_channels, name=ln)
        if lc: bot.logs_ch[str(g.id)] = lc.id; break
    e = ok(f"Setup terminé — {cfg['label']}")
    e.add_field(name="Rôles créés",  value=f"**{created['roles']}**",  inline=True)
    e.add_field(name="Salons texte", value=f"**{created['text']}**",   inline=True)
    e.add_field(name="Salons vocal", value=f"**{created['voice']}**",  inline=True)
    e.add_field(name="⚠️ Si Rôles:0",
                value="Paramètres du serveur → Rôles → Monte le rôle **Aegis** tout en haut.", inline=False)
    e.add_field(name="Étapes suivantes",
                value="`/arrivee` `/depart` `/panel` `/verification` `/reglement`", inline=False)
    await i.followup.send(embed=e)

@bot.tree.command(name="backup", description="Sauvegarder la structure du serveur")
@app_commands.describe(nom="Nom de la sauvegarde")
@app_commands.default_permissions(administrator=True)
async def backup(i: discord.Interaction, nom: Optional[str]=None):
    await i.response.defer(ephemeral=True)
    g    = i.guild
    name = nom or f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    roles  = [r for r in g.roles if r.name != "@everyone" and not r.managed]
    texts  = list(g.text_channels)
    voices = list(g.voice_channels)
    cats   = list(g.categories)
    if not roles and not texts:
        return await i.followup.send(embed=er("Intents manquants",
            "Active les **Privileged Gateway Intents** sur discord.com/developers → Bot."), ephemeral=True)
    data = {
        "roles":  [{"name":r.name,"color":r.color.value} for r in roles],
        "cats":   [{"name":c.name} for c in cats],
        "text":   [{"name":c.name,"cat":c.category.name if c.category else None} for c in texts],
        "voice":  [{"name":c.name,"cat":c.category.name if c.category else None} for c in voices],
    }
    bot.backups.setdefault(str(g.id), {})[name] = data
    await i.followup.send(embed=ok("Sauvegarde créée",
        f"**{name}**\nRôles : {len(data['roles'])} | Salons : {len(data['text'])+len(data['voice'])}"),
        ephemeral=True)

@bot.tree.command(name="restore", description="Restaurer une sauvegarde")
@app_commands.describe(nom="Nom de la sauvegarde")
@app_commands.default_permissions(administrator=True)
async def restore(i: discord.Interaction, nom: str):
    await i.response.defer()
    gid  = str(i.guild.id)
    data = bot.backups.get(gid, {}).get(nom)
    if not data:
        return await i.followup.send(embed=er("Introuvable", f"Sauvegarde `{nom}` inexistante."))
    r = {"roles":0,"channels":0}
    for x in data.get("roles",[]):
        if not discord.utils.get(i.guild.roles, name=x["name"]):
            try: await i.guild.create_role(name=x["name"],color=discord.Color(x.get("color",0))); r["roles"]+=1; await asyncio.sleep(0.3)
            except: pass
    for x in data.get("cats",[]):
        if not discord.utils.get(i.guild.categories, name=x["name"]):
            try: await i.guild.create_category(x["name"]); await asyncio.sleep(0.3)
            except: pass
    for x in data.get("text",[]):
        if not discord.utils.get(i.guild.text_channels, name=x["name"]):
            try:
                cat = discord.utils.get(i.guild.categories, name=x.get("cat"))
                await i.guild.create_text_channel(x["name"],category=cat); r["channels"]+=1; await asyncio.sleep(0.3)
            except: pass
    await i.followup.send(embed=ok("Restauré !",
        f"Rôles : **{r['roles']}** | Salons : **{r['channels']}**"))

@bot.tree.command(name="antiraid", description="Configurer l'anti-raid")
@app_commands.describe(activer="Activer", seuil="Joins par 10s", action="kick ou ban")
@app_commands.default_permissions(administrator=True)
async def antiraid(i: discord.Interaction, activer: bool=True, seuil: int=5, action: str="kick"):
    bot.raid_cfg[str(i.guild.id)] = {"enabled":activer,"threshold":seuil,"action":action}
    await i.response.send_message(embed=emb("◈  Anti-Raid",
        f"**Statut :** {'✅ Activé' if activer else '❌ Désactivé'}\n"
        f"**Seuil :** {seuil} joins/10s\n**Action :** {action}", C.NEON_PINK))

@bot.tree.command(name="antispam", description="Configurer l'anti-spam")
@app_commands.describe(activer="Activer", messages="Max messages", fenetre="Fenêtre en secondes",
                        mentions="Max mentions", action="mute/kick/ban", duree_mute="Durée mute (min)")
@app_commands.default_permissions(administrator=True)
async def antispam(i: discord.Interaction, activer: bool=True, messages: int=5,
                   fenetre: int=5, mentions: int=5, action: str="mute", duree_mute: int=5):
    bot.spam_cfg[str(i.guild.id)] = {"enabled":activer,"limit":messages,"window":fenetre,
                                      "mentions":mentions,"action":action,"dur":duree_mute}
    await i.response.send_message(embed=emb("◈  Anti-Spam",
        f"**Statut :** {'✅ Activé' if activer else '❌ Désactivé'}\n"
        f"**Messages :** {messages}/{fenetre}s\n**Mentions :** {mentions}\n**Action :** {action}", C.NEON_PINK))

@bot.tree.command(name="antinuke", description="Configurer la protection anti-nuke")
@app_commands.describe(activer="Activer", seuil="Actions max/10s avant sanction",
                        action="kick ou ban",
                        whitelist_add="ID à ajouter en whitelist",
                        whitelist_rem="ID à retirer de la whitelist")
@app_commands.default_permissions(administrator=True)
async def antinuke(i: discord.Interaction, activer: bool=True, seuil: int=5,
                   action: str="kick", whitelist_add: Optional[str]=None,
                   whitelist_rem: Optional[str]=None):
    gid = str(i.guild.id)
    cfg = bot.nuke_cfg.setdefault(gid, default_nuke_cfg())
    cfg.update({"enabled":activer,"threshold":max(1,seuil),
                "action":action if action in("kick","ban") else "kick"})
    wl = cfg["whitelist"]
    if whitelist_add:
        try:
            uid = int(whitelist_add)
            if uid not in wl: wl.append(uid)
        except: pass
    if whitelist_rem:
        try:
            uid = int(whitelist_rem)
            if uid in wl: wl.remove(uid)
        except: pass
    wl_txt = ", ".join([f"<@{uid}>" for uid in wl]) or "Aucun"
    e = emb("☢️  Anti-Nuke",
            f"**Statut :** {'✅ Activé' if activer else '❌ Désactivé'}\n"
            f"**Seuil :** {seuil} actions/10s\n**Sanction :** {cfg['action']}\n"
            f"**Whitelist :** {wl_txt}\n\n"
            f"**Surveille :**\n▸ Bans en masse\n▸ Suppression de salons\n▸ Suppression de rôles",
            C.NEON_RED)
    e.set_footer(text="⚠️ Ajoute tes admins en whitelist !  ◈  AEGIS V2.1")
    await i.response.send_message(embed=e)

@bot.tree.command(name="tempvoice", description="Salons vocaux temporaires")
@app_commands.describe(salon="Salon déclencheur")
@app_commands.default_permissions(administrator=True)
async def tempvoice(i: discord.Interaction, salon: discord.VoiceChannel):
    bot.temp_voices[str(i.guild.id)] = salon.id
    await i.response.send_message(embed=ok("Vocaux temporaires",
        f"Rejoins **{salon.name}** pour créer ton salon automatiquement !"))
@bot.tree.command(name="admin_panel", description="Panel admin — réservé au propriétaire du bot")
async def admin_panel(i: discord.Interaction):
    # Vérification : uniquement BOT_OWNER_ID
    if BOT_OWNER_ID == 0:
        return await i.response.send_message(
            embed=er("BOT_OWNER_ID non configuré",
                     "Ajoute **BOT_OWNER_ID** dans Railway → Variables avec ton ID Discord.\n"
                     "Pour trouver ton ID : Mode développeur → clic droit sur toi → Copier l'identifiant."),
            ephemeral=True)
    if i.user.id != BOT_OWNER_ID:
        return await i.response.send_message(
            embed=er("Accès refusé", "Cette commande est réservée au propriétaire du bot."),
            ephemeral=True)

    guilds      = bot.guilds
    total_mem   = sum(g.member_count or 0 for g in guilds)
    total_bots  = sum(sum(1 for m in g.members if m.bot) for g in guilds if g.members)
    humans      = max(0, total_mem - total_bots)

    e = discord.Embed(
        title="◈  AEGIS — Panel Admin",
        description=(
            f"**Bot :** {bot.user} (`{bot.user.id}`)\n"
            f"**Ping :** `{round(bot.latency*1000)} ms`\n"
            f"─────────────────────\n"
            f"**Serveurs :** `{len(guilds)}`\n"
            f"**Membres totaux :** `{total_mem:,}`\n"
            f"**Humains :** `{humans:,}`\n"
            f"**Bots :** `{total_bots:,}`\n"
            f"─────────────────────\n"
            f"**Sondages actifs :** `{sum(1 for p in bot.polls.values() if not p.get('ended'))}`\n"
            f"**Giveaways actifs :** `{sum(1 for g in bot.giveaways.values() if not g.get('ended'))}`\n"
            f"**Vocaux ouverts :** `{len(bot.vc_pool)}`"
        ),
        color=C.NEON_PINK,
        timestamp=datetime.now(timezone.utc)
    )
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.set_footer(text=f"Consulté par {i.user}  ◈  AEGIS V2.1")

    # Liste des serveurs triés par membres décroissant
    if guilds:
        sorted_g = sorted(guilds, key=lambda g: g.member_count or 0, reverse=True)
        lines = []
        for idx, g in enumerate(sorted_g[:20], 1):
            lines.append(f"`{idx}.` **{g.name}** — `{g.member_count or 0}` membres — `{g.id}`")
        if len(guilds) > 20:
            lines.append(f"*... et {len(guilds)-20} autre(s)*")
        e.add_field(name=f"▸ Serveurs ({len(guilds)})", value="\n".join(lines), inline=False)

    await i.response.send_message(embed=e, ephemeral=True)
# ══════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    token = os.environ.get('DISCORD_BOT_TOKEN')
    if token:
        logger.info("⚡ AEGIS V2.1 démarre...")
        bot.run(token)
    else:
        logger.error("❌ DISCORD_BOT_TOKEN manquant dans Railway → Variables !")
