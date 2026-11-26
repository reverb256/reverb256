
---

## Git hygiene rules (fleet-wide)

Fleet-wide rules are maintained in one place: the `homelab-ops` repo,
`AGENTS-shared/` directory:
- `git-hygiene.md` — staging, forbidden files, gates, identity, pre-push checks
- `merge-policy.md` — PR merge workflow (AI agents label and merge)
- `fleet-conventions.md` — deployment, budget, secrets, SPOF, hard rules

Do not duplicate these blocks locally. Check drift with
`bin/agents-md-check.py --check` from the homelab-ops repo.
