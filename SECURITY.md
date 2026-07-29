# Security Policy

## Reporting a vulnerability

Do not open a public issue for vulnerabilities involving credentials, authorization bypasses,
unsafe control behavior, or private user data.

Use GitHub's private
[vulnerability reporting form](https://github.com/J-Fidel/OpenShockBot/security/advisories/new).
Reports submitted there are visible only to repository maintainers and invited security
collaborators.

## Secrets

OpenShockBot loads credentials from environment variables. `.env` is ignored by Git. If a Discord
or OpenShock token is ever exposed, revoke and replace it immediately; deleting it from the latest
commit is not sufficient.
