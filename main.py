import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from yaml import Loader, load

with open("config.yml") as f:
    config = load(f.read(), Loader=Loader)

discord_token = config["bot"]["discord_token"]

guild_id = config["bot"]["guild"]

bot_id = config["bot"]["bot_id"]

log_chat_id = config["bot"]["chat_id"]
welcome_chat_id = config["bot"]["welcome_chat_id"]
muted_channel_id = config["bot"]["muted_channel_id"]

member_role_id = config["bot"]["member_role_id"]
muted_role_id = config["bot"]["muted_role_id"]

welcome_msg = config["bot"]["welcome_msg"]
boot_msg = config["bot"]["boot_msg"]

intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True
intents.messages = True
intents.members = True

client = discord.Client(intents=intents)
bot = commands.Bot(intents=intents, command_prefix="!")

# Track user messages
user_message_tracker = defaultdict(lambda: deque(maxlen=3))
TIME_WINDOW_SECONDS = 10  # Adjust as needed
MUTE_DURATION_MINUTES = 5  # How long to mute the user


@client.event
async def on_ready():
    channel = client.get_channel(log_chat_id)
    await channel.send(eval(boot_msg))


@client.event
async def on_member_remove(member):
    channel = client.get_channel(log_chat_id)

    t = time.localtime()
    current_time = time.strftime("%H:%M:%S", t)
    await channel.send(f"{current_time} <-- Member leave  {member}")


@client.event
async def on_member_update(before, after):

    guild = client.get_guild(guild_id)
    channel = client.get_channel(log_chat_id)
    welcome_room = client.get_channel(welcome_chat_id)

    if before.pending == True and after.pending == False:
        t = time.localtime()
        current_time = time.strftime("%H:%M:%S", t)

        member_role = discord.utils.get(guild.roles, id=member_role_id)

        if role is not None:
            # await channel.send(f"\t<@{role_id}>")
            await after.add_roles(member_role)

        await channel.send(f"{current_time} --> New Member {after.id}")
        # await welcome_room.send(eval(welcome_msg))


@client.event
async def on_message(message):
    # Skip bot messages

    user_id = message.author.id

    if user_id == bot_id:
        return

    channel_id = message.channel.id
    current_time = datetime.now()

    # print(f"{current_time} USER ID: {user_id} ")
    # Add current message to tracker
    user_message_tracker[user_id].append((channel_id, current_time))

    # Get user's recent messages
    recent_messages = user_message_tracker[user_id]

    # Check if we have 3 messages
    if len(recent_messages) == 3:
        # Extract channels and timestamps
        channels = [msg[0] for msg in recent_messages]
        timestamps = [msg[1] for msg in recent_messages]

        # Check if all channels are different
        unique_channels = len(set(channels)) == 3

        # Check if all messages are within the time window
        oldest_time = timestamps[0]
        newest_time = timestamps[2]
        time_diff = (newest_time - oldest_time).total_seconds()
        within_time_window = time_diff <= TIME_WINDOW_SECONDS

        if unique_channels and within_time_window:
            # Mute the user and handle the violation
            await mute_user(message.author, message.guild, time_diff)

            # Optional: Clear tracker to avoid duplicate triggers
            user_message_tracker[user_id].clear()


async def mute_user(user, guild, time_diff):
    """Mute the user using Discord's timeout feature"""
    try:
        # Calculate mute duration
        mute_duration = timedelta(minutes=MUTE_DURATION_MINUTES)

        # Apply timeout to user
        # await user.timeout(mute_duration, reason=f"Spammed 3 messages in different channels within {time_diff:.1f} seconds")

        # Send alert to log channel
        log_channel = client.get_channel(log_chat_id)
        if log_channel:
            await log_channel.send(
                f"🔇 **User Muted**: {user.mention} has been muted.\n"
                f"**Reason**: Sent messages in 3 different channels within {time_diff:.1f} seconds."
            )

        muted_role = discord.utils.get(guild.roles, id=muted_role_id)

        if muted_role is not None:
            await user.add_roles(muted_role)

        member_role = discord.utils.get(guild.roles, id=member_role_id)

        if member_role is not None:
            await user.remove_roles(member_role)

        muted_channel = client.get_channel(muted_channel_id)
        await muted_channel.send(
            f"You have been muted for {MUTE_DURATION_MINUTES} minutes for spamming messages across multiple channels."
        )

        print(f"Muted {user.name}")

    except discord.Forbidden:
        print(f"Missing permissions to mute {user.name}")
        # Log the error
        log_channel = client.get_channel(log_chat_id)
        if log_channel:
            await log_channel.send(
                f"❌ Failed to mute {user.mention} - Missing permissions!"
            )

    except Exception as e:
        print(f"Error muting user: {e}")


client.run(discord_token)
