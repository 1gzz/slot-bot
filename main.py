import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json
import pytz
import asyncio
import re
import os
import platform

class SlotBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.synced = False

    async def setup_hook(self):
        if not self.synced:
            await self.tree.sync()
            self.synced = True

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.messages = True

bot = SlotBot(command_prefix='$', intents=intents)

statuses = ["hello", "hi"]

@tasks.loop(seconds=30)
async def change_status():
    new_status = statuses.pop(0)
    statuses.append(new_status)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=new_status))

def clear_screen():
    if platform.system() == "Windows":
        os.system('cls')
    else:
        os.system('clear')

clear_screen()

@bot.event
async def on_ready():
    print(f'Successfully logged in as a bot !')
    reset_mentions.start()
    change_status.start()
    check_expired_slots.start()

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

category_id = config['category_id']
bot_token = config['token']

TIMEZONE = pytz.timezone('Europe/Tirane')

now = datetime.now(TIMEZONE)

if now.hour == 0 and now.minute == 0:
    reset_time = now
else:
    reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

print("Next reset time:", reset_time)

mention_count = {}

def load_slot_owners():
    try:
        with open('database.json', 'r') as file:
            data = json.load(file)
            slot_owners = [slot['user_id'] for slot in data.get('slots', [])]
            return slot_owners
    except Exception as e:
        print(f"Error loading slot owners: {e}")
        return []

@tasks.loop(seconds=60)
async def reset_mentions():
    global mention_count, reset_time

    now = datetime.now(TIMEZONE)
    
    if now > reset_time:
        mention_count = {}
        reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        slot_owners = load_slot_owners()
        for user_id in slot_owners:
            try:
                user = await bot.fetch_user(user_id)
                if user:
                    await user.send(f"Pings have been reset! You can now use 2 pings again on your slot.")
                    print("All slot owners have been notified about ping reset")
            except Exception as e:
                print(f"Could not send DM to {user_id}: {e}")

@tasks.loop(seconds=1800)
async def check_expired_slots():
    now = datetime.now(TIMEZONE)
    try:
        with open('database.json', 'r') as f:
            data = json.load(f)
    except Exception as e:
        return
    expired_slots = []
    for slot in data.get('slots', []):
        try:
            expiration_time = datetime.fromisoformat(slot['expiry_date']).astimezone(TIMEZONE)
        except Exception:
            continue
        if now > expiration_time:
            expired_slots.append(slot)
            user_id = slot['user_id']
            try:
                user = await bot.fetch_user(user_id)
                if user:
                    await user.send(f"Your slot has expired.")
            except Exception:
                pass
            channel_id = slot['channel_id']
            channel = bot.get_channel(channel_id)
            if channel:
                owner = await bot.fetch_user(user_id)
                await channel.set_permissions(owner, send_messages=False)
                embed1 = discord.Embed(
                    title="Slot Expired",
                    description=f"- This slot will be deleted within the next few hours!",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed1)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if isinstance(message.channel, discord.DMChannel):
        return
    if message.channel.category_id == category_id:
        if "@everyone" in message.content and not message.author.guild_permissions.administrator:
            channel = message.channel
            user = message.author
            await channel.set_permissions(user,
                                          send_messages=False,
                                          read_message_history=False,
                                          mention_everyone=False)
            embed1 = discord.Embed(
                title="Slot Revoked",
                description=f"- {channel.mention} has been revoked.\n- Reason: Everyone Ping",
                color=discord.Color.red()
            )
            await channel.send(embed=embed1)
            return
        if "@everyone" in message.content and message.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="Permission Denied",
                description="Failed to revoke slot because slot owner is an Administrator",
                color=discord.Color.gold()
            )
            await message.channel.send(embed=embed)
            return
    if "@here" in message.content and message.channel.category_id == category_id:
        mention_count["overall"] = mention_count.get("overall", 0) + 1
        mention_count[message.author.id] = mention_count.get(message.author.id, 0) + 1
        embed = discord.Embed(
            description=f'**{message.author.mention}, YOU USED** __**{mention_count[message.author.id]}/2**__ **PINGS**. | __**USE MM TO BE SAFE!**__',
            color=0x2f3136)
        na = await message.channel.send(embed=embed)
        if mention_count.get(message.author.id, 0) > 2:
            await message.channel.set_permissions(message.author, send_messages=False)
            embed = discord.Embed(
                description=f"**{message.author.mention}, your slot has been revoked because you exceeded the allowed limit of `@here` pings today.**",
                color=0xff0000)
            await na.delete()
            await message.channel.send(embed=embed)
    await bot.process_commands(message)

database_file = 'database.json'

def load_database():
    try:
        with open("database.json", "r") as f:
            db = json.load(f)
    except FileNotFoundError:
        db = {}
    except json.JSONDecodeError:
        db = {}
    if "slots" not in db:
        db["slots"] = []
    return db

def save_database(db):
    with open("database.json", "w") as f:
        json.dump(db, f, indent=4)

