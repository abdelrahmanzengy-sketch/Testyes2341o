"""
StaffMode Discord log bot — maintained by Tuna.

Works with StaffMode 1.9.9 (Paper / Folia).

Slash commands:
  /setuplog [channel]  - pick the log channel and create (or reuse) the
                         "StaffMode Logs" webhook used by the Minecraft plugin.
  /testlog             - post a sample live-action embed through the saved webhook
                         (proves the URL works without needing a staff session).
  /logstatus           - show which channel / webhook this bot has configured.

Put the webhook URL into plugins/Staff/config.yml:

  discord:
    enabled: true
    live-actions: true
    webhook-url: 'THE_URL'

The plugin posts directly to the webhook:
  • live embed for every staff action (TP, freeze, vanish, invsee, ban, …)
  • full session summary when staff turns OFF staff mode

Logs keep working while this bot is offline once the URL is in config.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
EXAMPLE_PATH = BASE / "config.example.json"
WEBHOOK_NAME = "StaffMode Logs"
DEFAULT_CONFIG = {"token": "", "log_channel_id": None, "webhook_url": None, "author": "Tuna"}

log = logging.getLogger("staffbot")


# ----------------------------------------------------------------- config ----
def load_config() -> dict:
    """Read config.json, creating it from the example file on first run."""
    for path in (CONFIG_PATH, EXAMPLE_PATH):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                break
            except (OSError, json.JSONDecodeError) as exc:
                raise SystemExit(f"Cannot read {path.name}: {exc}") from exc
    else:
        data = dict(DEFAULT_CONFIG)
    for key, value in DEFAULT_CONFIG.items():
        data.setdefault(key, value)
    if not CONFIG_PATH.exists():
        save_config(data)
    return data


def save_config(data: dict) -> None:
    """Atomic write so a crash can never leave a half-written config.json."""
    fd, tmp = tempfile.mkstemp(dir=BASE, prefix="config.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# -------------------------------------------------------------------- embeds ----
def example_session_embed() -> discord.Embed:
    embed = discord.Embed(title="📋 Staff Log — ExampleStaff", color=0x3498DB)
    embed.add_field(name="Staff", value="ExampleStaff (`uuid`)", inline=True)
    embed.add_field(
        name="Session",
        value="Started: 2026-10-24 20:00:00\nEnded: 2026-10-24 20:12:45",
        inline=True,
    )
    embed.add_field(
        name="Summary",
        value=(
            "**Duration:** 12m 45s\n"
            "**TP:** 3  **Freeze:** 1  **Vanish:** 2\n"
            "**Invsee:** 1  **Ban:** 0"
        ),
        inline=False,
    )
    embed.add_field(
        name="Actions",
        value=(
            "`20:01:02` **STAFF ON** — joined staff mode\n"
            "`20:02:10` **TP** — Teleported to Steve\n"
            "`20:05:44` **FREEZE** — Froze Griefer123\n"
            "`20:11:01` **VANISH** — Vanish ON\n"
            "`20:12:45` **STAFF OFF** — session ended"
        ),
        inline=False,
    )
    embed.set_footer(text="StaffMode · session report · Author: Tuna")
    return embed


def example_live_embed() -> discord.Embed:
    embed = discord.Embed(
        title="TP",
        description="Staff: **ExampleStaff**\nTeleported to Steve",
        color=0xE67E22,
    )
    embed.set_footer(text="StaffMode · live action · Author: Tuna")
    return embed


# ---------------------------------------------------------------------- bot ----
def build_bot(config: dict) -> commands.Bot:
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)
    bot.config = config

    @bot.event
    async def on_ready() -> None:
        try:
            synced = await bot.tree.sync()
            log.info("Logged in as %s — synced %d command(s)", bot.user, len(synced))
        except Exception:
            log.exception("Command tree sync failed")
        channel_id = bot.config.get("log_channel_id")
        if channel_id:
            log.info("Log channel id: %s", channel_id)

    @bot.tree.command(name="setuplog", description="Set the StaffMode log channel and create the webhook.")
    @app_commands.describe(channel="Channel where staff live actions + session reports appear")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(manage_webhooks=True, send_messages=True, embed_links=True)
    async def setuplog(
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.followup.send("Pick a text channel.", ephemeral=True)
            return

        me = target.guild.me if target.guild else None
        me_id = me.id if me else bot.user.id
        webhooks = await target.webhooks()
        webhook = next(
            (w for w in webhooks if w.name == WEBHOOK_NAME and w.user and w.user.id == me_id),
            None,
        )
        if webhook is None:
            webhook = await target.create_webhook(name=WEBHOOK_NAME, reason="StaffMode /setuplog")

        bot.config["log_channel_id"] = target.id
        bot.config["webhook_url"] = webhook.url
        save_config(bot.config)

        await target.send(
            content=(
                "✅ **StaffMode log channel ready.**\n"
                "• **Live actions** (TP, freeze, vanish, ban, …) post as they happen\n"
                "• **Session summary** posts when a staff member runs `/staff off`"
            ),
            embeds=[example_live_embed(), example_session_embed()],
        )
        await interaction.followup.send(
            f"Log channel set to {target.mention}.\n\n"
            "Paste this into `plugins/Staff/config.yml`:\n"
            "```yaml\n"
            "discord:\n"
            "  enabled: true\n"
            "  live-actions: true\n"
            f"  webhook-url: '{webhook.url}'\n"
            "```\n"
            "Then `/staff reload` (or restart the server).\n"
            "**Do not share the webhook URL** — it is shown only to you:",
            ephemeral=True,
        )
        await interaction.followup.send(f"||{webhook.url}||", ephemeral=True)

    @setuplog.error
    async def setuplog_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original
        if isinstance(error, app_commands.MissingPermissions):
            message = "You need **Manage Server** to use /setuplog."
        elif isinstance(error, app_commands.BotMissingPermissions):
            message = "I need **Manage Webhooks**, **Send Messages** and **Embed Links** in that channel."
        elif isinstance(error, discord.Forbidden):
            message = "Discord refused: give me **Manage Webhooks** in that channel."
        else:
            log.exception("setuplog failed", exc_info=error)
            message = "Something went wrong. Check the bot console."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @bot.tree.command(name="testlog", description="Post a sample StaffMode live-action embed via the saved webhook.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def testlog(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        url = bot.config.get("webhook_url")
        if not url:
            await interaction.followup.send(
                "No webhook saved yet. Run `/setuplog` first.", ephemeral=True
            )
            return
        try:
            webhook = discord.Webhook.from_url(url, client=bot)
            await webhook.send(
                username=WEBHOOK_NAME,
                embed=example_live_embed(),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await webhook.send(
                username=WEBHOOK_NAME,
                embed=example_session_embed(),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await interaction.followup.send(
                "Posted sample **live action** + **session report** embeds. "
                "If you see them in the log channel, the webhook is good.",
                ephemeral=True,
            )
        except Exception as exc:
            log.exception("testlog failed")
            await interaction.followup.send(f"Webhook test failed: `{exc}`", ephemeral=True)

    @bot.tree.command(name="logstatus", description="Show StaffMode log channel / webhook status.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def logstatus(interaction: discord.Interaction) -> None:
        channel_id = bot.config.get("log_channel_id")
        url = bot.config.get("webhook_url")
        channel_txt = f"<#{channel_id}>" if channel_id else "_not set_"
        url_txt = "saved (hidden)" if url else "_not set — run /setuplog_"
        embed = discord.Embed(title="StaffMode log status", color=0x2ECC71)
        embed.add_field(name="Channel", value=channel_txt, inline=True)
        embed.add_field(name="Webhook", value=url_txt, inline=True)
        embed.add_field(
            name="Plugin config",
            value=(
                "```yaml\n"
                "discord:\n"
                "  enabled: true\n"
                "  live-actions: true\n"
                "  webhook-url: '<from /setuplog>'\n"
                "```"
            ),
            inline=False,
        )
        embed.set_footer(text="StaffMode · Author: Tuna")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    return bot


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()
    token = os.environ.get("DISCORD_TOKEN") or config.get("token") or ""
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            f"Set your bot token in {CONFIG_PATH.name} or the DISCORD_TOKEN environment variable."
        )
    build_bot(config).run(token, log_handler=None)


if __name__ == "__main__":
    main()
