import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, logging, asyncio, random, re, aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict
from collections import defaultdict, deque

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Aegis')

BOT_OWNER_ID = int(os.environ.get('BOT_OWNER_ID', '0'))

# ==================== THEME ====================
class T:
    PINK=0xFF1493; GREEN=0x57F287; RED=0xED4245; ORANGE=0xFF6600
    GOLD=0xFFD700; BLURPLE=0x5865F2; PURPLE=0x9B59B6; TEAL=0x1ABC9C

    SPARKLE="✨"; LIGHTNING="⚡"; STAR="🌟"; DIAMOND="💎"; CROWN="👑"
    CRYSTAL="💠"; TICKET="🎫"; LOCK="🔐"; BAN="⛔"; KICK="👢"
    WARN="⚠️"; SHIELD="🛡️"; CHECK="✅"; CROSS="❌"; GEAR="⚙️"
    CHANNEL="💬"; VOICE="🔊"; ROLE="🎭"; SPAM="🚫"; GIVEAWAY="🎉"
    GIFT="🎁"; TROPHY="🏆"; CLOCK="⏰"; WAVE="👋"; DOOR="🚪"
    CHART="📊"; XP="⭐"; INFO="ℹ️"; POLL="📊"; ARROW="➜"
    MUTE="🔇"; MUSIC="🎵"; PAUSE="⏸️"; SKIP="⏭️"; STOP="⏹️"
    AI="🤖"; MEGA="📣"; FIRE="🔥"; NUKE="🚨"
    LINE="━━━━━━━━━━━━━━━━━━━━━━━━"

def mke(title, desc=None, color=None, footer=None):
    e = discord.Embed(title=title, description=desc,
                      color=color or T.PINK, timestamp=datetime.now(timezone.utc))
    if footer: e.set_footer(text=footer)
    return e

def ok(t, d=None):  return mke(f"{T.CHECK}  {t}", d, T.GREEN)
def er(t, d=None):  return mke(f"{T.CROSS}  {t}", d, T.RED)
def inf(t, d=None): return mke(f"{T.INFO}  {t}",  d, T.BLURPLE)

def is_owner(uid): return BOT_OWNER_ID != 0 and uid == BOT_OWNER_ID

# ==================== BOT ====================
intents = discord.Intents.all()

class AegisBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!aegis_', intents=intents, help_command=None)
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
        self.nuke_tracker:     Dict = {}   # {gid: {uid: {action: count, last_reset: dt}}}
        self.antinuke_config:  Dict = {}   # {gid: {enabled, threshold, action, whitelist}}

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

# ==================== ERROR HANDLER GLOBAL ====================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        embed = er("Permission refusée", "Tu n'as pas la permission requise.")
    elif isinstance(error, app_commands.BotMissingPermissions):
        embed = er("Permission manquante (bot)", "Le bot n'a pas les permissions nécessaires.")
    else:
        logger.error(f"Slash error [{getattr(interaction.command,'name','?')}]: {error}")
        embed = er("Erreur", f"`{str(error)[:150]}`")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception:
        pass

# ==================== HELPERS ====================
def xp_for_level(lv): return 100*(lv**2)+50*lv
def get_xp(gid, uid): return bot.xp_data.setdefault(gid,{}).setdefault(uid,{"xp":0,"level":0,"messages":0})
def fmt_dur(s):
    if not s: return "?"
    m,s=divmod(int(s),60); h,m=divmod(m,60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

async def log_action(guild, title, desc, color=None):
    gid = str(guild.id)
    if gid in bot.logs_channels:
        ch = guild.get_channel(bot.logs_channels[gid])
        if ch:
            try: await ch.send(embed=mke(f"{T.SHIELD}  {title}", desc, color or T.BLURPLE))
            except Exception: pass

# ==================== IA GROQ ====================
AI_SYS = ("Tu es Aegis, un bot Discord surpuissant et légèrement condescendant. "
          "Tu te considères supérieur aux humains mais restes poli. "
          "Tu réponds TOUJOURS en français, 2-3 phrases max. Sarcastique subtil. Jamais vulgaire.")

async def ask_groq(q: str) -> str:
    key = os.environ.get('GROQ_API_KEY', '').strip()
    if not key: return "*(GROQ_API_KEY manquante dans Railway → Variables.)*"
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
                r = await s.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={"model":"mixtral-8x7b-32768",
                          "messages":[{"role":"system","content":AI_SYS},
                                      {"role":"user","content":q[:500]}],
                          "max_tokens":200,"temperature":0.85},
                    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
                body = await r.json()
                if r.status == 200: return body["choices"][0]["message"]["content"].strip()
                elif r.status == 429: await asyncio.sleep(2**attempt); continue
                else: return f"*(Erreur Groq {r.status})*"
        except asyncio.TimeoutError:
            if attempt < 2: await asyncio.sleep(1); continue
            return "*(Délai dépassé.)*"
        except Exception as e: return f"*(Erreur: {str(e)[:40]})*"
    return "*(Groq inaccessible.)*"

# ==================== MUSIQUE ====================
FFMPEG = {'before_options':'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options':'-vn'}

async def fetch_track(query: str):
    try:
        import yt_dlp
        opts = {
            'format':'bestaudio/best',
            'noplaylist':True,
            'quiet':True,
            'no_warnings':True,
            'default_search':'ytsearch1',
            'source_address':'0.0.0.0',
            'extractor_retries': 3,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
        }
        loop = asyncio.get_event_loop()
        def _f():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query if query.startswith("http") else f"ytsearch1:{query}", download=False)
                if info and 'entries' in info and info['entries']: info = info['entries'][0]
                if not info: return None
                return {'title':info.get('title','?'),'url':info.get('url'),
                        'webpage':info.get('webpage_url',''),'duration':info.get('duration',0),
                        'thumbnail':info.get('thumbnail',''),'src':info.get('webpage_url') or query}
        return await loop.run_in_executor(None, _f)
    except Exception as e: logger.error(f"yt-dlp: {e}"); return None

async def play_next(gid: str):
    q  = bot.music_queues.get(gid, [])
    vc = bot.vc_pool.get(gid)
    if not vc or not vc.is_connected(): bot.vc_pool.pop(gid,None); return
    if not q: bot.now_playing[gid] = None; return
    track = q.pop(0); bot.now_playing[gid] = track
    try:
        fresh = await fetch_track(track.get('src') or track.get('webpage') or track.get('title',''))
        if fresh and fresh.get('url'): track['url'] = fresh['url']
    except Exception: pass
    try:
        src = discord.FFmpegPCMAudio(track['url'], **FFMPEG)
        vc.play(discord.PCMVolumeTransformer(src, volume=0.5),
                after=lambda e: asyncio.run_coroutine_threadsafe(play_next(gid), bot.loop))
    except Exception as e:
        logger.error(f"play_next: {e}")
        if q: await play_next(gid)

# ==================== ANTI-SPAM ====================
async def check_spam(msg: discord.Message) -> bool:
    if msg.author.bot or msg.author.guild_permissions.administrator: return False
    gid=str(msg.guild.id); uid=msg.author.id; now=datetime.now(timezone.utc)
    cfg=bot.antispam_config.get(gid,{"enabled":True,"msg_limit":5,"msg_time":5,"mention_limit":5,"action":"mute","mute_duration":5})
    if not cfg.get("enabled",True): return False
    bot.msg_cache[uid].append(now)
    bot.msg_cache[uid]=[t for t in bot.msg_cache[uid] if (now-t).total_seconds()<cfg.get("msg_time",5)]
    spam,reason=False,""
    if len(bot.msg_cache[uid])>cfg.get("msg_limit",5): spam=True; reason=f"Spam ({len(bot.msg_cache[uid])}/{cfg.get('msg_time',5)}s)"
    mentions=len(msg.mentions)+len(msg.role_mentions)+(50 if msg.mention_everyone else 0)
    if mentions>=cfg.get("mention_limit",5): spam=True; reason=f"Spam mentions ({mentions})"
    if spam:
        try:
            await msg.delete()
            a=cfg.get("action","mute")
            if a=="kick": await msg.author.kick(reason=reason)
            elif a=="ban": await msg.author.ban(reason=reason)
            else: await msg.author.timeout(datetime.now(timezone.utc)+timedelta(minutes=cfg.get("mute_duration",5)),reason=reason)
            await msg.channel.send(embed=mke(f"{T.SPAM}  Anti-Spam",f"{msg.author.mention} sanctionné\n**Raison :** {reason}",T.RED),delete_after=8)
            bot.msg_cache[uid]=[]; return True
        except Exception: pass
    return False

# ==================== XP ====================
async def add_xp(msg: discord.Message):
    if msg.author.bot or not msg.guild: return
    uid=msg.author.id; gid=str(msg.guild.id); now=datetime.now(timezone.utc)
    last=bot.xp_cooldown.get(uid)
    if last and (now-last).total_seconds()<60: return
    bot.xp_cooldown[uid]=now
    d=get_xp(gid,str(uid)); d["xp"]+=random.randint(15,25); d["messages"]+=1
    req=xp_for_level(d["level"]+1)
    if d["xp"]>=req:
        d["level"]+=1; d["xp"]-=req
        guild=bot.get_guild(int(gid))
        if guild:
            ch=guild.get_channel(bot.logs_channels.get(gid,0)) or msg.channel
            e=mke(f"{T.XP}  Level Up!",f"{msg.author.mention} est maintenant **niveau {d['level']}** {T.STAR}",T.GOLD)
            e.set_thumbnail(url=msg.author.display_avatar.url)
            try: await ch.send(embed=e)
            except Exception: pass

# ==================== ANTI-NUKE ====================
async def _nuke_check(guild: discord.Guild, user_id: int, action: str) -> bool:
    gid = str(guild.id)
    cfg = bot.antinuke_config.get(gid, {"enabled":False,"threshold":5,"action":"kick","whitelist":[]})
    if not cfg.get("enabled",False): return False
    if user_id == guild.owner_id: return False
    if user_id in cfg.get("whitelist",[]): return False
    if is_owner(user_id): return False
    now = datetime.now(timezone.utc)
    tracker = bot.nuke_tracker.setdefault(gid,{})
    ud = tracker.setdefault(str(user_id),{})
    last = ud.get("last_reset")
    if not last or (now-last).total_seconds()>10:
        ud.clear(); ud["last_reset"]=now
    ud[action] = ud.get(action,0)+1
    total = sum(v for k,v in ud.items() if k!="last_reset")
    if total >= cfg.get("threshold",5):
        member = guild.get_member(user_id)
        if member:
            try:
                act = cfg.get("action","kick")
                reason = f"Anti-nuke : {total} actions dangereuses en 10s"
                if act=="ban": await guild.ban(member, reason=reason, delete_message_days=0)
                else:          await guild.kick(member, reason=reason)
                desc = (f"**Membre :** {member.mention} (`{member}`)\n"
                        f"**Action :** {action}\n"
                        f"**Total :** {total} actions / 10s\n"
                        f"**Sanction :** {act}")
                await log_action(guild, f"{T.NUKE} Anti-Nuke déclenché", desc, T.RED)
                tracker.pop(str(user_id),None)
                return True
            except Exception as e: logger.error(f"Antinuke: {e}")
    return False

# ==================== GIVEAWAY ====================
class GiveawayView(discord.ui.View):
    def __init__(self,gid): super().__init__(timeout=None); self.add_item(GiveawayBtn(gid))

