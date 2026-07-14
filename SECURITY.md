# Security Policy

SchemaSafeBench executes generated SQL only against explicitly configured public benchmark databases. Its validator is a research guardrail, not a production security boundary.

## Report a vulnerability

Do not open a public issue for a vulnerability that can bypass query policy, mutate a database, escape configured paths, expose credentials, or cause uncontrolled resource use. Use GitHub private vulnerability reporting for this repository.

Include a minimal public fixture, affected revision, impact, and reproduction steps. Do not include proprietary schemas, live credentials, or private data.

## Supported code

Security fixes target the current `main` branch. Published releases may be patched when the affected behavior is present there.
