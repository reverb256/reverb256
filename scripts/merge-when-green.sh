#!/usr/bin/env bash
# Pending, red, missing or unreadable checks never merge.
set -euo pipefail
: "${GH_TOKEN:?GH_TOKEN is required}"
: "${GH_REPO:?GH_REPO is required}"
: "${EVENT_NAME:?EVENT_NAME is required}"
: "${EVENT_PATH:?EVENT_PATH is required}"
export GH_TOKEN

pr_number=$(jq -r 'if env.EVENT_NAME == "pull_request_target" then .pull_request.number elif env.EVENT_NAME == "workflow_run" then (.workflow_run.pull_requests[0].number // empty) else empty end' "$EVENT_PATH")
[[ -n "$pr_number" ]] || { echo "::notice::No pull request is associated with this event."; exit 0; }
meta=$(gh api "repos/$GH_REPO/pulls/$pr_number")
[[ $(jq -r .state <<<"$meta") == open ]] || { echo "::notice::PR #$pr_number is not open."; exit 0; }
head_sha=$(jq -r .head.sha <<<"$meta")
head_repo=$(jq -r '.head.repo.full_name // empty' <<<"$meta")
base_ref=$(jq -r .base.ref <<<"$meta")
draft=$(jq -r .draft <<<"$meta")
mergeable=$(jq -r 'if .mergeable == null then "unknown" else .mergeable end' <<<"$meta")
labelled=$(jq -r 'any(.labels[]?; .name == "ready-to-merge")' <<<"$meta")
[[ "$head_repo" == "$GH_REPO" ]] || { echo "::notice::PR #$pr_number has a foreign or unknown head."; exit 0; }
[[ "$base_ref" == main && "$draft" == false ]] || { echo "::notice::PR #$pr_number is draft or does not target main."; exit 0; }
[[ "$mergeable" != false ]] || { echo "::notice::PR #$pr_number is not mergeable."; exit 0; }
[[ "$labelled" == true ]] || { echo "::notice::PR #$pr_number lacks ready-to-merge."; exit 0; }

checks=$(gh api "repos/$GH_REPO/commits/$head_sha/check-runs?per_page=100" --jq .check_runs)
for required in pytest lint lychee; do
  row=$(jq -c --arg name "$required" '[.[] | select(.name == $name)] | sort_by(.id) | last // empty' <<<"$checks")
  [[ -n "$row" ]] || { echo "::notice::PR #$pr_number is missing required check $required."; exit 0; }
  [[ $(jq -r .status <<<"$row") == completed ]] || { echo "::notice::PR #$pr_number check $required is pending."; exit 0; }
  conclusion=$(jq -r '.conclusion // ""' <<<"$row")
  case "$conclusion" in
    success|skipped|neutral) ;;
    *) echo "::notice::PR #$pr_number check $required concluded $conclusion."; exit 0 ;;
  esac
done
echo "::notice::All required checks are green for PR #$pr_number at $head_sha; merging."
gh pr merge "$pr_number" --repo "$GH_REPO" --squash --delete-branch