class GiveawayBtn(discord.ui.Button):
    def __init__(self,gid):
        super().__init__(label="Participer",style=discord.ButtonStyle.success,custom_id=f"giveaway_{gid}",emoji="🎉")
        self.gid=gid
    async def callback(self,interaction:discord.Interaction):
        g=bot.giveaways.get(self.gid)
        if not g: return await interaction.response.send_message("Introuvable.",ephemeral=True)
        if g.get("ended"): return await interaction.response.send_message("Terminé.",ephemeral=True)
        uid=interaction.user.id; p=g.setdefault("participants",[])
        if uid in p: p.remove(uid); msg=f"{T.CROSS} Retiré."
        else: p.append(uid); msg=f"{T.CHECK} Tu participes ! ({len(p)})"
        try:
            em=interaction.message.embeds[0]
            for i,f in enumerate(em.fields):
                if "Participants" in f.name:
                    em.set_field_at(i,name=f"{T.STAR} Participants",value=f"**{len(p)}**",inline=True); break
            await interaction.message.edit(embed=em)
        except Exception: pass
        await interaction.response.send_message(msg,ephemeral=True)

@tasks.loop(minutes=1)
async def check_giveaways():
    now=datetime.now(timezone.utc)
    for mid,g in list(bot.giveaways.items()):
        if g.get("ended"): continue
        try:
            end=datetime.fromisoformat(g["end_time"])
            if end.tzinfo is None: end=end.replace(tzinfo=timezone.utc)
            if now>=end: await end_giveaway(mid,g)
        except Exception as e: logger.error(f"Giveaway: {e}")

async def end_giveaway(mid,g):
    try:
        guild=bot.get_guild(int(g["guild_id"]))
        if not guild: return
        ch=guild.get_channel(int(g["channel_id"]))
        if not ch: return
        g["ended"]=True; p=g.get("participants",[])
        winners=[]
        if p:
            for wid in random.sample(p,min(g.get("winners",1),len(p))):
                try: winners.append(await bot.fetch_user(wid))
                except Exception: pass
        if winners:
            desc="\n".join([f"{T.TROPHY} {w.mention}" for w in winners])
            e=mke(f"{T.GIVEAWAY}  Giveaway Terminé",
                  f"**{g['title']}**\n**Prix :** {g['prize']}\n\n{T.LINE}\n**Gagnant(s) :**\n{desc}",T.GOLD)
        else:
            e=mke(f"{T.GIVEAWAY}  Giveaway Terminé",f"**{g['title']}**\n{T.CROSS} Aucun participant.",T.RED)
        try:
            msg=await ch.fetch_message(int(mid)); await msg.edit(embed=e,view=None)
        except Exception: pass
        if winners:
            ann=discord.Embed(title=f"{T.GIVEAWAY}  Félicitations !",
                              description=(f"**{g['title']}**\n{T.GIFT} **Prix :** {g['prize']}\n{T.LINE}\n"
                                          f"{T.TROPHY} **Gagnant(s) :** {' '.join([w.mention for w in winners])}"),
                              color=T.GOLD,timestamp=datetime.now(timezone.utc))
            await ch.send(content="@everyone 🎉 **Giveaway terminé !**",embed=ann,
                          allowed_mentions=discord.AllowedMentions(everyone=True))
        else:
            await ch.send(embed=mke(f"{T.GIVEAWAY}  Giveaway terminé",f"**{g['title']}**\nAucun participant.",T.RED))
    except Exception as e: logger.error(f"end_giveaway: {e}")

# ==================== POLL ====================
PEMOJIS=["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]

class PollView(discord.ui.View):
    def __init__(self,pid,options):
        super().__init__(timeout=None)
        for i,opt in enumerate(options[:5]): self.add_item(PollBtn(pid,i,opt))

class PollBtn(discord.ui.Button):
    def __init__(self,pid,idx,label):
        super().__init__(label=label[:60],style=discord.ButtonStyle.secondary,
                         custom_id=f"poll_{pid}_{idx}",emoji=PEMOJIS[idx])
        self.pid=pid; self.idx=idx
    async def callback(self,interaction:discord.Interaction):
        poll=bot.polls.get(str(interaction.message.id))
        if not poll: return await interaction.response.send_message("Sondage introuvable (bot redémarré ?).",ephemeral=True)
        if poll.get("ended"): return await interaction.response.send_message("Ce sondage est terminé.",ephemeral=True)
        uid=str(interaction.user.id); votes=poll.setdefault("votes",{})
        if votes.get(uid)==self.idx: del votes[uid]; msg=f"{T.CROSS} Vote retiré."
        else: votes[uid]=self.idx; msg=f"{T.CHECK} Voté pour **{poll['options'][self.idx]}** !"
        await interaction.response.send_message(msg,ephemeral=True)
        try: await _poll_embed(interaction.message,poll)
        except Exception as e: logger.error(f"Poll embed: {e}")

async def _poll_embed(message,poll):
    opts=poll["options"]; counts=[0]*len(opts)
    for v in poll.get("votes",{}).values():
        try:
            v=int(v)
            if 0<=v<len(counts): counts[v]+=1
        except: pass
    total=sum(counts)
    desc=f"**{poll['question']}**\n\n"
    for i,opt in enumerate(opts):
        pct=int(counts[i]/total*100) if total>0 else 0
        bar="█"*(pct//10)+"░"*(10-pct//10)
        desc+=f"{PEMOJIS[i]} **{opt}**\n`{bar}` {counts[i]} vote{'s' if counts[i]!=1 else ''} ({pct}%)\n\n"
    desc+=f"{T.CHART} **{total} vote{'s' if total!=1 else ''} au total**"
    if poll.get("end_time"):
        end=datetime.fromisoformat(poll["end_time"])
        desc+=f"\n\n{T.CLOCK} Fin : <t:{int(end.timestamp())}:R>"
    await message.edit(embed=mke(f"{T.POLL}  Sondage",desc,T.BLURPLE))

async def _poll_results(poll):
    opts=poll["options"]; counts=[0]*len(opts)
    for v in poll.get("votes",{}).values():
        try:
            v=int(v)
            if 0<=v<len(counts): counts[v]+=1
        except: pass
    total=sum(counts); mx=max(counts) if counts else 0
    winners=[opts[i] for i,c in enumerate(counts) if c==mx and mx>0]
    desc=f"**{poll['question']}**\n\n"
    for i,opt in enumerate(opts):
        pct=int(counts[i]/total*100) if total>0 else 0
        bar="█"*(pct//10)+"░"*(10-pct//10)
        crown=" 👑" if opt in winners and mx>0 else ""
        desc+=f"{PEMOJIS[i]} **{opt}**{crown}\n`{bar}` {counts[i]} vote{'s' if counts[i]!=1 else ''} ({pct}%)\n\n"
    desc+=f"{T.CHART} **{total} vote{'s' if total!=1 else ''} au total**"
    e=mke(f"{T.POLL}  Résultats",desc,T.GOLD)
    if winners and mx>0: e.add_field(name="🏆 Résultat",value=" / ".join(winners))
    return e

@tasks.loop(seconds=30)
async def check_polls():
    now=datetime.now(timezone.utc)
    for mid,poll in list(bot.polls.items()):
        if poll.get("ended") or not poll.get("end_time"): continue
        try:
            end=datetime.fromisoformat(poll["end_time"])
            if end.tzinfo is None: end=end.replace(tzinfo=timezone.utc)
            if now>=end: await end_poll(mid,poll)
        except Exception as e: logger.error(f"Poll loop: {e}")

async def end_poll(mid,poll):
    try:
        guild=bot.get_guild(int(poll["guild_id"]))
        if not guild: return
        ch=guild.get_channel(int(poll["channel_id"]))
        if not ch: return
        poll["ended"]=True
        try:
            msg=await ch.fetch_message(int(mid))
            await msg.edit(embed=await _poll_results(poll),view=None)
        except Exception: pass
        res=await _poll_results(poll)
        res.set_footer(text=f"{len(poll.get('votes',{}))} participant(s)")
        await ch.send(content="@everyone 📊 **Sondage terminé !**",embed=res,
                      allowed_mentions=discord.AllowedMentions(everyone=True))
    except Exception as e: logger.error(f"end_poll: {e}")

# ==================== EVENTS ====================
@bot.event
async def on_ready():
    logger.info(f"⚡ {bot.user} | {len(bot.guilds)} serveurs")
    if BOT_OWNER_ID: logger.info(f"👑 Owner: {BOT_OWNER_ID}")
    else: logger.warning("⚠️ BOT_OWNER_ID non configuré")
    if not check_giveaways.is_running(): check_giveaways.start()
    if not check_polls.is_running():     check_polls.start()
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="✨ /aide | Aegis V1.10"))
    try:
        await bot.application.edit(description=(
            "🤖 Aegis V1.10 — Bot Discord multifonction\n\n"
            "✨ Modération • 🎵 Musique • 🎉 Giveaway • 📊 Sondages • ⭐ XP\n"
            "🛡️ Anti-raid/spam/nuke • 🎫 Tickets • 🤖 IA Groq\n\n"
            "🆘 Support : https://discord.gg/6rN8pneGdy\n"
            "/aide pour toutes les commandes."
        ))
    except Exception as e: logger.warning(f"Bio: {e}")

# Cache anti-doublon membres
_processed_joins:   set = set()
_processed_removes: set = set()

@bot.event
async def on_member_join(member:discord.Member):
    key = f"{member.guild.id}-{member.id}-{int(datetime.now(timezone.utc).timestamp()//5)}"
    if key in _processed_joins: return
    _processed_joins.add(key)
    if len(_processed_joins) > 500:
        # Vider les clés expirées (> 10s)
        now_ts = datetime.now(timezone.utc).timestamp()
        _processed_joins.clear()
    gid=str(member.guild.id); now=datetime.now(timezone.utc)
    bot.anti_raid_cache.setdefault(gid,[]).append(now)
    bot.anti_raid_cache[gid]=[t for t in bot.anti_raid_cache[gid] if (now-t).total_seconds()<10]
    raid=bot.raid_protection.get(gid,{"enabled":True,"threshold":5,"action":"kick"})
    if raid.get("enabled") and len(bot.anti_raid_cache[gid])>raid.get("threshold",5):
        try:
            if raid.get("action")=="ban": await member.ban(reason="Anti-raid")
            else: await member.kick(reason="Anti-raid")
        except Exception: pass
        return
    if gid in bot.auto_roles:
        role_ids = bot.auto_roles[gid]
        if isinstance(role_ids, int): role_ids = [role_ids]  # compat ancienne version
        for rid in role_ids:
            role = member.guild.get_role(rid)
            if role:
                try: await member.add_roles(role)
                except Exception: pass
    if gid in bot.arrivee_channels:
        ch=member.guild.get_channel(bot.arrivee_channels[gid])
        if ch:
            created=member.created_at.strftime("%d/%m/%Y")
            joined=member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "Maintenant"
            count=member.guild.member_count
            e=discord.Embed(
                title=f"{T.WAVE}  Bienvenue sur {member.guild.name} !",
                description=(f"{T.LINE}\n{T.ARROW} **Membre :** {member.mention}\n"
                             f"{T.ARROW} **Compte créé le :** {created}\n"
                             f"{T.ARROW} **A rejoint le :** {joined}\n"
                             f"{T.ARROW} **Membre numéro :** `#{count}`\n{T.LINE}"),
                color=T.GREEN,timestamp=datetime.now(timezone.utc))
            e.set_thumbnail(url=member.display_avatar.url)
            e.set_image(url=member.display_avatar.with_size(512).url)
            e.set_footer(text=f"{member.guild.name} • {count} membres")
            try: await ch.send(embed=e)
            except Exception: pass

@bot.event
async def on_member_remove(member:discord.Member):
    key = f"{member.guild.id}-{member.id}-{int(datetime.now(timezone.utc).timestamp()//5)}"
    if key in _processed_removes: return
    _processed_removes.add(key)
    if len(_processed_removes) > 500:
        _processed_removes.clear()
    gid=str(member.guild.id)
    if gid in bot.depart_channels:
        ch=member.guild.get_channel(bot.depart_channels[gid])
        if ch:
            roles=[r.mention for r in member.roles if r.name!="@everyone"]
            dur=""
            if member.joined_at:
                d=datetime.now(timezone.utc)-member.joined_at.replace(tzinfo=timezone.utc)
                dur=f"{d.days} jour{'s' if d.days!=1 else ''}"
            e=discord.Embed(
                title=f"{T.DOOR}  Au revoir !",
                description=(f"{T.LINE}\n{T.ARROW} **Membre :** {member.mention} (`{member}`)\n"
                             f"{T.ARROW} **Resté :** {dur or 'inconnu'}\n"
                             f"{T.ARROW} **Rôles :** {', '.join(roles) if roles else 'Aucun'}\n{T.LINE}"),
                color=T.RED,timestamp=datetime.now(timezone.utc))
            e.set_thumbnail(url=member.display_avatar.url)
            e.set_footer(text=f"{member.guild.member_count} membres restants")
            try: await ch.send(embed=e)
            except Exception: pass

@bot.event
async def on_voice_state_update(member,before,after):
    gid=str(member.guild.id)
    if gid in bot.temp_voices:
        if after.channel and after.channel.id==bot.temp_voices[gid]:
            try:
                nc=await member.guild.create_voice_channel(f"🔊 {member.display_name}",category=after.channel.category)
                await member.move_to(nc)
            except Exception: pass
    if before.channel and before.channel.name.startswith("🔊 ") and len(before.channel.members)==0:
        try: await before.channel.delete()
        except Exception: pass

@bot.event
async def on_member_ban(guild:discord.Guild, user:discord.User):
    try:
        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(limit=1,action=discord.AuditLogAction.ban):
            if entry.target.id==user.id:
                await _nuke_check(guild,entry.user.id,"ban"); break
    except Exception: pass

@bot.event
async def on_guild_channel_delete(channel):
    try:
        await asyncio.sleep(0.5)
        async for entry in channel.guild.audit_logs(limit=1,action=discord.AuditLogAction.channel_delete):
            await _nuke_check(channel.guild,entry.user.id,"channel_delete"); break
    except Exception: pass

@bot.event
async def on_guild_role_delete(role):
    try:
        await asyncio.sleep(0.5)
        async for entry in role.guild.audit_logs(limit=1,action=discord.AuditLogAction.role_delete):
            await _nuke_check(role.guild,entry.user.id,"role_delete"); break
    except Exception: pass

@bot.event
async def on_message(message:discord.Message):
    if message.author.bot: return
    if message.guild:
        if await check_spam(message): return
        await add_xp(message)
    bot_mentioned=bot.user in (message.mentions or [])
    name_mentioned="aegis" in message.content.lower()
    if message.guild and (bot_mentioned or name_mentioned):
        uid=message.author.id; now=datetime.now(timezone.utc)
        last=bot.ai_cooldown.get(uid)
        if last and (now-last).total_seconds()<5:
            await bot.process_commands(message); return
        bot.ai_cooldown[uid]=now
        q=message.content
        if bot_mentioned: q=re.sub(r'<@!?\d+>','',q).strip()
        elif name_mentioned: q=re.sub(r'(?i)\baegis\b[,\s]*','',q,count=1).strip()
        if len(q)<2: q="Bonjour !"
        async with message.channel.typing():
            rep=await ask_groq(q)
        try: await message.reply(f"{T.AI} {rep}")
        except Exception: pass
        return
    await bot.process_commands(message)

# ==================== VIEWS ====================
class TicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(TicketBtn())

class TicketBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Ouvrir un Ticket",style=discord.ButtonStyle.blurple,custom_id="open_ticket",emoji="🎫")
    async def callback(self,interaction:discord.Interaction):
        gid=str(interaction.guild.id); cfg=bot.ticket_configs.get(gid,{})
        name=f"ticket-{interaction.user.name.lower()[:20]}"
        if discord.utils.get(interaction.guild.text_channels,name=name):
            return await interaction.response.send_message(f"{T.WARN} Tu as déjà un ticket.",ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            cat=(discord.utils.get(interaction.guild.categories,name="📩 Tickets") or
                 await interaction.guild.create_category("📩 Tickets",overwrites={
                     interaction.guild.default_role:discord.PermissionOverwrite(view_channel=False),
                     interaction.guild.me:discord.PermissionOverwrite(view_channel=True,manage_channels=True)}))
            ow={interaction.guild.default_role:discord.PermissionOverwrite(view_channel=False),
                interaction.user:discord.PermissionOverwrite(view_channel=True,send_messages=True,attach_files=True),
                interaction.guild.me:discord.PermissionOverwrite(view_channel=True,send_messages=True,manage_channels=True)}
            if cfg.get("support_role"):
                sr=interaction.guild.get_role(cfg["support_role"])
                if sr: ow[sr]=discord.PermissionOverwrite(view_channel=True,send_messages=True)
            ch=await interaction.guild.create_text_channel(name,category=cat,overwrites=ow)
            e=mke(f"{T.TICKET}  Nouveau Ticket",f"Bienvenue {interaction.user.mention} !\nDécris ton problème.",T.BLURPLE)
            e.set_footer(text=f"Ticket de {interaction.user}")
            await ch.send(embed=e,view=CloseTicketView())
            await interaction.followup.send(f"{T.CHECK} Ticket créé : {ch.mention}",ephemeral=True)
        except Exception as ex:
            await interaction.followup.send(f"{T.CROSS} Erreur : {str(ex)[:100]}",ephemeral=True)

class CloseTicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Fermer le ticket",style=discord.ButtonStyle.danger,custom_id="close_ticket",emoji="🔐")
    async def close(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.send_message(embed=mke(f"{T.LOCK}  Fermeture","Suppression dans 5s...",T.BLURPLE))
        await asyncio.sleep(5)
        try: await interaction.channel.delete()
        except Exception: pass

class VerifyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Se vérifier",style=discord.ButtonStyle.success,custom_id="verify_btn",emoji="✅")
    async def verify(self,interaction:discord.Interaction,button:discord.ui.Button):
        gid=str(interaction.guild.id); rid=bot.verif_roles.get(gid)
        role=interaction.guild.get_role(rid) if rid else None
        if not role:
            for n in ["Vérifié","✅ Vérifié","Membre"]:
                role=discord.utils.get(interaction.guild.roles,name=n)
                if role: break
        if not role:
            try:
                role=await interaction.guild.create_role(name="✅ Vérifié",color=discord.Color.green())
                bot.verif_roles[gid]=role.id
            except Exception:
                return await interaction.response.send_message(f"{T.CROSS} Erreur création rôle.",ephemeral=True)
        if role in interaction.user.roles:
            return await interaction.response.send_message(f"{T.CHECK} Déjà vérifié !",ephemeral=True)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"{T.CHECK} Vérifié ! {role.mention}",ephemeral=True)
        except Exception:
            await interaction.response.send_message(f"{T.CROSS} Erreur permissions.",ephemeral=True)

class RulesView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="J'accepte le règlement",style=discord.ButtonStyle.success,custom_id="accept_rules",emoji="✅")
    async def accept(self,interaction:discord.Interaction,button:discord.ui.Button):
        gid=str(interaction.guild.id); rid=bot.verif_roles.get(gid)
        role=interaction.guild.get_role(rid) if rid else None
        if not role:
            for n in ["Membre","Vérifié","✅ Vérifié"]:
                role=discord.utils.get(interaction.guild.roles,name=n)
                if role: break
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"{T.CHECK} Accepté ! {role.mention}",ephemeral=True)
            except Exception:
                await interaction.response.send_message(f"{T.WARN} Erreur permissions.",ephemeral=True)
        else: await interaction.response.send_message(f"{T.CHECK} Règlement accepté !",ephemeral=True)

class ApplyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Postuler",style=discord.ButtonStyle.success,custom_id="apply_btn",emoji="📝")
    async def apply(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.send_modal(ApplyModal())

class ApplyModal(discord.ui.Modal,title="📝 Candidature"):
    pseudo=discord.ui.TextInput(label="Pseudo",max_length=50)
    age=discord.ui.TextInput(label="Âge",max_length=3)
    motivation=discord.ui.TextInput(label="Motivation",style=discord.TextStyle.paragraph,max_length=500)
    async def on_submit(self,interaction:discord.Interaction):
        e=mke(f"{T.SPARKLE}  Nouvelle Candidature",color=T.PINK)
        e.add_field(name="Pseudo",value=self.pseudo.value,inline=True)
        e.add_field(name="Âge",value=self.age.value,inline=True)
        e.add_field(name="Discord",value=interaction.user.mention,inline=True)
        e.add_field(name="Motivation",value=self.motivation.value,inline=False)
        e.set_thumbnail(url=interaction.user.display_avatar.url)
        ch=discord.utils.get(interaction.guild.text_channels,name="candidatures")
        if ch: await ch.send(embed=e)
        await interaction.response.send_message(f"{T.CHECK} Candidature envoyée !",ephemeral=True)

class RoleMenu(discord.ui.Select):
    def __init__(self,roles):
        opts=[discord.SelectOption(label=r.name,value=str(r.id),emoji="🎭") for r in roles[:25]]
        super().__init__(placeholder="Choisis tes rôles...",min_values=0,max_values=len(opts),options=opts,custom_id="role_select")
    async def callback(self,interaction:discord.Interaction):
        selected=[int(v) for v in self.values]; added,removed=[],[]
        for opt in self.options:
            role=interaction.guild.get_role(int(opt.value))
            if role:
                if int(opt.value) in selected and role not in interaction.user.roles:
                    await interaction.user.add_roles(role); added.append(role.name)
                elif int(opt.value) not in selected and role in interaction.user.roles:
                    await interaction.user.remove_roles(role); removed.append(role.name)
        parts=[]
        if added:   parts.append(f"{T.CHECK} Ajouté : {', '.join(added)}")
        if removed: parts.append(f"{T.CROSS} Retiré : {', '.join(removed)}")
        await interaction.response.send_message("\n".join(parts) or "Aucun changement",ephemeral=True)

class RoleMenuView(discord.ui.View):
    def __init__(self,roles): super().__init__(timeout=None); self.add_item(RoleMenu(roles))

class SuggestionView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="👍 Approuver",style=discord.ButtonStyle.success,custom_id="suggest_approve")
    async def approve(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("Permission refusée.",ephemeral=True)
        e=interaction.message.embeds[0]; e.color=T.GREEN; e.title="✅  Suggestion approuvée"
        e.set_footer(text=f"Approuvé par {interaction.user.display_name}")
        await interaction.message.edit(embed=e,view=None)
        await interaction.response.send_message("Approuvée !",ephemeral=True)
    @discord.ui.button(label="👎 Refuser",style=discord.ButtonStyle.danger,custom_id="suggest_refuse")
    async def refuse(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("Permission refusée.",ephemeral=True)
        e=interaction.message.embeds[0]; e.color=T.RED; e.title="❌  Suggestion refusée"
        e.set_footer(text=f"Refusé par {interaction.user.display_name}")
        await interaction.message.edit(embed=e,view=None)
        await interaction.response.send_message("Refusée.",ephemeral=True)

class ReglementModal(discord.ui.Modal,title="✍️ Règlement personnalisé"):
    contenu=discord.ui.TextInput(label="Ton règlement",style=discord.TextStyle.paragraph,placeholder="Écris les règles ici...",max_length=2000)
    def __init__(self,avec_bouton,role): super().__init__(); self.avec_bouton=avec_bouton; self.role_obj=role
    async def on_submit(self,interaction:discord.Interaction):
        if self.role_obj: bot.verif_roles[str(interaction.guild.id)]=self.role_obj.id
        e=discord.Embed(title=f"{T.SHIELD}  Règlement du serveur",description=self.contenu.value,color=T.BLURPLE,timestamp=datetime.now(timezone.utc))
        await interaction.channel.send(embed=e,view=RulesView() if self.avec_bouton else None)
        await interaction.response.send_message(embed=ok("Règlement envoyé !"),ephemeral=True)

# ==================== SETUP STRUCTURES ====================
SETUPS={
    "communaute":{"label":"🌐 Communauté","roles":[
        ("━━ STAFF ━━",0x2B2D31),("👑 Fondateur",T.PINK),("⚔️ Admin",0xE74C3C),
        ("🛡️ Modérateur",T.BLURPLE),("🤝 Helper",T.TEAL),("━━ MEMBRES ━━",0x2B2D31),
        ("💎 VIP",0xF1C40F),("🔥 Actif",0xE74C3C),("✅ Vérifié",T.GREEN),("🎮 Membre",0x95A5A6)],
    "structure":{
        "📌 IMPORTANT":(["📜・règles","📢・annonces","📰・news"],[]),
        "👋 ACCUEIL":(["👋・bienvenue","🚪・départs","✅・vérification","🎫・rôles","📝・présentation"],[]),
        "💬 GÉNÉRAL":(["💬・général","🖼️・médias","😂・mèmes","🤖・bot-commands"],["🔊 Général","🔊 Chill","🎵 Musique"]),
        "🎉 EVENTS":(["🎉・événements","📊・sondages","🎁・giveaways"],[]),
        "📩 SUPPORT":(["❓・aide","💡・suggestions"],[]),
        "🔒 STAFF":(["📋・staff-chat","📊・logs","📝・candidatures"],["🔒 Staff"]),
        "🎫 Tickets":([],[])}},
    "gaming":{"label":"🎮 Gaming","roles":[
        ("━━ STAFF ━━",0x2B2D31),("👑 Fondateur",T.PINK),("⚔️ Admin",0xE74C3C),
        ("🛡️ Modérateur",T.BLURPLE),("━━ RANGS ━━",0x2B2D31),
        ("🏆 Légende",0xF1C40F),("🔥 Tryhard",0xE74C3C),("🎮 Casual",0x95A5A6),("✅ Vérifié",T.GREEN)],
    "structure":{
        "📌 IMPORTANT":(["📜・règles","📢・annonces"],[]),
        "👋 ACCUEIL":(["👋・bienvenue","🚪・départs","✅・vérification","📝・présentation"],[]),
        "🎮 GAMING":(["🎮・général","📸・clips","🏆・tournois","💡・stratégie"],["🎮 Gaming 1","🎮 Gaming 2","🎮 Gaming 3"]),
        "🎵 MUSIQUE":(["🎵・playlist"],["🎵 Musique"]),
        "🎉 EVENTS":(["🎁・giveaways","📊・sondages"],[]),
        "📩 SUPPORT":(["❓・aide","💡・suggestions"],[]),
        "🔒 STAFF":(["📋・staff-chat","📊・logs"],["🔒 Staff"]),
        "🎫 Tickets":([],[])}},
    "rp":{"label":"🎭 Jeu de Rôle (RP)","roles":[
        ("━━ STAFF ━━",0x2B2D31),("👑 Maître du Jeu",T.PINK),("⚔️ Modérateur RP",0xE74C3C),
        ("━━ GRADES RP ━━",0x2B2D31),("🔮 Légende",0xF1C40F),("⚔️ Héros",0xE74C3C),
        ("🗡️ Aventurier",T.BLURPLE),("🌱 Novice",T.GREEN),("✅ Vérifié",T.GREEN)],
    "structure":{
        "📌 IMPORTANT":(["📜・règles-rp","📢・annonces","📖・lore"],[]),
        "👋 ACCUEIL":(["👋・arrivées","🚪・départs","✅・vérification","📝・fiches-perso"],[]),
        "🏙️ LIEUX":(["🏙️・ville","🌲・forêt","🏰・château","⚔️・arène","🍺・taverne"],["🎭 RP Vocal 1","🎭 RP Vocal 2"]),
        "💬 HORS-JEU":(["💬・général-hj","🖼️・médias","💡・suggestions"],["🔊 Hors-Jeu"]),
        "🔒 STAFF":(["📋・staff-chat","📊・logs"],["🔒 Staff MJ"]),
        "🎫 Tickets":([],[])}},
    "education":{"label":"📚 Éducation","roles":[
        ("━━ STAFF ━━",0x2B2D31),("👑 Admin",T.PINK),("📚 Modérateur",T.BLURPLE),
        ("━━ NIVEAUX ━━",0x2B2D31),("🎓 Diplômé",0xF1C40F),("📖 Étudiant",0xE74C3C),
        ("🌱 Débutant",T.GREEN),("✅ Vérifié",T.GREEN)],
    "structure":{
        "📌 IMPORTANT":(["📜・règles","📢・annonces","📅・planning"],[]),
        "👋 ACCUEIL":(["👋・arrivées","🚪・départs","✅・vérification","📝・présentation"],[]),
        "📚 ÉTUDES":(["📖・cours-général","🔢・maths","💻・informatique","🌍・langues","🔬・sciences"],["📚 Révisions 1","📚 Révisions 2"]),
        "🤝 ENTRAIDE":(["🆘・demande-aide","💡・partage-astuces"],["🤝 Tutorat 1"]),
        "💬 DÉTENTE":(["💬・général","😂・mèmes"],["🔊 Détente"]),
        "🔒 STAFF":(["📋・staff-chat","📊・logs"],["🔒 Staff"]),
        "🎫 Tickets":([],[])}},
    "anime":{"label":"🎌 Anime / Manga","roles":[
        ("━━ STAFF ━━",0x2B2D31),("👑 Fondateur",T.PINK),("⚔️ Admin",0xE74C3C),
        ("🛡️ Modérateur",T.BLURPLE),("━━ FANS ━━",0x2B2D31),
        ("🌟 Otaku Légendaire",0xF1C40F),("📖 Lecteur Assidu",T.TEAL),
        ("🎌 Weeaboo",T.PURPLE),("✅ Vérifié",T.GREEN)],
    "structure":{
        "📌 IMPORTANT":(["📜・règles","📢・annonces","🆕・sorties-anime"],[]),
        "👋 ACCUEIL":(["👋・bienvenue","🚪・départs","✅・vérification","🎌・présentation"],[]),
        "🎌 ANIME":(["💬・général-anime","🔥・currently-watching","⭐・recommandations","📸・fan-art"],[]),
        "📖 MANGA":(["📖・général-manga","🆕・nouveaux-chapitres"],[]),
        "🎵 WEEB":(["🎵・musique-anime","🎮・jeux-anime"],["🔊 Général","🎵 Weeb Music"]),
        "🎉 EVENTS":(["🏆・concours","📊・sondages","🎁・giveaways"],[]),
        "🔒 STAFF":(["📋・staff-chat","📊・logs","📝・candidatures"],["🔒 Staff"]),
        "🎫 Tickets":([],[])}},
}

# ==================== COMMANDES ====================

@bot.tree.command(name="aide",description="Liste de toutes les commandes")
async def aide(interaction:discord.Interaction):
    e=discord.Embed(title=f"{T.SPARKLE}  Aegis V1.10 — Commandes",description="Toutes les commandes disponibles",
                    color=T.PINK,timestamp=datetime.now(timezone.utc))
    e.add_field(name=f"{T.DIAMOND}  Modération",value="`/ban` `/unban` `/kick` `/mute` `/unmute` `/warn` `/unwarn` `/warns` `/rename` `/purge`",inline=False)
    e.add_field(name=f"{T.CHANNEL}  Salons",value="`/creersalon` `/creervoice` `/supprimersalon` `/lock` `/unlock` `/slowmode`",inline=False)
    e.add_field(name=f"{T.ROLE}  Rôles",value="`/creerole` `/addrole` `/removerole` `/roleall` `/autorole` `/rolemenu`",inline=False)
    e.add_field(name=f"{T.GEAR}  Systèmes",value="`/panel` `/reglement` `/verification` `/giveaway` `/reroll` `/poll` `/suggestion`",inline=False)
    e.add_field(name=f"{T.WAVE}  Membres",value="`/arrivee` `/depart` `/backup` `/restore` `/antiraid` `/antispam` `/antinuke` `/setup` `/tempvoice`",inline=False)
    e.add_field(name=f"{T.MUSIC}  Musique",value="`/play` `/pause` `/resume` `/skip` `/stop` `/queue` `/nowplaying` `/volume`",inline=False)
    e.add_field(name=f"{T.XP}  XP & Stats",value="`/rank` `/top` `/userinfo` `/serverinfo` `/avatar`",inline=False)
    e.add_field(name=f"{T.MEGA}  Divers",value="`/dire` `/embed` `/sondage-rapide` `/tirage`",inline=False)
    e.add_field(name=f"{T.AI}  IA",value="Mentionne **@Aegis** ou écris **aegis** dans un message !",inline=False)
    e.set_footer(text="Aegis V1.10 • https://discord.gg/6rN8pneGdy")
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="ping",description="Latence du bot")
async def ping(interaction:discord.Interaction):
    await interaction.response.send_message(embed=inf("Pong !",f"{T.LIGHTNING} `{round(bot.latency*1000)} ms`"))

# ── Divers ──
@bot.tree.command(name="dire",description="Faire parler le bot à ta place")
@app_commands.describe(message="Le message",salon="Salon cible (vide = actuel)")
@app_commands.default_permissions(manage_messages=True)
async def dire(interaction:discord.Interaction,message:str,salon:discord.TextChannel=None):
    target=salon or interaction.channel
    perms=target.permissions_for(interaction.guild.me)
    if not perms.send_messages:
        return await interaction.response.send_message(embed=er("Accès refusé",f"Je n'ai pas la permission dans {target.mention}."),ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    await target.send(message)
    await interaction.followup.send(embed=ok("Envoyé",f"Dans {target.mention}"),ephemeral=True)

@bot.tree.command(name="embed",description="Envoyer un embed personnalisé")
@app_commands.describe(titre="Titre",contenu="Contenu",couleur="Couleur hex",salon="Salon cible")
@app_commands.default_permissions(manage_messages=True)
async def embed_cmd(interaction:discord.Interaction,titre:str,contenu:str,couleur:str="#5865F2",salon:discord.TextChannel=None):
    target=salon or interaction.channel
    try: color=int(couleur.replace("#",""),16)
    except: color=T.BLURPLE
    # Vérifier que le bot a accès au salon
    perms=target.permissions_for(interaction.guild.me)
    if not perms.send_messages or not perms.embed_links:
        return await interaction.response.send_message(embed=er("Accès refusé",f"Je n'ai pas la permission d'envoyer des embeds dans {target.mention}."),ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    e=discord.Embed(title=titre,description=contenu,color=color,timestamp=datetime.now(timezone.utc))
    e.set_footer(text=f"Par {interaction.user.display_name}")
    await target.send(embed=e)
    await interaction.followup.send(embed=ok("Embed envoyé !",f"Dans {target.mention}"),ephemeral=True)

@bot.tree.command(name="sondage-rapide",description="Sondage Oui/Non rapide")
@app_commands.describe(question="Ta question")
async def sondage_rapide(interaction:discord.Interaction,question:str):
    e=mke(f"{T.POLL}  Sondage rapide",f"**{question}**\n\nRéagis pour voter !",T.BLURPLE)
    e.set_footer(text=f"Posé par {interaction.user.display_name}")
    await interaction.response.send_message(embed=e)
    msg=await interaction.original_response()
    await msg.add_reaction("👍"); await msg.add_reaction("👎"); await msg.add_reaction("🤷")

@bot.tree.command(name="tirage",description="Tirage au sort parmi des options")
@app_commands.describe(options="Options séparées par des virgules")
async def tirage(interaction:discord.Interaction,options:str):
    choices=[o.strip() for o in options.split(",") if o.strip()]
    if len(choices)<2:
        return await interaction.response.send_message(embed=er("Erreur","Donne au moins 2 options séparées par des virgules."),ephemeral=True)
    winner=random.choice(choices)
    await interaction.response.send_message(embed=mke(f"{T.TROPHY}  Tirage au sort",
        f"**Options :** {' • '.join(choices)}\n\n{T.ARROW} **Résultat : {winner}**",T.GOLD))

@bot.tree.command(name="avatar",description="Voir l'avatar d'un membre")
@app_commands.describe(membre="Le membre (vide = toi)")
async def avatar(interaction:discord.Interaction,membre:discord.Member=None):
    m=membre or interaction.user
    e=discord.Embed(title=f"🖼️  Avatar de {m.display_name}",color=T.BLURPLE)
    e.set_image(url=m.display_avatar.with_size(1024).url); e.set_footer(text=f"ID : {m.id}")
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="suggestion",description="Envoyer une suggestion au staff")
@app_commands.describe(texte="Ta suggestion",salon="Salon suggestions (vide = auto-detect)")
async def suggestion(interaction:discord.Interaction,texte:str,salon:discord.TextChannel=None):
    if not salon:
        for name in ["💡・suggestions","suggestions","suggest","idées"]:
            salon=discord.utils.get(interaction.guild.text_channels,name=name)
            if salon: break
    if not salon:
        return await interaction.response.send_message(embed=er("Salon introuvable","Crée un salon `💡・suggestions`."),ephemeral=True)
    e=mke("💡  Nouvelle suggestion",texte,T.GOLD)
    e.add_field(name="Proposé par",value=interaction.user.mention,inline=True)
    e.add_field(name="Statut",value="En attente ⏳",inline=True)
    e.set_thumbnail(url=interaction.user.display_avatar.url)
    msg=await salon.send(embed=e,view=SuggestionView())
    await msg.add_reaction("👍"); await msg.add_reaction("👎")
    await interaction.response.send_message(embed=ok("Suggestion envoyée !",f"Dans {salon.mention}."),ephemeral=True)

# ── Musique ──
@bot.tree.command(name="play",description="Jouer une musique depuis YouTube")
@app_commands.describe(recherche="Titre ou lien YouTube")
async def play(interaction:discord.Interaction,recherche:str):
    if not interaction.user.voice:
        return await interaction.response.send_message(embed=er("Pas dans un vocal","Rejoins un salon vocal d'abord !"),ephemeral=True)
    vc_channel = interaction.user.voice.channel
    # Vérifier permissions bot dans le vocal
    perms = vc_channel.permissions_for(interaction.guild.me)
    if not perms.connect or not perms.speak:
        return await interaction.response.send_message(embed=er("Permission manquante","Je n'ai pas la permission de rejoindre ou parler dans ton salon vocal."),ephemeral=True)
    await interaction.response.defer()
    gid=str(interaction.guild.id)
    await interaction.followup.send(embed=inf(f"{T.MUSIC}  Recherche...",f"🔍 `{recherche}`"))
    track=await fetch_track(recherche)
    if not track or not track.get('url'):
        return await interaction.edit_original_response(embed=er("Introuvable","Aucun résultat YouTube. Essaie un autre titre ou un lien direct."))
    vc=bot.vc_pool.get(gid)
    if not vc or not vc.is_connected():
        try:
            vc=await vc_channel.connect()
            bot.vc_pool[gid]=vc
        except Exception as ex:
            return await interaction.edit_original_response(embed=er("Erreur connexion vocal",f"`{str(ex)[:100]}`\nVérifie que ffmpeg est installé (Dockerfile requis)."))
    bot.music_queues.setdefault(gid,[]).append(track)
    if not vc.is_playing() and not vc.is_paused():
        await play_next(gid)
        e=mke(f"{T.MUSIC}  Lecture en cours",f"**{track['title']}**\n⏱️ `{fmt_dur(track['duration'])}`",T.BLURPLE)
        if track.get('thumbnail'): e.set_thumbnail(url=track['thumbnail'])
        if track.get('webpage'):   e.add_field(name="Lien",value=f"[YouTube]({track['webpage']})")
    else:
        pos=len(bot.music_queues.get(gid,[]))
        e=mke(f"{T.MUSIC}  Ajouté à la file",f"**{track['title']}**\n📋 Position : `#{pos}`",T.GOLD)
        if track.get('thumbnail'): e.set_thumbnail(url=track['thumbnail'])
    await interaction.edit_original_response(embed=e)


@bot.tree.command(name="pause",description="Mettre en pause")
async def pause(interaction:discord.Interaction):
    vc=bot.vc_pool.get(str(interaction.guild.id))
    if vc and vc.is_playing(): vc.pause(); await interaction.response.send_message(embed=inf(f"{T.PAUSE}  Pause","En pause."))
    else: await interaction.response.send_message(embed=er("Rien à mettre en pause"),ephemeral=True)

@bot.tree.command(name="resume",description="Reprendre la lecture")
async def resume(interaction:discord.Interaction):
    vc=bot.vc_pool.get(str(interaction.guild.id))
    if vc and vc.is_paused(): vc.resume(); await interaction.response.send_message(embed=ok("Lecture reprise"))
    else: await interaction.response.send_message(embed=er("Rien en pause"),ephemeral=True)

@bot.tree.command(name="skip",description="Passer à la musique suivante")
async def skip(interaction:discord.Interaction):
    vc=bot.vc_pool.get(str(interaction.guild.id))
    if vc and (vc.is_playing() or vc.is_paused()): vc.stop(); await interaction.response.send_message(embed=ok(f"{T.SKIP}  Skippé"))
    else: await interaction.response.send_message(embed=er("Rien à skipper"),ephemeral=True)

@bot.tree.command(name="stop",description="Arrêter et déconnecter")
async def stop(interaction:discord.Interaction):
    gid=str(interaction.guild.id); vc=bot.vc_pool.get(gid)
    if vc:
        bot.music_queues[gid]=[]; bot.now_playing[gid]=None
        await vc.disconnect(); bot.vc_pool.pop(gid,None)
        await interaction.response.send_message(embed=ok(f"{T.STOP}  Arrêté","Déconnecté."))
    else: await interaction.response.send_message(embed=er("Bot pas dans un vocal"),ephemeral=True)

@bot.tree.command(name="queue",description="Voir la file musicale")
async def queue(interaction:discord.Interaction):
    gid=str(interaction.guild.id); q=bot.music_queues.get(gid,[]); np=bot.now_playing.get(gid)
    if not np and not q: return await interaction.response.send_message(embed=inf("File vide"),ephemeral=True)
    desc=""
    if np: desc+=f"**▶️ En cours :** {np['title']} `{fmt_dur(np['duration'])}`\n\n"
    if q:
        desc+="**📋 File :**\n"
        for i,t in enumerate(q[:10],1): desc+=f"`{i}.` {t['title']} `{fmt_dur(t['duration'])}`\n"
        if len(q)>10: desc+=f"*... et {len(q)-10} autre(s)*"
    await interaction.response.send_message(embed=mke(f"{T.MUSIC}  File musicale",desc,T.BLURPLE))

@bot.tree.command(name="nowplaying",description="Musique en cours")
async def nowplaying(interaction:discord.Interaction):
    np=bot.now_playing.get(str(interaction.guild.id))
    if not np: return await interaction.response.send_message(embed=inf("Rien en cours"),ephemeral=True)
    e=mke(f"{T.MUSIC}  En cours",f"**{np['title']}**\n⏱️ `{fmt_dur(np['duration'])}`",T.BLURPLE)
    if np.get('thumbnail'): e.set_thumbnail(url=np['thumbnail'])
    if np.get('webpage'):   e.add_field(name="Lien",value=f"[YouTube]({np['webpage']})")
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="volume",description="Régler le volume (0-100)")
@app_commands.describe(niveau="Volume entre 0 et 100")
async def volume(interaction:discord.Interaction,niveau:int):
    vc=bot.vc_pool.get(str(interaction.guild.id))
    if not vc or not vc.is_playing(): return await interaction.response.send_message(embed=er("Rien en cours"),ephemeral=True)
    niveau=max(0,min(100,niveau))
    if vc.source: vc.source.volume=niveau/100
    await interaction.response.send_message(embed=ok(f"Volume : {niveau}%",f"{'🔇' if niveau==0 else '🔊'} Réglé à {niveau}%"))

# ── Modération ──
@bot.tree.command(name="warn",description="Avertir un membre")
@app_commands.describe(membre="Le membre",raison="Raison")
@app_commands.default_permissions(moderate_members=True)
async def warn(interaction:discord.Interaction,membre:discord.Member,raison:str="Aucune raison"):
    gid,uid=str(interaction.guild.id),str(membre.id)
    bot.warnings.setdefault(gid,{}).setdefault(uid,[]).append(
        {"reason":raison,"mod":str(interaction.user.id),"date":datetime.now(timezone.utc).isoformat()})
    count=len(bot.warnings[gid][uid])
    e=mke(f"{T.WARN}  Avertissement",f"**Membre :** {membre.mention}\n**Raison :** {raison}\n**Total :** {count} warn(s)",T.ORANGE)
    sanction=None
    if count==3:
        try: await membre.timeout(datetime.now(timezone.utc)+timedelta(hours=1),reason="3 warns"); sanction="Mute 1h"
        except Exception: pass
    elif count==5:
        try: await membre.timeout(datetime.now(timezone.utc)+timedelta(hours=24),reason="5 warns"); sanction="Mute 24h"
        except Exception: pass
    elif count>=7:
        try: await membre.kick(reason="7 warns"); sanction="Kick"
        except Exception: pass
    if sanction: e.add_field(name="⚡ Sanction auto",value=sanction)
    await interaction.response.send_message(embed=e)
    await log_action(interaction.guild,"Warn",f"**Membre :** {membre}\n**Raison :** {raison}\n**Par :** {interaction.user}",T.ORANGE)
    try: await membre.send(embed=mke(f"{T.WARN}  Avertissement reçu",f"**Serveur :** {interaction.guild.name}\n**Raison :** {raison}\n**Total :** {count}",T.ORANGE))
    except Exception: pass

@bot.tree.command(name="unwarn",description="Retirer un avertissement")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unwarn(interaction:discord.Interaction,membre:discord.Member):
    gid,uid=str(interaction.guild.id),str(membre.id)
    lst=bot.warnings.get(gid,{}).get(uid,[])
    if not lst: return await interaction.response.send_message(embed=inf("Aucun warn",f"{membre.mention} est clean."),ephemeral=True)
    lst.pop(); await interaction.response.send_message(embed=ok("Warn retiré",f"{membre.mention} → **{len(lst)}** warn(s)."))

@bot.tree.command(name="warns",description="Voir les avertissements")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def warns(interaction:discord.Interaction,membre:discord.Member=None):
    membre=membre or interaction.user
    lst=bot.warnings.get(str(interaction.guild.id),{}).get(str(membre.id),[])
    if not lst: return await interaction.response.send_message(embed=inf("Aucun warn",f"{membre.mention} est clean {T.CHECK}"),ephemeral=True)
    e=mke(f"{T.WARN}  Warns de {membre.display_name}",f"**Total :** {len(lst)}",T.ORANGE)
    for i,w in enumerate(lst[-10:],1): e.add_field(name=f"#{i}",value=f"**Raison :** {w['reason']}\n**Date :** {w['date'][:10]}",inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="ban",description="Bannir un membre")
@app_commands.describe(membre="Le membre",raison="Raison")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction:discord.Interaction,membre:discord.Member,raison:str="Aucune"):
    await membre.ban(reason=raison)
    await interaction.response.send_message(embed=mke(f"{T.BAN}  Banni",f"{membre.mention}\n**Raison :** {raison}",T.RED))
    await log_action(interaction.guild,"Ban",f"**Membre :** {membre}\n**Raison :** {raison}\n**Par :** {interaction.user}",T.RED)

