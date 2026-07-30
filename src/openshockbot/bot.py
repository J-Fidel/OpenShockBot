from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from .config import Settings
from .database import Database
from .models import (
    AccessDecision,
    AccessMode,
    ControlRequest,
    ControlSource,
    ControlType,
)
from .openshock import OpenShockClient, OpenShockError
from .policy import PolicyEngine, PolicyError
from .service import ControlService

LOGGER = logging.getLogger(__name__)


class OpenShockDiscordBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.guild_reactions = True
        intents.guild_messages = True

        owner_ids = set(settings.owner_ids) if settings.owner_ids else None
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            owner_ids=owner_ids,
        )

        self.settings = settings
        self.database = Database(settings.database_path)
        self.openshock = OpenShockClient(
            settings.openshock_token,
            base_url=settings.openshock_api_base,
            user_agent=settings.user_agent,
        )
        self.policy = PolicyEngine(
            self.database,
            global_max_intensity=settings.global_max_intensity,
            global_max_duration_ms=settings.global_max_duration_ms,
        )
        self.controls = ControlService(self.database, self.policy, self.openshock)
        self.reaction_actions = {
            settings.reaction_shock_emoji: ControlType.SHOCK,
            settings.reaction_vibrate_emoji: ControlType.VIBRATE,
            settings.reaction_sound_emoji: ControlType.SOUND,
        }

    async def setup_hook(self) -> None:
        await self.database.connect()
        if (
            self.settings.default_target_discord_id is not None
            and self.settings.default_shocker_id is not None
        ):
            await self.database.upsert_target(
                self.settings.default_target_discord_id,
                self.settings.default_shocker_id,
                max_intensity=min(25, self.settings.global_max_intensity),
                max_duration_ms=min(3000, self.settings.global_max_duration_ms),
                cooldown_seconds=self.settings.default_cooldown_seconds,
            )

        self.tree.add_command(openshock_group)
        synced = await self.tree.sync()
        LOGGER.info("Synced %s application command groups", len(synced))

    async def close(self) -> None:
        await self.openshock.close()
        await self.database.close()
        await super().close()

    async def on_ready(self) -> None:
        LOGGER.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "unknown")

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == (self.user.id if self.user else None):
            return
        action = self.reaction_actions.get(str(payload.emoji))
        if action is None or payload.guild_id is None:
            return

        try:
            channel = self.get_channel(payload.channel_id)
            if channel is None:
                channel = await self.fetch_channel(payload.channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                return
            message = await channel.fetch_message(payload.message_id)
            target = await self.database.get_target(message.author.id)
            if target is None:
                return
            reaction = target.reaction_settings.get(action)
            if reaction is None:
                LOGGER.warning("Missing %s reaction settings for target", action.value)
                return

            request = ControlRequest(
                actor_id=payload.user_id,
                target_id=message.author.id,
                action=action,
                intensity=reaction.intensity,
                duration_ms=reaction.duration_ms,
                source=ControlSource.REACTION,
                guild_id=payload.guild_id,
                message_id=payload.message_id,
            )
            await self.controls.execute(request)
        except PolicyError as exc:
            LOGGER.info("Reaction control denied: %s", exc.public_message)
        except (discord.HTTPException, OpenShockError) as exc:
            LOGGER.warning("Reaction control failed: %s", exc)
        except Exception:
            LOGGER.exception("Unexpected reaction control failure")


openshock_group = app_commands.Group(
    name="openshock",
    description="Control linked OpenShock shockers.",
)


def _bot(interaction: discord.Interaction) -> OpenShockDiscordBot:
    if not isinstance(interaction.client, OpenShockDiscordBot):
        raise RuntimeError("OpenShockBot command used with an unexpected Discord client")
    return interaction.client


async def _respond_error(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        await interaction.edit_original_response(content=message)
    else:
        await interaction.response.send_message(message, ephemeral=True)


async def _run_control(
    interaction: discord.Interaction,
    target: discord.Member,
    action: ControlType,
    intensity: int,
    duration_seconds: float,
) -> None:
    bot = _bot(interaction)
    await interaction.response.defer(thinking=True)
    request = ControlRequest(
        actor_id=interaction.user.id,
        target_id=target.id,
        action=action,
        intensity=intensity,
        duration_ms=round(duration_seconds * 1000),
        source=ControlSource.SLASH_COMMAND,
        guild_id=interaction.guild_id,
    )
    try:
        result = await bot.controls.execute(request)
    except PolicyError as exc:
        await _respond_error(interaction, exc.public_message)
        return
    except OpenShockError:
        LOGGER.exception("OpenShock rejected a slash command")
        await _respond_error(interaction, "OpenShock could not complete that control.")
        return

    verb = {
        ControlType.SHOCK: "shocked",
        ControlType.VIBRATE: "vibrated",
        ControlType.SOUND: "sent a sound to",
    }[action]
    await interaction.edit_original_response(
        content=(
            f"{interaction.user.mention} {verb} {target.mention} at "
            f"{result.intensity}% for {result.duration_ms / 1000:g}s."
        )
    )


@openshock_group.command(name="shock", description="Send a shock to a linked target.")
@app_commands.describe(
    target="The linked Discord member to control.",
    intensity="Requested intensity; the target's lower safety cap always wins.",
    duration="Requested duration in seconds.",
)
async def shock_command(
    interaction: discord.Interaction,
    target: discord.Member,
    intensity: app_commands.Range[int, 1, 100],
    duration: app_commands.Range[float, 0.3, 65.535],
) -> None:
    await _run_control(interaction, target, ControlType.SHOCK, intensity, duration)


@openshock_group.command(name="vibrate", description="Vibrate a linked target.")
async def vibrate_command(
    interaction: discord.Interaction,
    target: discord.Member,
    intensity: app_commands.Range[int, 1, 100],
    duration: app_commands.Range[float, 0.3, 65.535],
) -> None:
    await _run_control(interaction, target, ControlType.VIBRATE, intensity, duration)


@openshock_group.command(name="sound", description="Send a sound to a linked target.")
async def sound_command(
    interaction: discord.Interaction,
    target: discord.Member,
    intensity: app_commands.Range[int, 1, 100] = 100,
    duration: app_commands.Range[float, 0.3, 65.535] = 0.3,
) -> None:
    await _run_control(interaction, target, ControlType.SOUND, intensity, duration)


@openshock_group.command(name="stop", description="Immediately stop a linked shocker.")
async def stop_command(
    interaction: discord.Interaction,
    target: discord.Member,
) -> None:
    bot = _bot(interaction)
    await interaction.response.defer(thinking=True, ephemeral=True)
    request = ControlRequest(
        actor_id=interaction.user.id,
        target_id=target.id,
        action=ControlType.STOP,
        intensity=0,
        duration_ms=300,
        source=ControlSource.SLASH_COMMAND,
        guild_id=interaction.guild_id,
    )
    try:
        await bot.controls.execute(request)
    except PolicyError as exc:
        await _respond_error(interaction, exc.public_message)
        return
    except OpenShockError:
        LOGGER.exception("OpenShock rejected a stop command")
        await _respond_error(interaction, "OpenShock could not complete the stop command.")
        return
    await interaction.edit_original_response(content=f"Stop sent for {target.mention}.")


@openshock_group.command(name="pause", description="Pause or resume controls for yourself.")
async def pause_command(
    interaction: discord.Interaction,
    paused: bool,
) -> None:
    bot = _bot(interaction)
    updated = await bot.database.set_paused(interaction.user.id, paused)
    if not updated:
        await _respond_error(interaction, "You are not linked to an OpenShock shocker.")
        return
    state = "paused" if paused else "resumed"
    await interaction.response.send_message(
        f"Your OpenShock controls are now {state}.", ephemeral=True
    )


@openshock_group.command(name="block", description="Block a Discord user from controlling you.")
async def block_command(
    interaction: discord.Interaction,
    user: discord.Member,
) -> None:
    bot = _bot(interaction)
    if await bot.database.get_target(interaction.user.id) is None:
        await _respond_error(interaction, "You are not linked to an OpenShock shocker.")
        return
    await bot.database.set_access_rule(
        interaction.user.id,
        user.id,
        AccessDecision.BLOCK,
    )
    await interaction.response.send_message(
        f"{user.mention} is now blocked from controlling you.",
        ephemeral=True,
    )


@openshock_group.command(name="allow", description="Explicitly allow a Discord user.")
async def allow_command(
    interaction: discord.Interaction,
    user: discord.Member,
) -> None:
    bot = _bot(interaction)
    if await bot.database.get_target(interaction.user.id) is None:
        await _respond_error(interaction, "You are not linked to an OpenShock shocker.")
        return
    await bot.database.set_access_rule(
        interaction.user.id,
        user.id,
        AccessDecision.ALLOW,
    )
    await interaction.response.send_message(
        f"{user.mention} is now explicitly allowed to control you.",
        ephemeral=True,
    )


@openshock_group.command(name="clear-rule", description="Remove a block or allow rule.")
async def clear_rule_command(
    interaction: discord.Interaction,
    user: discord.Member,
) -> None:
    bot = _bot(interaction)
    if await bot.database.get_target(interaction.user.id) is None:
        await _respond_error(interaction, "You are not linked to an OpenShock shocker.")
        return
    await bot.database.remove_access_rule(interaction.user.id, user.id)
    await interaction.response.send_message(
        f"Your explicit access rule for {user.mention} was removed.",
        ephemeral=True,
    )


@openshock_group.command(
    name="access-mode",
    description="Choose whether everyone or only allowed users can control you.",
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="Everyone except blocked users", value="everyone"),
        app_commands.Choice(name="Only explicitly allowed users", value="allowlist"),
    ]
)
async def access_mode_command(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
) -> None:
    bot = _bot(interaction)
    updated = await bot.database.set_access_mode(interaction.user.id, AccessMode(mode.value))
    if not updated:
        await _respond_error(interaction, "You are not linked to an OpenShock shocker.")
        return
    await interaction.response.send_message(
        f"Your access mode is now `{mode.value}`.",
        ephemeral=True,
    )


