> Maintainer / author: Tuna

# StaffMode Discord Log Bot (2.2)

Companion bot for **StaffMode 1.9.9**.

## What gets logged

The **Minecraft plugin** posts to a Discord webhook (not through the bot process):

| When | What |
|------|------|
| Staff turns **ON** | Live embed: who, world, coords |
| **Every action** while in staff mode | Live embed: TP, freeze, unfreeze, vanish, spectator, invsee, endersee, scan, ban, notes, … |
| Punish commands / GUI | Audit embeds (ban, mute, kick, ALL actions, …) |
| Staff turns **OFF** | Full **session report** embed (duration + every action) |

`discord.live-actions: true` (default) enables the live stream. Session reports always post when logging is enabled.

## Bot commands

| Command | Purpose |
|---------|---------|
| `/setuplog [#channel]` | Create/reuse **StaffMode Logs** webhook + print YAML for the plugin |
| `/testlog` | Post sample live + session embeds through the webhook |
| `/logstatus` | Show configured channel / webhook |

## Setup

1. Create a Discord bot at https://discord.com/developers/applications  
   - Enable bot, copy token  
   - Invite with scopes `bot` + `applications.commands`  
   - Permissions: **Manage Webhooks**, **Send Messages**, **Embed Links**  
   - No privileged intents needed

2. Install & run:

```bash
pip install -r requirements.txt
# put token in config.json  (or export DISCORD_TOKEN=...)
python bot.py
```

3. In Discord: `/setuplog #your-staff-log-channel`

4. Paste the YAML it shows into `plugins/Staff/config.yml`, then `/staff reload`.

5. Optional: `/testlog` to verify the channel without joining Minecraft.

## Note

Once the webhook URL is in the plugin config, **logs work even if this bot is offline**. The bot is for setup, testing, and status.

## Compatibility

- StaffMode **1.9.9** (PacketEvents is shaded inside the plugin jar — no separate PE plugin required)
- discord.py 2.4+