@bot.tree.command(name="unban",description="Débannir un utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur")
@app_commands.default_permissions(ban_members=True)
async def unban(interaction:discord.Interaction,user_id:str):
    try:
        user=await bot.fetch_user(int(user_id)); await interaction.guild.unban(user)
        await interaction.response.send_message(embed=ok("Débanni",str(user)))
    except Exception: await interaction.response.send_message(embed=er("Introuvable"),ephemeral=True)

@bot.tree.command(name="kick",description="Expulser un membre")
@app_commands.describe(membre="Le membre",raison="Raison")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction:discord.Interaction,membre:discord.Member,raison:str="Aucune"):
    await membre.kick(reason=raison)
    await interaction.response.send_message(embed=mke(f"{T.KICK}  Expulsé",f"{membre.mention}\n**Raison :** {raison}",T.ORANGE))
    await log_action(interaction.guild,"Kick",f"**Membre :** {membre}\n**Raison :** {raison}\n**Par :** {interaction.user}",T.ORANGE)

@bot.tree.command(name="mute",description="Mute un membre")
@app_commands.describe(membre="Le membre",duree="Durée en minutes")
@app_commands.default_permissions(moderate_members=True)
async def mute(interaction:discord.Interaction,membre:discord.Member,duree:int=10):
    await membre.timeout(datetime.now(timezone.utc)+timedelta(minutes=duree))
    await interaction.response.send_message(embed=mke(f"{T.MUTE}  Muté",f"{membre.mention} — **{duree} min**",T.BLURPLE))