@openshock_group.command(name="status", description="Show a target's current bot settings.")
async def status_command(
    interaction: discord.Interaction,
    target: discord.Member | None = None,
) -> None:
    bot = _bot(interaction)
    selected = target or interaction.user
    config = await bot.database.get_target(selected.id)
    if config is None:
        await _respond_error(interaction, "That Discord user is not linked.")
        return
    bot = _bot(interaction)
    reaction_lines = []
    for emoji, action in bot.reaction_actions.items():
        reaction = config.reaction_settings[action]
        state = "enabled" if reaction.enabled else "disabled"
        reaction_lines.append(
            f"{emoji} {action.value}: `{state}` · "
            f"`{reaction.intensity}%/{reaction.duration_ms / 1000:g}s`"
        )
    await interaction.response.send_message(
        "\n".join(
            [
                f"**OpenShockBot status for {selected.mention}**",
                f"Paused: `{config.paused}`",
                "**Reaction controls**",
                *reaction_lines,
                f"Access mode: `{config.access_mode.value}`",
                f"Maximum intensity: `{config.max_intensity}%`",
                f"Maximum duration: `{config.max_duration_ms / 1000:g}s`",
                f"Cooldown: `{config.cooldown_seconds:g}s`",
            ]
        ),
        ephemeral=True,
    )