def user_has_slot(user_id):
    db = load_database()
    for slot in db["slots"]:
        if slot["user_id"] == str(user_id):
            return True, slot
    return False, None

def add_slot(slot_id, user_id, slot_name, duration_days):
    db = load_database()
    purchase_date = datetime.now(TIMEZONE)
    expiry_date = purchase_date + timedelta(days=duration_days)
    purchase_date_str = purchase_date.strftime("%Y-%m-%d %H:%M:%S")
    expiry_date_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
    db["slots"].append({
        "slotId": slot_id,
        "user_id": str(user_id),
        "slot_name": slot_name,
        "status": "held",
        "purchase_date": purchase_date_str,
        "expiry_date": expiry_date_str,
        "duration_days": duration_days
    })
    save_database(db)

@bot.tree.command(name="slot", description="Create a slot channel for a user.")
@discord.app_commands.describe(user="The user to assign the slot to", duration="Duration (e.g. 1w, 2d)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def slot_command(interaction: discord.Interaction, user: discord.Member, duration: str = '1w'):
    await interaction.response.send_message(f"Creating slot for {user.mention}...", ephemeral=True)
    category = discord.utils.get(interaction.guild.categories, id=category_id)
    if category is None:
        await interaction.followup.send("Category not found. Please check the category ID in the config.", ephemeral=True)
        return
    channel_name = f"{user.name}-slot"
    channel = await category.create_text_channel(channel_name)
    await channel.set_permissions(interaction.guild.default_role,
                                  view_channel=True,
                                  send_messages=False)
    await channel.set_permissions(user,
                                  view_channel=True,
                                  send_messages=True,
                                  mention_everyone=True)
    duration_days = 0
    duration_text_parts = []
    matches = re.findall(r'(\d+)([dwmy])', duration)
    if not matches:
        await interaction.followup.send("Invalid duration format. Please use something like '1d', '1w', or '1m'.", ephemeral=True)
        return
    duration_map = {
        'd': 1,
        'w': 7,
        'm': 30,
    }
    for value, unit in matches:
        days = int(value) * duration_map[unit]
        duration_days += days
        duration_text_parts.append(f"{value} {unit}")
    duration_text = ', '.join(duration_text_parts) if duration_text_parts else "0 days"
    purchase_date = datetime.now(TIMEZONE)
    expiry_date = purchase_date + timedelta(days=duration_days)
    db = load_database()
    purchase_date_str = purchase_date.strftime("%Y-%m-%d %H:%M:%S")
    expiry_date_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
    db["slots"].append({
        "user_id": user.id,
        "channel_id": channel.id,
        "slot_name": channel_name,
        "purchase_date": purchase_date_str,
        "expiry_date": expiry_date_str,
        "duration_days": duration_days
    })
    save_database(db)
    embed = discord.Embed(
        title="Slot Channel Created",
        description=f"{channel.mention} for {user.mention} has been created.",
        color=discord.Color.green()
    )
    await channel.send(embed=embed)
    try:
        await user.send(f"Your new slot {channel.mention} has been successfully created for {duration}.")
    except Exception:
        pass
    embed2 = discord.Embed(
        title="SLOT RULES",
        description="""**➥ You can ping @here 2 times per day on your slot. Based on CEST timezone.\n➥ No refunds. \n➥ No everyone Ping or role ping.\n➥ No advertising allowed, only your autobuy link.\n➥ Refuse MM = revoke without refund\n➥ Scam = Slot revoke without refund\n➥ If you disobey any of these rules, your slot will be revoked without refund.**\n""",
        color=0x2f3136)
    await channel.send(embed=embed2)
    purchase_timestamp = int(purchase_date.timestamp())
    expiry_timestamp = int(expiry_date.timestamp())
    embed3 = discord.Embed(
        title="Slot Details",
        description=(f"**Purchase Date:** <t:{purchase_timestamp}>\n"
                     f"**Duration:** **{duration_days} days | {duration_text}**\n"
                     f"**Expiry Date:** <t:{expiry_timestamp}>") ,
        color=discord.Color.green()
    )
    embed3.add_field(name="Permissions",
                    value="```2x @here pings```",
                    inline=False)
    embed3.add_field(name="Rule 1",
                    value="Must follow the slot rules strictly.",
                    inline=False)
    embed3.add_field(name="Rule 2",
                    value="Must always accept MM.",
                    inline=False)
    await channel.send(embed=embed3)
    await interaction.followup.send(f"Slot channel {channel.mention} created for {user.mention}.", ephemeral=True)

@bot.tree.command(name="revokeslot", description="Revoke a slot channel.")
@discord.app_commands.describe(channel="The slot channel to revoke", reason="Reason for revoking the slot")
@discord.app_commands.checks.has_permissions(administrator=True)
async def revokeslot_command(interaction: discord.Interaction, channel: discord.TextChannel, reason: str = None):
    await interaction.response.defer(thinking=True)
    database = load_database()
    slots = database.get("slots", [])
    slot = next((s for s in slots if s['channel_id'] == channel.id), None)
    if slot is None:
        await interaction.followup.send(f"No slot found for {channel.mention}.")
        return
    owner_id = slot['user_id']
    owner = interaction.guild.get_member(owner_id)
    if owner:
        await channel.set_permissions(owner, send_messages=False)
        reason = reason or "Violation of Slot Rules"
        embed_success = discord.Embed(
            title="Slot Revoked",
            description=f"- {channel.mention} has been revoked.\n- Reason: {reason}",
            color=discord.Color.red()
        )
        await channel.send(embed=embed_success)
        await interaction.followup.send(f"Slot revoked and message sent in {channel.mention}.")
    else:
        await interaction.followup.send("The slot owner is no longer a member of the server.")

@bot.tree.command(name="hold", description="Hold a slot channel (prevent user from sending messages)")
@discord.app_commands.describe(channel="The slot channel to hold")
@discord.app_commands.checks.has_permissions(administrator=True)
async def hold_command(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(thinking=True)
    db = load_database()
    slot = next((s for s in db["slots"] if s["channel_id"] == channel.id), None)
    if slot is None:
        await interaction.followup.send(f"No slot found for channel {channel.mention}.")
        return
    user = interaction.guild.get_member(slot["user_id"])
    if user is None:
        await interaction.followup.send(f"Could not find the user for slot {channel.mention}.")
        return
    await channel.set_permissions(user, send_messages=False)
    embed = discord.Embed(
        title="Slot On Hold",
        description=f"- {channel.mention} is now on hold.\n- Do NOT deal with this slot owner until the slot is unheld!",
        color=discord.Color.orange()
    )
    await channel.send(embed=embed)
    await interaction.followup.send(f"Slot put on hold and message sent in {channel.mention}.")

@bot.tree.command(name="unhold", description="Unhold a slot channel (allow user to send messages again)")
@discord.app_commands.describe(channel="The slot channel to unhold")
@discord.app_commands.checks.has_permissions(administrator=True)
async def unhold_command(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(thinking=True)
    db = load_database()
    slot = next((s for s in db["slots"] if s["channel_id"] == channel.id), None)
    if slot is None:
        await interaction.followup.send(f"No slot found for channel {channel.mention}.")
        return
    user = interaction.guild.get_member(slot["user_id"])
    if user is None:
        await interaction.followup.send(f"Could not find the user for slot {channel.mention}.")
        return
    await channel.set_permissions(user, send_messages=True)
    embed = discord.Embed(
        title="Slot Unheld",
        description=f"- {channel.mention} is now unheld.\n- You can now start deals with this channel again!\n- Always use a middleman to be safe.",
        color=discord.Color.green()
    )
    await channel.send(embed=embed)
    await interaction.followup.send(f"Slot unheld and message sent in {channel.mention}.")

@bot.tree.command(name="help", description="Show help for slot bot commands.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Help - Slot Bot Commands",
        description="Here are the available commands you can use:",
        color=discord.Color.blue()
    )
    embed.add_field(name="/slot [user] [duration]", 
                    value="Creates a slot channel for the specified user with a specified duration. Duration can be in weeks (w), months (m), or days.",
                    inline=False)
    embed.add_field(name="/deleteslot [channel]", 
                    value="Deletes the specified slot channel after confirmation.",
                    inline=False)
    embed.add_field(name="/revokeslot [channel]", 
                    value="Revokes the specified slot channel.",
                    inline=False)
    embed.add_field(name="/hold [channel]", 
                    value="Holds the specified slot, preventing further communication until unheld.",
                    inline=False)
    embed.add_field(name="/unhold [channel]", 
                    value="Unholds the specified slot, allowing communication again.",
                    inline=False)
    embed.add_field(name="/srules", 
                    value="Sends the slot rules in the current channel.",
                    inline=False)
    embed.add_field(name="/help", 
                    value="Displays this help message.",
                    inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="srules", description="Send the slot rules in a channel.")
@discord.app_commands.describe(channel="The channel to send the rules in (optional)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def srules_command(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if channel is None:
        channel = interaction.channel
    embed = discord.Embed(title='SLOT RULES',
                            description="""**➥ You can ping @here 2 times per day on your slot. Based on CEST timezone.\n➥ No refunds. \n➥ No everyone Ping or role ping.\n➥ No advertising allowed, only your autobuy link.\n➥ Refuse MM = revoke without refund\n➥ Scam = Slot revoke without refund\n➥ If you disobey any of these rules, your slot will be revoked without refund.**\n""",
    color=0xBF40BF)
    await channel.send(embed=embed)
    await interaction.response.send_message("Slot rules sent!")

@bot.tree.error
def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    try:
        if interaction.response.is_done():
            coro = interaction.followup.send(f"❌ Error: {str(error)}", ephemeral=True)
        else:
            coro = interaction.response.send_message(f"❌ Error: {str(error)}", ephemeral=True)
        asyncio.create_task(coro)
    except Exception as e:
        print(f"Failed to send error message: {e}")
    print(f"App command error: {error}")

if __name__ == "__main__":
    bot.run(bot_token)