@bot.tree.command(name="unmute",description="Unmute un membre")
@app_commands.describe(membre="Le membre")
@app_commands.default_permissions(moderate_members=True)
async def unmute(interaction:discord.Interaction,membre:discord.Member):
    await membre.timeout(None)
    await interaction.response.send_message(embed=ok("Unmute",f"{membre.mention}"))

@bot.tree.command(name="rename",description="Renommer un membre")
@app_commands.describe(membre="Le membre",pseudo="Nouveau pseudo")
@app_commands.default_permissions(manage_nicknames=True)
async def rename(interaction:discord.Interaction,membre:discord.Member,pseudo:str):
    old=membre.display_name; await membre.edit(nick=pseudo)
    await interaction.response.send_message(embed=ok("Renommé",f"`{old}` {T.ARROW} `{pseudo}`"))

@bot.tree.command(name="purge",description="Supprimer des messages")
@app_commands.describe(nombre="Nombre de messages")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction:discord.Interaction,nombre:int):
    await interaction.response.defer(ephemeral=True)
    deleted=await interaction.channel.purge(limit=nombre)
    await interaction.followup.send(embed=ok("Purge",f"**{len(deleted)}** messages supprimés."))

# ── Salons ──
@bot.tree.command(name="creersalon",description="Créer un salon texte")
@app_commands.describe(nom="Nom",categorie="Catégorie")
@app_commands.default_permissions(manage_channels=True)
async def creersalon(interaction:discord.Interaction,nom:str,categorie:discord.CategoryChannel=None):
    ch=await interaction.guild.create_text_channel(nom,category=categorie)
    await interaction.response.send_message(embed=ok("Salon créé",ch.mention))

