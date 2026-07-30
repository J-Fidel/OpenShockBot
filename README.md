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
- Independently configurable reaction controls on messages from linked targets:
  ⚡ shock, 🌊 vibrate, 🔊 sound
- Per-target pause state
- Personal block and allow rules
- Open-to-everyone and allow-list access modes
- Per-actor/per-target cooldowns
- Bot-wide and per-target intensity/duration ceilings
- Self-service safety limits, per-reaction toggles/defaults, and cooldown configuration
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

## Run continuously on a Linux server

The repository includes a hardened user-level systemd unit for the checkout location used by this
server.

```bash
mkdir -p ~/.config/systemd/user
ln -s ~/Documents/OpenShockBot/deploy/openshockbot.service \
  ~/.config/systemd/user/openshockbot.service
systemctl --user daemon-reload
systemctl --user enable --now openshockbot
systemctl --user status openshockbot
```

Follow live logs with:

```bash
journalctl --user -u openshockbot -f
```

If the bot must continue after the account logs out, an administrator can enable lingering once:

```bash
sudo loginctl enable-linger "$USER"
```

After changing `.env`, restart with `systemctl --user restart openshockbot`.

## First applied test

1. Keep the OpenShock physical emergency stop accessible and leave the shocker unworn.
2. Start the bot and wait for its log to say that it logged into Discord.
3. In Discord, run `/openshock status` and confirm your personal ceilings, cooldown, and access
   mode.
4. Run `/openshock sound` against your linked Discord user. Confirm the intended shocker beeps.
5. Run `/openshock vibrate` at the lowest practical intensity and minimum duration while the
   shocker is still unworn.
6. Test `/openshock pause`, a blocked user, cooldown behavior, and `/openshock stop` before any
   worn use.

Do not begin with a shock command. Any later worn test should use explicit consent and the lowest
personal limits that can verify operation.

## Access model

Each linked Discord user owns their target configuration:

- `everyone`: anyone may control the target except personally blocked users.
- `allowlist`: only explicitly allowed users may control the target.
- The target may pause itself at any time.
- A `stop` request is always accepted by the bot for a linked target, including while paused.
- Effective intensity and duration are the lowest applicable bot-wide and target-specific limits.

Reaction controls use the target's stored per-action intensity and duration. A reaction only
triggers when it is newly added; Discord does not generate another add event while the same
reaction remains.

Each reaction type has an independent toggle, intensity, and duration. Configure one with:

```text
/openshock reaction-config action:Shock enabled:False intensity:1 duration:0.3
```

New and migrated targets have shock reactions disabled at 1% for 0.3 seconds until the target
explicitly enables them. Sound and vibrate inherit the previous reaction defaults during migration.
The shared cooldown, access rules, pause state, and personal and bot-wide safety ceilings apply to
every reaction type.

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
