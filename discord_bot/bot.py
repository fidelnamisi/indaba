"""
Indaba Bot — Discord interface for the Indaba publishing dashboard.

Runs on EC2. Calls Indaba Flask API at http://localhost:5050.
Listens in #indaba-ops channel. Responds to !commands and natural language.
"""
import asyncio
import json
import textwrap

import discord
from discord.ext import commands

import config
import indaba_client as api
import claude_agent
import roadmap

# ── Discord setup ─────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Per-channel conversation history so the agent remembers context across turns.
# channel_id → list of message dicts (role/content), capped at 30 items.
_channel_history: dict[int, list] = {}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _in_ops_channel(ctx_or_message) -> bool:
    """Return True if the message is in the configured ops channel."""
    channel = getattr(ctx_or_message, "channel", ctx_or_message)
    return channel.name == config.INDABA_CHANNEL_NAME


def _trunc(text: str, limit: int = 1900) -> str:
    """Truncate to Discord's message limit with a marker."""
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n… *(truncated)*"


def _fmt_pipeline(entries: list) -> str:
    """Format a list of pipeline entries as a compact table."""
    if not entries:
        return "No entries found."
    lines = []
    for e in entries:
        stage = e.get("workflow_stage", "?")
        book = e.get("book", "?")
        title = e.get("chapter", "?")
        eid = e.get("id", "?")
        lines.append(f"[{book}] {title} — *{stage}* `{eid}`")
    return "\n".join(lines)


def _fmt_hub(data: dict) -> str:
    """Format hub summary as readable text."""
    lines = ["**Indaba Hub Summary**"]

    pipeline = data.get("pipeline", {})
    if pipeline:
        lines.append("\n**Pipeline stages:**")
        for stage, count in pipeline.items():
            icon = {"producing": "✍️", "publishing": "📤", "promoting": "📣"}.get(stage, "•")
            lines.append(f"  {icon} {stage}: {count}")

    promote = data.get("promote", {})
    if promote:
        lines.append("\n**Promo:**")
        lines.append(f"  contacts: {promote.get('contacts_count', 0)}")
        lines.append(f"  messages queued: {promote.get('messages_queued', 0)}")
        lines.append(f"  open leads: {promote.get('open_leads', 0)}")

    recent = data.get("recent_activity", [])
    if recent:
        lines.append("\n**Recent activity:**")
        for item in recent[:5]:
            lines.append(f"  • {item}")

    pending = data.get("pending_tasks", [])
    if pending:
        lines.append("\n**Pending tasks:**")
        for item in pending[:5]:
            lines.append(f"  ⚠ {item}")

    return "\n".join(lines)


async def _reply(ctx, text: str):
    """Send a truncated reply."""
    await ctx.send(_trunc(text))


# ── Bot events ────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"[Indaba Bot] Connected as {bot.user} | Listening in #{config.INDABA_CHANNEL_NAME}")
    # Announce in the ops channel if found
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == config.INDABA_CHANNEL_NAME:
                try:
                    await channel.send("**Indaba Bot online.** Type `!help` for commands.")
                except Exception:
                    pass
                break


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if not _in_ops_channel(message):
        return

    # Process !commands first
    await bot.process_commands(message)

    # Natural language: any message not starting with !
    if not message.content.startswith("!"):
        await _handle_natural_language(message)


# ── Natural language dispatch — full agentic loop ─────────────────────────────

async def _handle_natural_language(message: discord.Message):
    """
    Route any non-! message through the Claude agent.
    Maintains per-channel history so the agent remembers context across turns.
    """
    channel_id = message.channel.id
    history = _channel_history.get(channel_id, [])

    status_msg = await message.channel.send("*Working…*")
    steps = []

    def on_progress(step_text: str):
        steps.append(step_text)

    try:
        result, updated_history = await asyncio.to_thread(
            claude_agent.run_agent, message.content, history, on_progress
        )
        _channel_history[channel_id] = updated_history

        reply_parts = []
        if steps:
            reply_parts.append("**Steps taken:**\n" + "\n".join(steps))
            reply_parts.append("")
        reply_parts.append(result)
        final = "\n".join(reply_parts)

        await status_msg.edit(content=_trunc(final))

    except Exception as e:
        await status_msg.edit(content=f"Agent error: {e}")