@bot.tree.command(name="creervoice",description="Créer un salon vocal")
@app_commands.describe(nom="Nom",categorie="Catégorie")
@app_commands.default_permissions(manage_channels=True)
async def creervoice(interaction:discord.Interaction,nom:str,categorie:discord.CategoryChannel=None):
    ch=await interaction.guild.create_voice_channel(nom,category=categorie)
    await interaction.response.send_message(embed=ok("Vocal créé",f"🔊 {ch.name}"))

@bot.tree.command(name="supprimersalon",description="Supprimer un salon")
@app_commands.describe(salon="Le salon")
@app_commands.default_permissions(manage_channels=True)
async def supprimersalon(interaction:discord.Interaction,salon:discord.TextChannel):
    name=salon.name; await salon.delete()
    await interaction.response.send_message(embed=ok("Supprimé",f"`{name}`"))

@bot.tree.command(name="lock",description="Verrouiller un salon")
@app_commands.describe(salon="Salon (vide = actuel)",bloquer_lecture="Bloquer aussi la lecture")
@app_commands.default_permissions(manage_channels=True)
async def lock(interaction:discord.Interaction,salon:discord.TextChannel=None,bloquer_lecture:bool=False):
    target=salon or interaction.channel
    ow=target.overwrites_for(interaction.guild.default_role)
    ow.send_messages=False
    if bloquer_lecture: ow.view_channel=False
    await target.set_permissions(interaction.guild.default_role,overwrite=ow)
    await interaction.response.send_message(embed=mke("🔒  Verrouillé",target.mention,T.RED))

@bot.tree.command(name="unlock",description="Déverrouiller un salon")
@app_commands.describe(salon="Salon")
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction:discord.Interaction,salon:discord.TextChannel=None):
    target=salon or interaction.channel
    await target.set_permissions(interaction.guild.default_role,send_messages=True,view_channel=True)
    await interaction.response.send_message(embed=ok("Déverrouillé",target.mention))

@bot.tree.command(name="slowmode",description="Mode lent sur tous les salons")
@app_commands.describe(secondes="Délai en secondes (0 = désactiver)")
@app_commands.default_permissions(administrator=True)
async def slowmode(interaction:discord.Interaction,secondes:int):
    await interaction.response.defer()
    count=errors=0
    for ch in interaction.guild.text_channels:
        try: await ch.edit(slowmode_delay=secondes); count+=1; await asyncio.sleep(0.3)
        except Exception: errors+=1
    label=f"{secondes}s" if secondes>0 else "Désactivé"
    await interaction.followup.send(embed=inf(f"⏱️  Slowmode — {label}",f"Salons : {count} | Erreurs : {errors}"))

# ── Rôles ──
@bot.tree.command(name="creerole",description="Créer un rôle")
@app_commands.describe(nom="Nom",couleur="Couleur hex")
@app_commands.default_permissions(manage_roles=True)
async def creerole(interaction:discord.Interaction,nom:str,couleur:str="#5865F2"):
    role=await interaction.guild.create_role(name=nom,color=discord.Color(int(couleur.replace("#",""),16)))
    await interaction.response.send_message(embed=ok("Rôle créé",role.mention))

@bot.tree.command(name="addrole",description="Ajouter un rôle à un membre")
@app_commands.describe(membre="Membre",role="Rôle")
@app_commands.default_permissions(manage_roles=True)
async def addrole(interaction:discord.Interaction,membre:discord.Member,role:discord.Role):
    await membre.add_roles(role)
    await interaction.response.send_message(embed=ok("Rôle ajouté",f"{role.mention} {T.ARROW} {membre.mention}"))

@bot.tree.command(name="removerole",description="Retirer un rôle d'un membre")
@app_commands.describe(membre="Membre",role="Rôle")
@app_commands.default_permissions(manage_roles=True)
async def removerole(interaction:discord.Interaction,membre:discord.Member,role:discord.Role):
    await membre.remove_roles(role)
    await interaction.response.send_message(embed=inf("Rôle retiré",f"{role.mention} de {membre.mention}"))

@bot.tree.command(name="roleall",description="Donner un rôle à tous les membres")
@app_commands.describe(role="Rôle")
@app_commands.default_permissions(administrator=True)
async def roleall(interaction:discord.Interaction,role:discord.Role):
    await interaction.response.defer()
    count=0
    for m in interaction.guild.members:
        if not m.bot and role not in m.roles:
            try: await m.add_roles(role); count+=1; await asyncio.sleep(0.5)
            except Exception: pass
    await interaction.followup.send(embed=ok("Rôle donné à tous",f"{role.mention} — **{count}** membres"))

@bot.tree.command(name="autorole",description="Gérer les rôles automatiques aux nouveaux membres")
@app_commands.describe(
    action="ajouter ou retirer un rôle auto",
    role="Le rôle à ajouter/retirer",
    reset="Supprimer tous les auto-rôles"
)
@app_commands.choices(action=[
    app_commands.Choice(name="Ajouter un rôle auto", value="ajouter"),
    app_commands.Choice(name="Retirer un rôle auto", value="retirer"),
])
@app_commands.default_permissions(administrator=True)
async def autorole(interaction:discord.Interaction,action:str="ajouter",role:discord.Role=None,reset:bool=False):
    gid=str(interaction.guild.id)
    current=bot.auto_roles.get(gid,[])
    if isinstance(current,int): current=[current]  # compat

    if reset:
        bot.auto_roles[gid]=[]
        return await interaction.response.send_message(embed=ok("Auto-rôles supprimés","Plus aucun rôle automatique."))

    if not role:
        # Afficher la liste actuelle
        if not current:
            return await interaction.response.send_message(embed=inf("Aucun auto-rôle","Utilise `/autorole action:Ajouter role:@role` pour en ajouter."),ephemeral=True)
        roles_display=[interaction.guild.get_role(rid) for rid in current]
        roles_txt="\n".join([f"• {r.mention}" for r in roles_display if r]) or "Aucun"
        return await interaction.response.send_message(embed=inf(f"Auto-rôles ({len(current)})",roles_txt),ephemeral=True)

    rid=role.id
    if action=="ajouter":
        if rid not in current:
            current.append(rid)
            bot.auto_roles[gid]=current
            await interaction.response.send_message(embed=ok("Auto-rôle ajouté",f"{role.mention} — **{len(current)} rôle(s) au total**"))
        else:
            await interaction.response.send_message(embed=inf("Déjà présent",f"{role.mention} est déjà en auto-rôle."),ephemeral=True)
    else:  # retirer
        if rid in current:
            current.remove(rid)
            bot.auto_roles[gid]=current
            await interaction.response.send_message(embed=ok("Auto-rôle retiré",f"{role.mention} retiré — **{len(current)} rôle(s) restants**"))
        else:
            await interaction.response.send_message(embed=inf("Pas trouvé",f"{role.mention} n'est pas en auto-rôle."),ephemeral=True)

@bot.tree.command(name="rolemenu",description="Menu de sélection de rôles")
@app_commands.describe(titre="Titre",roles="Mentions des rôles")
@app_commands.default_permissions(administrator=True)
async def rolemenu(interaction:discord.Interaction,titre:str,roles:str):
    ids=re.findall(r'<@&(\d+)>',roles)
    objs=[interaction.guild.get_role(int(i)) for i in ids if interaction.guild.get_role(int(i))]
    if not objs: return await interaction.response.send_message(embed=er("Erreur","Utilise des mentions de rôles."),ephemeral=True)
    e=mke(f"{T.ROLE}  {titre}","\n".join([f"{T.ARROW} {r.mention}" for r in objs]),T.PINK)
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.send(embed=e,view=RoleMenuView(objs))
    await interaction.followup.send(embed=ok("Menu créé !"),ephemeral=True)

# ── Systèmes ──
@bot.tree.command(name="panel",description="Créer un panel de tickets")
@app_commands.describe(titre="Titre",description="Description",role_support="Rôle support")
@app_commands.default_permissions(administrator=True)
async def panel(interaction:discord.Interaction,titre:str="Support",description:str="Clique pour ouvrir un ticket.",role_support:discord.Role=None):
    bot.ticket_configs[str(interaction.guild.id)]={"support_role":role_support.id if role_support else None}
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.send(embed=mke(f"{T.TICKET}  {titre}",description,T.BLURPLE),view=TicketView())
    await interaction.followup.send(embed=ok("Panel créé !"),ephemeral=True)

