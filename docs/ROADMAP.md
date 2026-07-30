# Roadmap

This roadmap translates the desired ShockBot-style experience into an OpenShock-native design.
Priorities may move as real-world testing exposes safety, consent, or Discord usability needs.

## Phase 1 — Safe control foundation

- [x] Async OpenShock v2 control adapter
- [x] Shock, vibrate, sound, and stop slash commands
- [x] Linked Discord users and OpenShock shocker UUIDs
- [x] Personal pause, block list, allow list, and access mode
- [x] Bot-wide and personal intensity/duration ceilings
- [x] Per-actor cooldowns and per-target command serialization
- [x] SQLite audit history
- [x] Reaction triggers using wearer-controlled defaults
- [x] Self-service defaults and safety configuration
- [x] Per-reaction enable toggles, intensity, and duration
- [x] Central-account shared-shocker onboarding with target consent

## Phase 2 — Reaction experience

- [ ] Configurable reaction emojis per server or target
- [ ] Short aggregation windows for multiple unique reactors
- [ ] Wearer-selected aggregation curve with a hard cap
- [ ] Duplicate-event and remove/re-add replay protection
- [ ] Optional quiet, reaction-based, or channel-message acknowledgement
- [ ] Per-source controls so wearers can disable reactions without disabling commands

Reaction counts must never bypass the target's personal or bot-wide ceilings.

## Phase 3 — Discord interaction surfaces

- [ ] Persistent quick-action button panels
- [ ] Quick action plus custom intensity/duration modal
- [ ] Message context-menu controls
- [ ] User context-menu controls
- [ ] Ephemeral light/medium/heavy selection
- [ ] Target and preset select menus

Every surface will create the same internal control request and pass through the same policy engine.

## Phase 4 — Presets and richer personalization

- [ ] Named personal presets
- [ ] Per-controller defaults, bounded by the target's settings
- [ ] Per-action limits and cooldowns
- [ ] Multiple shockers per Discord target
- [ ] Optional server role rules
- [ ] Audit export and retention controls

## Phase 5 — Operations and community

- [ ] Database migrations and backup documentation
- [ ] Health checks and structured logs
- [ ] Release automation and signed container images
- [ ] Localization framework
- [ ] Private GitHub vulnerability reporting
- [ ] Maintainer and moderation documentation

## Non-goals

- Bypassing OpenShock permissions or limits
- Allowing Discord administrators to override a wearer's personal block list
- Storing Discord or OpenShock credentials in the database
- Treating software stop as a replacement for a physical emergency stop