# ── Action implementations ────────────────────────────────────────────────────

async def _do_hub(reply):
    try:
        data = await asyncio.to_thread(api.hub_summary)
        await reply(_fmt_hub(data))
    except Exception as e:
        await reply(f"Hub summary failed: {e}")


async def _do_pipeline(reply, book="", stage=""):
    try:
        entries = await asyncio.to_thread(api.pipeline_list, book, stage)
        header = "**Pipeline"
        if book:
            header += f" — {book.upper()}"
        if stage:
            header += f" ({stage})"
        header += f"** ({len(entries)} entries)\n"
        await reply(header + _fmt_pipeline(entries))
    except Exception as e:
        await reply(f"Pipeline list failed: {e}")


async def _do_pipeline_get(reply, entry_id: str):
    if not entry_id:
        await reply("Provide an entry ID. E.g. `!entry love-back-ch2-pipeline`")
        return
    try:
        data = await asyncio.to_thread(api.pipeline_get, entry_id)
        text = f"**{data.get('chapter', '?')}** (`{entry_id}`)\n"
        text += f"Book: {data.get('book')} | Stage: {data.get('workflow_stage')}\n"
        assets = data.get("assets", {})
        if assets:
            text += "Assets: " + ", ".join(f"{k}={'✓' if v else '✗'}" for k, v in assets.items() if v) + "\n"
        await reply(text)
    except Exception as e:
        await reply(f"Entry lookup failed: {e}")


async def _do_set_stage(reply, entry_id: str, stage: str):
    if not entry_id or not stage:
        await reply("Need both entry ID and stage. E.g. `!stage love-back-ch2-pipeline publishing`")
        return
    try:
        data = await asyncio.to_thread(api.pipeline_set_stage, entry_id, stage)
        await reply(f"Moved `{entry_id}` → **{stage}**")
    except Exception as e:
        await reply(f"Stage update failed: {e}")


async def _do_publish(reply, entry_id: str):
    if not entry_id:
        await reply("Provide an entry ID. E.g. `!publish love-back-ch2-pipeline`")
        return
    await reply(f"Publishing `{entry_id}` to website…")
    try:
        data = await asyncio.to_thread(api.website_publish, entry_id)
        url = data.get("chapter_url", "")
        await reply(f"Published! {url}" if url else f"Done: {data}")
    except Exception as e:
        await reply(f"Publish failed: {e}")


async def _do_deploy(reply):
    await reply("Deploying website to Amplify… (takes ~2 min)")
    try:
        data = await asyncio.to_thread(api.website_deploy)
        await reply(f"Deploy started: {data}")
    except Exception as e:
        await reply(f"Deploy failed: {e}")


async def _do_deploy_status(reply):
    try:
        data = await asyncio.to_thread(api.website_deploy_status)
        state = data.get("state", "?")
        await reply(f"Deploy status: **{state}**" + (f" — {data.get('error')}" if data.get("error") else ""))
    except Exception as e:
        await reply(f"Status check failed: {e}")


async def _do_work_sync(reply, work_id: str):
    if not work_id:
        await reply("Provide a work code. E.g. `!sync LB`")
        return
    try:
        data = await asyncio.to_thread(api.website_work_sync, work_id)
        chapters = data.get("chapters", [])
        lines = [f"**{data.get('series', work_id)} sync** ({len(chapters)} chapters)"]
        for ch in chapters[:15]:
            status = ch.get("status", "?")
            icon = "🟢" if status == "live" else "🔴" if status == "missing" else "🟡"
            lines.append(f"  {icon} Ch {ch.get('chapter_number', '?')} — {ch.get('title', '?')} ({status})")
        await reply("\n".join(lines))
    except Exception as e:
        await reply(f"Sync check failed: {e}")


async def _do_works(reply):
    try:
        data = await asyncio.to_thread(api.works_list)
        works = data.get("works", data) if isinstance(data, dict) else data
        lines = ["**Works**"]
        for w in works:
            lines.append(f"  [{w.get('code', '?')}] {w.get('title', '?')} — {w.get('genre', '')}")
        await reply("\n".join(lines))
    except Exception as e:
        await reply(f"Works list failed: {e}")