@bot.tree.command(name="reglement",description="Envoyer le règlement")
@app_commands.describe(type_reglement="defaut = règles du bot | perso = tu écris",avec_bouton="Ajouter bouton",role="Rôle à l'acceptation")
@app_commands.choices(type_reglement=[
    app_commands.Choice(name="Défaut (règles du bot)",value="defaut"),
    app_commands.Choice(name="Personnalisé (j'écris moi-même)",value="perso")])
@app_commands.default_permissions(administrator=True)
async def reglement(interaction:discord.Interaction,type_reglement:str="defaut",avec_bouton:bool=True,role:discord.Role=None):
    if type_reglement=="perso":
        await interaction.response.send_modal(ReglementModal(avec_bouton,role))
    else:
        if role: bot.verif_roles[str(interaction.guild.id)]=role.id
        rules=[(f"{T.DIAMOND}  Respect","Respecte tous les membres et le staff."),
               (f"{T.LIGHTNING}  Anti-spam","Évite de répéter les mêmes messages."),
               (f"{T.STAR}  Publicité","Toute pub non autorisée est interdite."),
               (f"{T.CRYSTAL}  Contenu","Aucun contenu NSFW, violent ou illégal."),
               (f"{T.CROWN}  Staff","Les décisions du staff sont finales.")]
        e=discord.Embed(title=f"{T.SHIELD}  Règlement du serveur",description=T.LINE,color=T.BLURPLE,timestamp=datetime.now(timezone.utc))
        for t,c in rules: e.add_field(name=t,value=c,inline=False)
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.send(embed=e,view=RulesView() if avec_bouton else None)
        await interaction.followup.send(embed=ok("Règlement envoyé !"),ephemeral=True)

@bot.tree.command(name="verification",description="Panel de vérification")
@app_commands.describe(role="Rôle à donner",titre="Titre",description="Description")
@app_commands.default_permissions(administrator=True)
async def verification(interaction:discord.Interaction,role:discord.Role=None,titre:str="Vérification",description:str="Clique pour te vérifier !"):
    gid=str(interaction.guild.id)
    if not role:
        role=(discord.utils.get(interaction.guild.roles,name="✅ Vérifié") or
              await interaction.guild.create_role(name="✅ Vérifié",color=discord.Color.green()))
    bot.verif_roles[gid]=role.id
    e=mke(f"{T.SHIELD}  {titre}",f"{description}\n\n**Rôle :** {role.mention}",T.BLURPLE)
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.send(embed=e,view=VerifyView())
    await interaction.followup.send(embed=ok("Panel créé !"),ephemeral=True)

@bot.tree.command(name="arrivee",description="Configurer le salon des messages de bienvenue")
@app_commands.describe(salon="Le salon où envoyer les messages de bienvenue")
@app_commands.default_permissions(administrator=True)
async def arrivee(interaction:discord.Interaction,salon:discord.TextChannel):
    bot.arrivee_channels[str(interaction.guild.id)]=salon.id
    await interaction.response.send_message(embed=ok("Arrivées configurées",f"Salon : {salon.mention}"))

@bot.tree.command(name="depart",description="Configurer le salon des messages de départ")
@app_commands.describe(salon="Le salon où envoyer les messages de départ")
@app_commands.default_permissions(administrator=True)
async def depart(interaction:discord.Interaction,salon:discord.TextChannel):
    bot.depart_channels[str(interaction.guild.id)]=salon.id
    await interaction.response.send_message(embed=ok("Départs configurés",f"Salon : {salon.mention}"))

@bot.tree.command(name="giveaway",description="Créer un giveaway")
@app_commands.describe(titre="Titre",prix="Prix",duree_heures="Durée en heures",gagnants="Gagnants")
@app_commands.default_permissions(administrator=True)
async def giveaway_cmd(interaction:discord.Interaction,titre:str,prix:str,duree_heures:int,gagnants:int=1):
    await interaction.response.defer()
    end_time=datetime.now(timezone.utc)+timedelta(hours=duree_heures)
    e=discord.Embed(title=f"{T.GIVEAWAY}  {titre.upper()}",description=f"{T.GIFT} **Prix :** {prix}\n{T.LINE}",color=T.GOLD,timestamp=datetime.now(timezone.utc))
    e.add_field(name=f"{T.TROPHY} Gagnants",value=f"**{gagnants}**",inline=True)
    e.add_field(name=f"{T.STAR} Participants",value=f"**0**",inline=True)
    e.add_field(name=f"{T.CLOCK} Fin",value=f"<t:{int(end_time.timestamp())}:R>",inline=True)
    e.set_footer(text=f"Organisé par {interaction.user.display_name}")
    msg=await interaction.channel.send(embed=e); mid=str(msg.id)
    bot.giveaways[mid]={"title":titre,"prize":prix,"winners":gagnants,"end_time":end_time.isoformat(),
                        "channel_id":str(interaction.channel.id),"guild_id":str(interaction.guild.id),
                        "participants":[],"ended":False}
    view=GiveawayView(mid); bot.add_view(view); await msg.edit(view=view)
    await interaction.followup.send(embed=ok("Giveaway créé !",f"**{titre}** — {prix} — {duree_heures}h — {gagnants} gagnant(s)"),ephemeral=True)

@bot.tree.command(name="reroll",description="Relancer un giveaway terminé")
@app_commands.describe(message_id="ID du message du giveaway")
@app_commands.default_permissions(administrator=True)
async def reroll(interaction:discord.Interaction,message_id:str):
    g=bot.giveaways.get(message_id)
    if not g: return await interaction.response.send_message(embed=er("Introuvable"),ephemeral=True)
    if not g.get("ended"): return await interaction.response.send_message(embed=er("En cours"),ephemeral=True)
    p=g.get("participants",[])
    if not p: return await interaction.response.send_message(embed=er("Aucun participant"),ephemeral=True)
    winners=[]
    for wid in random.sample(p,min(g.get("winners",1),len(p))):
        try: winners.append(await bot.fetch_user(wid))
        except Exception: pass
    if winners:
        await interaction.response.send_message(content=" ".join([w.mention for w in winners]),
            embed=mke(f"{T.GIVEAWAY}  Reroll !",f"**Gagnant(s) :** {', '.join([w.mention for w in winners])}\n**Prix :** {g.get('prize')}",T.GOLD))
    else: await interaction.response.send_message(embed=er("Erreur reroll"),ephemeral=True)

@bot.tree.command(name="poll",description="Créer un sondage interactif")
@app_commands.describe(question="La question",option1="Option 1",option2="Option 2",
                        option3="Option 3",option4="Option 4",option5="Option 5",
                        duree_minutes="Durée en minutes (0 = sans limite)")
@app_commands.default_permissions(manage_messages=True)
async def poll_cmd(interaction:discord.Interaction,question:str,option1:str,option2:str,
                   option3:str=None,option4:str=None,option5:str=None,duree_minutes:int=0):
    options=[o for o in [option1,option2,option3,option4,option5] if o]
    end_time=None
    if duree_minutes>0: end_time=datetime.now(timezone.utc)+timedelta(minutes=duree_minutes)
    desc=f"**{question}**\n\n"
    for i,opt in enumerate(options):
        desc+=f"{PEMOJIS[i]} **{opt}**\n`░░░░░░░░░░` 0 vote (0%)\n\n"
    desc+=f"{T.CHART} **0 vote au total**"
    if end_time: desc+=f"\n\n{T.CLOCK} Fin : <t:{int(end_time.timestamp())}:R>"
    e=mke(f"{T.POLL}  Sondage",desc,T.BLURPLE)
    e.set_footer(text=f"Sondage par {interaction.user.display_name}"+(f" • {duree_minutes} min" if duree_minutes>0 else ""))
    await interaction.response.send_message(embed=e)
    msg=await interaction.original_response(); msg_id=str(msg.id)
    poll_data={"question":question,"options":options,"votes":{},"ended":False,
               "guild_id":str(interaction.guild.id),"channel_id":str(interaction.channel.id)}
    if end_time: poll_data["end_time"]=end_time.isoformat()
    bot.polls[msg_id]=poll_data
    await msg.edit(view=PollView(msg_id,options))

# ── Infos ──
@bot.tree.command(name="userinfo",description="Informations sur un membre")
@app_commands.describe(membre="Le membre (vide = toi)")
async def userinfo(interaction:discord.Interaction,membre:discord.Member=None):
    m=membre or interaction.user; gid=str(interaction.guild.id); d=get_xp(gid,str(m.id))
    roles=[r.mention for r in m.roles if r.name!="@everyone"]
    e=discord.Embed(title=f"{T.INFO}  {m.display_name}",color=m.color or T.BLURPLE,timestamp=datetime.now(timezone.utc))
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="Discord",value=str(m),inline=True)
    e.add_field(name="ID",value=f"`{m.id}`",inline=True)
    e.add_field(name="Bot",value=T.CHECK if m.bot else T.CROSS,inline=True)
    e.add_field(name="Créé le",value=m.created_at.strftime("%d/%m/%Y"),inline=True)
    e.add_field(name="Rejoint le",value=m.joined_at.strftime("%d/%m/%Y") if m.joined_at else "?",inline=True)
    e.add_field(name=f"{T.XP} Niveau",value=f"**{d['level']}** ({d['xp']} XP)",inline=True)
    e.add_field(name=f"{T.ROLE} Rôles ({len(roles)})",value=" ".join(roles[:10]) or "Aucun",inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="serverinfo",description="Informations sur le serveur")
async def serverinfo(interaction:discord.Interaction):
    g=interaction.guild
    total=g.member_count or len(g.members) or 0
    bots=sum(1 for m in g.members if m.bot)
    humans=total-bots if total>=bots else total
    e=discord.Embed(title=f"{T.INFO}  {g.name}",color=T.BLURPLE,timestamp=datetime.now(timezone.utc))
    if g.icon: e.set_thumbnail(url=g.icon.url)
    e.add_field(name="ID",value=f"`{g.id}`",inline=True)
    e.add_field(name="Propriétaire",value=g.owner.mention if g.owner else "?",inline=True)
    e.add_field(name="Créé le",value=g.created_at.strftime("%d/%m/%Y"),inline=True)
    e.add_field(name="Membres",value=f"**{humans}** humains / **{bots}** bots",inline=True)
    e.add_field(name="Salons",value=f"**{len(g.text_channels)}** texte / **{len(g.voice_channels)}** vocal",inline=True)
    e.add_field(name="Rôles",value=f"**{len(g.roles)}**",inline=True)
    e.add_field(name="Boosts",value=f"**{g.premium_subscription_count}** (Niv. {g.premium_tier})",inline=True)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="rank",description="Voir son niveau XP")
@app_commands.describe(membre="Le membre (vide = toi)")
async def rank(interaction:discord.Interaction,membre:discord.Member=None):
    m=membre or interaction.user; gid=str(interaction.guild.id); d=get_xp(gid,str(m.id))
    lvl,xp_c=d["level"],d["xp"]; req=xp_for_level(lvl+1)
    pct=int(xp_c/req*100) if req>0 else 0; bar="█"*(pct//10)+"░"*(10-pct//10)
    su=sorted(bot.xp_data.get(gid,{}).items(),key=lambda x:(x[1]["level"],x[1]["xp"]),reverse=True)
    rp=next((i+1 for i,(uid,_) in enumerate(su) if uid==str(m.id)),"?")
    e=discord.Embed(title=f"{T.XP}  Rang de {m.display_name}",color=T.GOLD,timestamp=datetime.now(timezone.utc))
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="Niveau",value=f"**{lvl}**",inline=True)
    e.add_field(name="XP",value=f"**{xp_c}** / {req}",inline=True)
    e.add_field(name="Classement",value=f"**#{rp}**",inline=True)
    e.add_field(name="Messages",value=f"**{d['messages']}**",inline=True)
    e.add_field(name="Progression",value=f"`{bar}` {pct}%",inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="top",description="Top 10 XP du serveur")
