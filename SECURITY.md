# Security Policy

## Reporting a vulnerability

Do not open a public issue for vulnerabilities involving credentials, authorization bypasses,
unsafe control behavior, or private user data.

Until private GitHub vulnerability reporting is configured, contact the repository owner privately.
The owner should enable **Settings → Security → Private vulnerability reporting** immediately after
the repository is published, then update this file with the reporting link.

## Secrets

OpenShockBot loads credentials from environment variables. `.env` is ignored by Git. If a Discord
or OpenShock token is ever exposed, revoke and replace it immediately; deleting it from the latest
commit is not sufficient.
