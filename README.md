# OpenShockBot

OpenShockBot is a safety-focused, self-hostable Discord bot for controlling
[OpenShock](https://openshock.org/) shockers. It is an independent community project and is
not affiliated with or endorsed by OpenShock.

> [!WARNING]
> OpenShock controls physical hardware. Use this software only with informed, ongoing consent.
> Configure conservative limits, keep a physical emergency stop accessible, and follow the
> [OpenShock safety rules](https://wiki.openshock.org/home/safety-rules).

## Current features

- `/openshock shock`, `vibrate`, `sound`, and safety-oriented `stop` commands
- Reaction controls on messages from linked targets: ⚡ shock, 🌊 vibrate, 🔊 sound
- Per-target pause state
- Personal block and allow rules
- Open-to-everyone and allow-list access modes
- Per-actor/per-target cooldowns
- Bot-wide and per-target intensity/duration ceilings
- Self-service safety limits, defaults, reaction toggle, and cooldown configuration
- SQLite audit log of sent, denied, and failed controls
- Private recent-activity history
- Async OpenShock API access
- Secrets loaded from environment variables, never from tracked configuration

This is an alpha. Persistent button panels, context menus, presets, and reaction aggregation are
planned next; see the [roadmap](docs/ROADMAP.md).

## Requirements

- Python 3.11 or newer
- A Discord application and bot token
- An OpenShock API token
- An OpenShock shocker UUID

## Set up Discord

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and create an
   application named **OpenShockBot**.
2. Open **Bot**, create the bot if needed, and copy its token into `DISCORD_BOT_TOKEN` in `.env`.
   Never paste that token into chat, an issue, or a commit.
3. Enable Developer Mode in Discord under **User Settings → Advanced**. Right-click your user and
   choose **Copy User ID**; put it in `BOT_OWNER_IDS`.
4. Under **OAuth2 → URL Generator**, select the `bot` and `applications.commands` scopes.
5. Give the bot `View Channels`, `Send Messages`, `Read Message History`, and `Add Reactions`.
6. Open the generated URL and add the bot to your server.

OpenShockBot does not need Discord's privileged Message Content intent.

## Set up OpenShock

1. In the OpenShock web app, create an API token under **Settings → API Tokens**.
2. Copy it into `OPENSHOCK_TOKEN` in `.env`.
3. Copy the UUID of the shocker you want to control.
4. Either set `DEFAULT_TARGET_DISCORD_ID` and `DEFAULT_SHOCKER_ID` in `.env`, or run the private
   `/openshock link` command after the bot starts.

Do not commit the API token. OpenShock requires applications to send a meaningful `User-Agent`;
the default is set in `.env.example`.

## Run locally

```bash
git clone https://github.com/YOUR-USERNAME/OpenShockBot.git
cd OpenShockBot
cp .env.example .env
# Edit .env with your private values.

python -m venv .venv
source .venv/bin/activate
pip install -e .
openshockbot
```

Slash commands registered globally can take a little while to appear after the bot's first start.

## Access model

Each linked Discord user owns their target configuration:

- `everyone`: anyone may control the target except personally blocked users.
- `allowlist`: only explicitly allowed users may control the target.
- The target may pause itself at any time.
- A `stop` request is always accepted by the bot for a linked target, including while paused.
- Effective intensity and duration are the lowest applicable bot-wide and target-specific limits.

Reaction controls use the target's stored default intensity and duration. A reaction only triggers
when it is newly added; Discord does not generate another add event while the same reaction remains.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Security issues involving
tokens, authorization bypasses, or unsafe control behavior should follow [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE). Contributions are welcome.