async def _do_status(reply):
    try:
        data = await asyncio.to_thread(api.ec2_sender_health)
        queued = data.get("queued", "?")
        device = data.get("gowa_device", "unknown")
        ok = data.get("ok", False)
        icon = "🟢" if ok else "🔴"
        await reply(f"{icon} EC2 Sender — queued: {queued} | device: {device}")
    except Exception as e:
        await reply(f"EC2 status check failed: {e}")


async def _do_idea(reply, text: str):
    if not text:
        await reply("What's the idea? `!idea <your idea here>`")
        return
    try:
        status = await asyncio.to_thread(roadmap.add_idea, text)
        await reply(f"Got it — {status}")
    except Exception as e:
        await reply(f"Idea capture failed: {e}")


async def _do_help(reply):
    help_text = textwrap.dedent("""
        **Indaba Bot — Natural language is the primary interface.**

        Just talk to me: "Generate the next proverb", "Publish chapter 3 of Love Back",
        "What's in the pipeline?", "Move OAO ch5 to publishing"

        For **write operations** (generate, queue, publish, deploy) I'll show a preview
        and ask you to say **yes** before doing anything.
        For **read operations** (hub, pipeline, status) I respond immediately.

        **Quick shortcuts:**
        `!hub`                     Pipeline overview
        `!pipeline [book] [stage]`  List entries (filter optional)
        `!works`                   List all book series
        `!status`                  EC2 sender health
        `!idea <text>`             Capture idea → ROADMAP.md → GitHub
        `!help`                    This message

        *Book codes: LB, OAO, ROTRQ, MOSAS*
        *Stages: producing, publishing, promoting*
    """).strip()
    await reply(help_text)


# ── !commands (explicit prefix versions) ─────────────────────────────────────

@bot.command(name="hub")
async def cmd_hub(ctx):
    if not _in_ops_channel(ctx): return
    await _do_hub(lambda t: _reply(ctx, t))


@bot.command(name="pipeline")
async def cmd_pipeline(ctx, book: str = "", stage: str = ""):
    if not _in_ops_channel(ctx): return
    await _do_pipeline(lambda t: _reply(ctx, t), book, stage)


@bot.command(name="entry")
async def cmd_entry(ctx, entry_id: str = ""):
    if not _in_ops_channel(ctx): return
    await _do_pipeline_get(lambda t: _reply(ctx, t), entry_id)


@bot.command(name="stage")
async def cmd_stage(ctx, entry_id: str = "", stage: str = ""):
    if not _in_ops_channel(ctx): return
    await _do_set_stage(lambda t: _reply(ctx, t), entry_id, stage)


@bot.command(name="publish")
async def cmd_publish(ctx, entry_id: str = ""):
    if not _in_ops_channel(ctx): return
    await _do_publish(lambda t: _reply(ctx, t), entry_id)


@bot.command(name="deploy")
async def cmd_deploy(ctx):
    if not _in_ops_channel(ctx): return
    await _do_deploy(lambda t: _reply(ctx, t))


@bot.command(name="deploystatus")
async def cmd_deploy_status(ctx):
    if not _in_ops_channel(ctx): return
    await _do_deploy_status(lambda t: _reply(ctx, t))


@bot.command(name="sync")
async def cmd_sync(ctx, work_id: str = ""):
    if not _in_ops_channel(ctx): return
    await _do_work_sync(lambda t: _reply(ctx, t), work_id)


@bot.command(name="works")
async def cmd_works(ctx):
    if not _in_ops_channel(ctx): return
    await _do_works(lambda t: _reply(ctx, t))


@bot.command(name="status")
async def cmd_status(ctx):
    if not _in_ops_channel(ctx): return
    await _do_status(lambda t: _reply(ctx, t))


@bot.command(name="idea")
async def cmd_idea(ctx, *, text: str = ""):
    if not _in_ops_channel(ctx): return
    await _do_idea(lambda t: _reply(ctx, t), text)


@bot.command(name="help")
async def cmd_help(ctx):
    if not _in_ops_channel(ctx): return
    await _do_help(lambda t: _reply(ctx, t))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        print("[Indaba Bot] ERROR: DISCORD_BOT_TOKEN not set. Bot cannot start.")
        raise SystemExit(1)
    bot.run(config.DISCORD_TOKEN)