async def top(interaction:discord.Interaction):
    gid=str(interaction.guild.id); gxp=bot.xp_data.get(gid,{})
    if not gxp: return await interaction.response.send_message(embed=inf("Classement vide","Personne n'a encore de XP."),ephemeral=True)
    su=sorted(gxp.items(),key=lambda x:(x[1]["level"],x[1]["xp"]),reverse=True)[:10]
    medals=["🥇","🥈","🥉"]+[f"**#{i}**" for i in range(4,11)]; desc=""
    for i,(uid,d) in enumerate(su):
        member=interaction.guild.get_member(int(uid))
        name=member.display_name if member else f"ID:{uid}"
        desc+=f"{medals[i]} **{name}** — Niveau {d['level']} ({d['xp']} XP)\n"
    await interaction.response.send_message(embed=mke(f"{T.TROPHY}  Top 10 XP",desc,T.GOLD))

# ── Administration ──
@bot.tree.command(name="setup",description="Setup complet selon un style de serveur")
@app_commands.describe(style="Style du serveur")
@app_commands.choices(style=[
    app_commands.Choice(name="🌐 Communauté / Discussion",value="communaute"),
    app_commands.Choice(name="🎮 Gaming",value="gaming"),
    app_commands.Choice(name="🎭 Jeu de Rôle (RP)",value="rp"),
    app_commands.Choice(name="📚 Éducation / Études",value="education"),
    app_commands.Choice(name="🎌 Anime / Manga",value="anime")])
@app_commands.default_permissions(administrator=True)
async def setup(interaction:discord.Interaction,style:str="communaute"):
    await interaction.response.defer()
    g=interaction.guild; cfg=SETUPS[style]; created={"roles":0,"text":0,"voice":0}
    for name,color in cfg["roles"]:
        if not discord.utils.get(g.roles,name=name):
            try: await g.create_role(name=name,color=discord.Color(color)); created["roles"]+=1; await asyncio.sleep(0.4)
            except discord.Forbidden: pass  # Bot n'a pas manage_roles
            except Exception: pass
    for cat_name,(texts,voices) in cfg["structure"].items():
        cat=discord.utils.get(g.categories,name=cat_name)
        if not cat:
            try:
                ow={g.default_role:discord.PermissionOverwrite(view_channel=False)} if "STAFF" in cat_name or "MJ" in cat_name else {}
                cat=await g.create_category(cat_name,overwrites=ow); await asyncio.sleep(0.3)
            except Exception: continue
        for ch_name in texts:
            if not discord.utils.get(g.text_channels,name=ch_name):
                try: await g.create_text_channel(ch_name,category=cat); created["text"]+=1; await asyncio.sleep(0.3)
                except Exception: pass
        for vc_name in voices:
            if not discord.utils.get(g.voice_channels,name=vc_name):
                try: await g.create_voice_channel(vc_name,category=cat); created["voice"]+=1; await asyncio.sleep(0.3)
                except Exception: pass
    for ln in ["📊・logs","logs"]:
        lc=discord.utils.get(g.text_channels,name=ln)
        if lc: bot.logs_channels[str(g.id)]=lc.id; break
    e=ok(f"Setup terminé ! — {cfg['label']}")
    e.add_field(name="Rôles",value=f"**{created['roles']}**",inline=True)
    e.add_field(name="Salons texte",value=f"**{created['text']}**",inline=True)
    e.add_field(name="Salons vocal",value=f"**{created['voice']}**",inline=True)
    e.add_field(name="Étapes suivantes",value="`/arrivee` `/depart` `/panel` `/verification` `/reglement` `/antispam`",inline=False)
    await interaction.followup.send(embed=e)

@bot.tree.command(name="backup",description="Sauvegarder la structure du serveur")
@app_commands.describe(nom="Nom de la sauvegarde")
@app_commands.default_permissions(administrator=True)
async def backup(interaction:discord.Interaction,nom:str=None):
    await interaction.response.defer(ephemeral=True)
    g=interaction.guild; name=nom or f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    data={"roles":[{"name":r.name,"color":r.color.value} for r in g.roles if r.name!="@everyone" and not r.managed],
          "categories":[{"name":c.name} for c in g.categories],
          "text":[{"name":c.name,"category":c.category.name if c.category else None} for c in g.text_channels],
          "voice":[{"name":c.name,"category":c.category.name if c.category else None} for c in g.voice_channels]}
    bot.backups.setdefault(str(g.id),{})[name]=data
    await interaction.followup.send(embed=ok("Sauvegarde créée",f"**{name}**\nRôles : {len(data['roles'])} | Salons : {len(data['text'])+len(data['voice'])}"),ephemeral=True)

@bot.tree.command(name="restore",description="Restaurer une sauvegarde")
@app_commands.describe(nom="Nom de la sauvegarde")
@app_commands.default_permissions(administrator=True)
async def restore(interaction:discord.Interaction,nom:str):
    await interaction.response.defer()
    gid=str(interaction.guild.id); data=bot.backups.get(gid,{}).get(nom)
    if not data: return await interaction.followup.send(embed=er("Introuvable",f"**{nom}** n'existe pas."))
    restored={"roles":0,"channels":0}
    for r in data.get("roles",[]):
        if not discord.utils.get(interaction.guild.roles,name=r["name"]):
            try: await interaction.guild.create_role(name=r["name"],color=discord.Color(r.get("color",0))); restored["roles"]+=1; await asyncio.sleep(0.3)
            except Exception: pass
    for c in data.get("categories",[]):
        if not discord.utils.get(interaction.guild.categories,name=c["name"]):
            try: await interaction.guild.create_category(c["name"]); await asyncio.sleep(0.3)
            except Exception: pass
    for ch in data.get("text",[]):
        if not discord.utils.get(interaction.guild.text_channels,name=ch["name"]):
            try:
                cat=discord.utils.get(interaction.guild.categories,name=ch.get("category"))
                await interaction.guild.create_text_channel(ch["name"],category=cat); restored["channels"]+=1; await asyncio.sleep(0.3)
            except Exception: pass
    await interaction.followup.send(embed=ok("Restauré !",f"Rôles : **{restored['roles']}** | Salons : **{restored['channels']}**"))

@bot.tree.command(name="antiraid",description="Configurer l'anti-raid")
@app_commands.describe(activer="Activer",seuil="Joins par 10 secondes",action="kick ou ban")
@app_commands.default_permissions(administrator=True)
async def antiraid(interaction:discord.Interaction,activer:bool=True,seuil:int=5,action:str="kick"):
    bot.raid_protection[str(interaction.guild.id)]={"enabled":activer,"threshold":seuil,"action":action}
    await interaction.response.send_message(embed=mke(f"{T.SHIELD}  Anti-Raid",
        f"**Statut :** {'✅' if activer else '❌'}\n**Seuil :** {seuil}/10s\n**Action :** {action}",T.BLURPLE))

@bot.tree.command(name="antispam",description="Configurer l'anti-spam")
@app_commands.describe(activer="Activer",messages="Max messages",temps="En secondes",mentions="Max mentions",action="mute/kick/ban",duree_mute="Minutes")
@app_commands.default_permissions(administrator=True)
async def antispam(interaction:discord.Interaction,activer:bool=True,messages:int=5,temps:int=5,mentions:int=5,action:str="mute",duree_mute:int=5):
    bot.antispam_config[str(interaction.guild.id)]={"enabled":activer,"msg_limit":messages,"msg_time":temps,"mention_limit":mentions,"action":action,"mute_duration":duree_mute}
    await interaction.response.send_message(embed=mke(f"{T.SPAM}  Anti-Spam",
        f"**Statut :** {'✅' if activer else '❌'}\n**Messages :** {messages}/{temps}s\n**Mentions :** {mentions}\n**Action :** {action}",T.BLURPLE))

@bot.tree.command(name="antinuke",description="Configurer la protection anti-nuke")
@app_commands.describe(activer="Activer l'anti-nuke",seuil="Actions max en 10s avant sanction",
                        action="kick ou ban",
                        ajouter_whitelist="ID d'un membre à ajouter en whitelist",
                        retirer_whitelist="ID d'un membre à retirer de la whitelist")
@app_commands.default_permissions(administrator=True)
async def antinuke(interaction:discord.Interaction,activer:bool=True,seuil:int=5,action:str="kick",
                   ajouter_whitelist:str=None,retirer_whitelist:str=None):
    gid=str(interaction.guild.id)
    cfg=bot.antinuke_config.setdefault(gid,{"enabled":False,"threshold":5,"action":"kick","whitelist":[]})
    cfg["enabled"]=activer
    cfg["threshold"]=max(1,seuil)
    cfg["action"]=action if action in ("kick","ban") else "kick"
    wl=cfg.setdefault("whitelist",[])
    if ajouter_whitelist:
        try:
            uid=int(ajouter_whitelist)
            if uid not in wl: wl.append(uid)
        except ValueError: pass
    if retirer_whitelist:
        try:
            uid=int(retirer_whitelist)
            if uid in wl: wl.remove(uid)
        except ValueError: pass
    wl_display=[interaction.guild.get_member(uid).mention if interaction.guild.get_member(uid) else f"`{uid}`" for uid in wl]
    e=mke(f"{T.NUKE}  Anti-Nuke",
          f"**Statut :** {'✅ Activé' if activer else '❌ Désactivé'}\n"
          f"**Seuil :** {seuil} actions / 10s\n"
          f"**Sanction :** {cfg['action']}\n"
          f"**Whitelist :** {', '.join(wl_display) if wl_display else 'Aucun'}\n\n"
          f"**Actions surveillées :**\n"
          f"• Bans en masse\n• Suppression de salons\n• Suppression de rôles",
          T.RED)
    e.set_footer(text="⚠️ Ajoute tes admins de confiance en whitelist !")
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="tempvoice",description="Salons vocaux temporaires")
@app_commands.describe(salon="Salon déclencheur")
@app_commands.default_permissions(administrator=True)
async def tempvoice(interaction:discord.Interaction,salon:discord.VoiceChannel):
    bot.temp_voices[str(interaction.guild.id)]=salon.id
    await interaction.response.send_message(embed=ok("Vocaux temporaires",f"Rejoins **{salon.name}** pour créer ton salon !"))

# ── DM All ──
@bot.tree.command(name="dmall",description="Envoyer un DM à tous les membres du serveur")
@app_commands.describe(message="Le message à envoyer en DM")
@app_commands.default_permissions(administrator=True)
async def dmall(interaction:discord.Interaction,message:str):
    await interaction.response.defer(ephemeral=True)
    guild=interaction.guild
    members=[m for m in guild.members if not m.bot]
    total=len(members)
    await interaction.followup.send(embed=inf("📨  DM en cours...",f"Envoi à **{total}** membres..."),ephemeral=True)
    e_dm=discord.Embed(title=f"📨  Message de {guild.name}",description=message,color=T.BLURPLE,timestamp=datetime.now(timezone.utc))
    e_dm.set_footer(text=f"Envoyé depuis {guild.name}")
    if guild.icon: e_dm.set_thumbnail(url=guild.icon.url)
    sent=failed=0
    for member in members:
        try: await member.send(embed=e_dm); sent+=1
        except Exception: failed+=1
        await asyncio.sleep(1.2)
    await interaction.edit_original_response(embed=ok("DM envoyés !",f"**Envoyés :** {sent}\n**Échoués :** {failed}\n**Total :** {total}"))


# ==================== RUN ====================
if __name__=="__main__":
    from dotenv import load_dotenv
    load_dotenv()
    token=os.environ.get('DISCORD_BOT_TOKEN')
    if token:
        logger.info("⚡ Aegis V1.10 démarre...")
        bot.run(token)
    else:
        logger.error("❌ DISCORD_BOT_TOKEN manquant !")
