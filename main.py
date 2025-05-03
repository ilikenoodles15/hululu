import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

ALLOWED_ROLE_IDS = [1365490217641054232, 1368138573794115674]
LOG_CHANNEL_ID = 1368319592669249746
DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

@tasks.loop(minutes=1)
async def check_expired_roles():
    data = load_data()
    updated = False
    now = datetime.utcnow().timestamp()
    for guild_id in list(data.keys()):
        for user_id in list(data[guild_id].keys()):
            role_info = data[guild_id][user_id]
            if role_info["expires_at"] != "permanent" and now >= role_info["expires_at"]:
                guild = bot.get_guild(int(guild_id))
                member = guild.get_member(int(user_id))
                role = guild.get_role(role_info["role_id"])
                if member and role:
                    await member.remove_roles(role)
                    log_channel = guild.get_channel(LOG_CHANNEL_ID)
                    await log_channel.send(
                        f"⏰ Role **{role.name}** was automatically removed from {member.mention} (time expired)."
                    )
                del data[guild_id][user_id]
                updated = True
        if not data[guild_id]:
            del data[guild_id]
    if updated:
        save_data(data)

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    check_expired_roles.start()

@bot.slash_command(name="temprole", description="Give a user a role temporarily or permanently.")
async def temprole(
    ctx: discord.ApplicationContext,
    member: discord.Member,
    role: discord.Role,
    duration: str
):
    if not any(role.id in ALLOWED_ROLE_IDS for role in ctx.author.roles):
        await ctx.respond("🚫 You do not have permission to use this command.", ephemeral=True)
        return

    await member.add_roles(role)
    
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    await log_channel.send(f"✅ {ctx.author.mention} gave {role.name} to {member.mention}. Duration: `{duration}`")

    if duration.lower() == "permanent":
        expires_at = "permanent"
    else:
        try:
            amount = int(duration[:-1])
            unit = duration[-1].lower()
            if unit == "s":
                delta = timedelta(seconds=amount)
            elif unit == "m":
                delta = timedelta(minutes=amount)
            elif unit == "h":
                delta = timedelta(hours=amount)
            elif unit == "d":
                delta = timedelta(days=amount)
            else:
                await ctx.respond("❌ Invalid time format. Use `30s`, `10m`, `5h`, `7d`, or `permanent`.", ephemeral=True)
                return
            expires_at = (datetime.utcnow() + delta).timestamp()
        except Exception:
            await ctx.respond("❌ Invalid time format. Use `30s`, `10m`, `5h`, `7d`, or `permanent`.", ephemeral=True)
            return

    data = load_data()
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    if guild_id not in data:
        data[guild_id] = {}
    data[guild_id][user_id] = {
        "role_id": role.id,
        "expires_at": expires_at
    }
    save_data(data)

    await ctx.respond(f"✅ Role **{role.name}** has been given to {member.mention} for `{duration}`.")