@openshock_group.command(
    name="configure",
    description="Set your personal safety caps and shared control cooldown.",
)
async def configure_command(
    interaction: discord.Interaction,
    max_intensity: app_commands.Range[int, 1, 100],
    max_duration: app_commands.Range[float, 0.3, 65.535],
    cooldown: app_commands.Range[float, 0, 3600],
) -> None:
    bot = _bot(interaction)
    target = await bot.database.get_target(interaction.user.id)
    if target is None:
        await _respond_error(interaction, "You are not linked to an OpenShock shocker.")
        return

    max_duration_ms = round(max_duration * 1000)
    if max_intensity > bot.settings.global_max_intensity:
        await _respond_error(
            interaction,
            f"The bot-wide intensity ceiling is {bot.settings.global_max_intensity}%.",
        )
        return
    if max_duration_ms > bot.settings.global_max_duration_ms:
        await _respond_error(
            interaction,
            "The requested maximum duration exceeds the bot-wide ceiling.",
        )
        return
    await bot.database.configure_target(
        interaction.user.id,
        max_intensity=max_intensity,
        max_duration_ms=max_duration_ms,
        cooldown_seconds=cooldown,
    )
    await interaction.response.send_message(
        "Your OpenShockBot safety settings were updated.",
        ephemeral=True,
    )


