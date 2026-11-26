# AGENTS.md guard

A small composite action that requires the canonical fleet `AGENTS.md` pointer
and rejects the retired direct-merge policy wording. It does not copy or own
the rules; the rules remain in `homelab-ops/AGENTS-shared/`.

## Usage

```yaml
- uses: reverb256/reverb256/.github/actions/agents-md-guard@<commit-sha>
  with:
    files: AGENTS.md
```

Pin the action to a full commit SHA. The default input is `AGENTS.md`.

The guard fails when a file:

- contains the old duplicated fleet-rules block;
- omits the canonical `homelab-ops/AGENTS-shared/` pointer;
- uses the retired `AI agents label and merge` pointer wording;
- instructs an agent to run a direct merge;
- says the `ready-to-merge` label is optional or not required.

Negated references such as “never run `gh pr merge`” are allowed.
