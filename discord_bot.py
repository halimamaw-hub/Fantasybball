"""
Discord front-end for the fantasy basketball draft assistant.

This does NOT reimplement any draft logic -- it loads the exact same
DraftTracker that the terminal version builds (via build_tracker()) and
feeds each Discord message straight into dispatch_command(), the same
command dispatcher the `python fantasybball_draftloop.py` terminal loop
uses. Whatever that prints is captured and sent back as a Discord message.

Required environment variables (set these in Render's dashboard, never in
code):
  DISCORD_KEY       -- your bot's token, from the Discord Developer Portal
  DRAFT_CHANNEL_ID   -- (optional but recommended) the numeric ID of the one
                        channel the bot should treat as the draft room. If
                        unset, the bot reacts to every message in every
                        channel it can see, which is usually not what you
                        want for a shared server.
"""
import os
import io
import asyncio
import contextlib

import discord

from web_server import keep_alive
from fantasybball_draftloop import build_tracker, dispatch_command, _LOOP_HELP

DRAFT_CHANNEL_ID = (
    int(os.environ["DRAFT_CHANNEL_ID"]) if os.environ.get("DRAFT_CHANNEL_ID") else None
)

intents = discord.Intents.default()
intents.message_content = True  # must ALSO be enabled in the Dev Portal
bot = discord.Client(intents=intents)

# Loaded once in on_ready(), then reused for the lifetime of the process.
state = {}


def _chunk_text(text, limit=1900):
    """Discord messages cap at 2000 chars; split long command output
    (catrank/h2hstand tables etc.) into safe chunks on line boundaries."""
    lines = text.split("\n")
    chunks, current = [], ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [""]


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id={bot.user.id})")
    # CSV loading + the ensemble/consensus math is CPU-bound; run it off
    # the event loop so it can't stall Discord's heartbeat.
    tracker, weekly = await asyncio.to_thread(build_tracker)
    state["tracker"] = tracker
    state["weekly"] = weekly
    print("Draft tracker ready.")
    if DRAFT_CHANNEL_ID:
        channel = bot.get_channel(DRAFT_CHANNEL_ID)
        if channel:
            await channel.send("Draft assistant is online.\n```\n" + _LOOP_HELP.strip() + "\n```")


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if "tracker" not in state:
        return  # still loading CSVs
    if DRAFT_CHANNEL_ID and message.channel.id != DRAFT_CHANNEL_ID:
        return

    raw = message.content.strip()
    if not raw:
        return

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            dispatch_command(state["tracker"], state["weekly"], raw)
    except Exception as e:  # keep the bot alive even if a command errors
        await message.channel.send(f"Error running that command: `{e}`")
        return

    output = buf.getvalue().strip()
    if not output:
        return
    for chunk in _chunk_text(output):
        await message.channel.send(f"```\n{chunk}\n```")


if __name__ == "__main__":
    keep_alive()
    token = os.environ.get("DISCORD_KEY")
    if not token:
        raise SystemExit(
            "DISCORD_KEY environment variable is not set. Add it in Render's "
            "Environment Variables section (see the setup guide)."
        )
    bot.run(token)