@openshock_group.command(
    name="reaction-config",
    description="Configure one reaction type's toggle and default strength.",
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="Shock", value=ControlType.SHOCK.value),
        app_commands.Choice(name="Vibrate", value=ControlType.VIBRATE.value),
        app_commands.Choice(name="Sound", value=ControlType.SOUND.value),
    ]
)
@app_commands.describe(
    action="The reaction type to configure.",
    enabled="Whether this emoji can trigger its action.",
    intensity="Default intensity for this reaction type.",
    duration="Default duration in seconds for this reaction type.",
)
async def reaction_config_command(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    enabled: bool,
    intensity: app_commands.Range[int, 1, 100],
    duration: app_commands.Range[float, 0.3, 65.535],
) -> None:
    bot = _bot(interaction)
    target = await bot.database.get_target(interaction.user.id)
    if target is None:
        await _respond_error(interaction, "You are not linked to an OpenShock shocker.")
        return

    duration_ms = round(duration * 1000)
    effective_max_intensity = min(target.max_intensity, bot.settings.global_max_intensity)
    effective_max_duration_ms = min(
        target.max_duration_ms,
        bot.settings.global_max_duration_ms,
    )
    if intensity > effective_max_intensity or duration_ms > effective_max_duration_ms:
        await _respond_error(
            interaction,
            "Reaction defaults cannot exceed the effective safety ceilings.",
        )
        return

    control_type = ControlType(action.value)
    updated = await bot.database.configure_reaction(
        interaction.user.id,
        control_type,
        enabled=enabled,
        intensity=intensity,
        duration_ms=duration_ms,
    )
    if not updated:
        await _respond_error(interaction, "That reaction setting could not be updated.")
        return
    state = "enabled" if enabled else "disabled"
    await interaction.response.send_message(
        f"{control_type.value} reactions are now {state} at "
        f"{intensity}% for {duration_ms / 1000:g}s.",
        ephemeral=True,
    )


@openshock_group.command(name="history", description="Show your ten most recent audit entries.")
async def history_command(interaction: discord.Interaction) -> None:
    bot = _bot(interaction)
    if await bot.database.get_target(interaction.user.id) is None:
        await _respond_error(interaction, "You are not linked to an OpenShock shocker.")
        return
    rows = await bot.database.recent_audit(interaction.user.id)
    if not rows:
        await interaction.response.send_message("Your audit history is empty.", ephemeral=True)
        return
    lines = ["**Recent OpenShockBot activity**"]
    for row in rows:
        effective = ""
        if row["effective_intensity"] is not None:
            effective = (
                f" · {row['effective_intensity']}%/{int(row['effective_duration_ms']) / 1000:g}s"
            )
        lines.append(
            f"`{str(row['occurred_at'])[:19]}` <@{row['actor_discord_user_id']}> "
            f"{row['action']} via {row['source']} · **{row['outcome']}**{effective}"
        )
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@openshock_group.command(name="link", description="Link a Discord member to a shocker UUID.")
@app_commands.describe(shocker_id="The shocker's OpenShock UUID; this response is private.")
async def link_command(
    interaction: discord.Interaction,
    target: discord.Member,
    shocker_id: str,
) -> None:
    bot = _bot(interaction)
    if not await bot.is_owner(interaction.user):
        await _respond_error(interaction, "Only a configured bot owner can link shockers.")
        return
    await bot.database.upsert_target(
        target.id,
        shocker_id.strip(),
        display_name=target.display_name,
        max_intensity=min(25, bot.settings.global_max_intensity),
        max_duration_ms=min(3000, bot.settings.global_max_duration_ms),
        cooldown_seconds=bot.settings.default_cooldown_seconds,
    )
    await interaction.response.send_message(
        f"{target.mention} is linked. The shocker UUID was not echoed.",
        ephemeral=True,
    )


def run_bot(settings: Settings) -> None:
    bot = OpenShockDiscordBot(settings)
    bot.run(settings.discord_bot_token, log_handler=None)
