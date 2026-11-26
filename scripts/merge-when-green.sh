#!/usr/bin/env bash
# Label-gated squash merge. Pending/red checks and unreadable state never merge.
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${GH_REPO:?GH_REPO is required}"
: "${EVENT_NAME:?EVENT_NAME is required}"
: "${EVENT_PATH:?EVENT_PATH is required}"
export GH_TOKEN

pr_number=$(python3 - "$EVENT_NAME" "$EVENT_PATH" <<'PY'
import json
import sys

name, path = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as handle:
    event = json.load(handle)
if name == "pull_request_target":
    number = event.get("pull_request", {}).get("number")
elif name == "workflow_run":
    pulls = event.get("workflow_run", {}).get("pull_requests") or []
    number = pulls[0].get("number") if pulls else None
else:
    number = None
print(number or "")
PY
)

if [[ -z "$pr_number" ]]; then
  echo "::notice::No pull request is associated with this event; nothing to do."
  exit 0
fi

meta=$(gh api "repos/$GH_REPO/pulls/$pr_number")
state=$(jq -r '.state' <<<"$meta")
if [[ "$state" != "open" ]]; then
  echo "::notice::PR #$pr_number is not open; nothing to do."
  exit 0
fi

head_sha=$(jq -r '.head.sha' <<<"$meta")
head_repo=$(jq -r '.head.repo.full_name // empty' <<<"$meta")
base_ref=$(jq -r '.base.ref' <<<"$meta")
draft=$(jq -r '.draft' <<<"$meta")
mergeable=$(jq -r 'if .mergeable == null then "unknown" else .mergeable end' <<<"$meta")
labelled=$(jq -r 'any(.labels[]?; .name == "ready-to-merge")' <<<"$meta")

if [[ "$head_repo" != "$GH_REPO" ]]; then
  echo "::notice::PR #$pr_number has a foreign or unknown head repository; nothing to do."
  exit 0
fi
if [[ "$base_ref" != "main" || "$draft" != "false" ]]; then
  echo "::notice::PR #$pr_number is draft or does not target main; nothing to do."
  exit 0
fi
if [[ "$mergeable" == "false" ]]; then
  echo "::notice::PR #$pr_number is not mergeable; nothing to do."
  exit 0
fi
if [[ "$labelled" != "true" ]]; then
  echo "::notice::PR #$pr_number lacks ready-to-merge; nothing to do."
  exit 0
fi

checks=$(gh api "repos/$GH_REPO/commits/$head_sha/check-runs?per_page=100" --jq '.check_runs')
for required in pytest lint lychee; do
  row=$(jq -c --arg name "$required" '[.[] | select(.name == $name)] | sort_by(.id) | last // empty' <<<"$checks")
  if [[ -z "$row" ]]; then
    echo "::notice::PR #$pr_number is missing required check $required; nothing to do."
    exit 0
  fi
  status=$(jq -r '.status' <<<"$row")
  conclusion=$(jq -r '.conclusion // ""' <<<"$row")
  if [[ "$status" != "completed" ]]; then
    echo "::notice::PR #$pr_number check $required is pending; nothing to do."
    exit 0
  fi
  case "$conclusion" in
    success|skipped|neutral) ;;
    *)
      echo "::notice::PR #$pr_number check $required concluded $conclusion; nothing to do."
      exit 0
      ;;
  esac
done

echo "::notice::All required checks are green for PR #$pr_number at $head_sha; merging."
gh pr merge "$pr_number" --repo "$GH_REPO" --squash --delete-branch
