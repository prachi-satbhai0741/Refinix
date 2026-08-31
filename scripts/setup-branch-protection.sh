#!/usr/bin/env bash
#
# AegisForge — one-time branch protection setup.
#
#   member branch  ->  dev  ->  main      (pull requests only, no exceptions)
#
# WHO RUNS THIS
#   A repository ADMIN. At the time of writing that is only
#   @prachi-satbhai0741. Everyone else has `write` and will get HTTP 403.
#
# WHAT IT DOES
#   Creates (or updates) two GitHub repository rulesets:
#
#     aegisforge-main   on refs/heads/main
#     aegisforge-dev    on refs/heads/dev
#
#   Both rulesets:
#     - block direct pushes (a pull request is required)
#     - block force pushes
#     - block branch deletion
#
#   The main ruleset also requires every check in MAIN_REQUIRED_CHECKS.
#   The dev ruleset requires a PR but deliberately runs no automated CI.
#
#   Deliberately NOT required: approving reviews and CODEOWNERS sign-off.
#   The team rule is "anyone can do anything, but nothing is pushed directly".
#   Any member may open, review, and merge any pull request, including their
#   own. Automated CI and required checks run only on the dev -> main release
#   PR, not on member -> dev integration PRs. Raise
#   REQUIRED_APPROVALS below if the team later wants a review gate.
#
#   `pr-flow-guard` enforces that only `dev` may open a PR into `main`.
#   Member -> dev remains a team convention without automated checks.
#
# STRICTNESS
#   bypass_actors is empty. Admins are NOT exempt — that is what "no direct
#   main push at all" means. To make an emergency change, temporarily set the
#   ruleset enforcement to "disabled" in
#   Settings -> Rules -> Rulesets, make the change, then re-enable it. Do that
#   deliberately and tell the team; do not add a permanent bypass.
#
# PREREQUISITES
#   1. gh CLI installed and authenticated:  gh auth status
#   2. .github/workflows/pr-flow-guard.yml already merged into `main`, otherwise
#      the release check never reports and PRs into main hang forever.
#
# USAGE
#   ./scripts/setup-branch-protection.sh
#   ./scripts/setup-branch-protection.sh --dry-run
#   REPO=owner/name ./scripts/setup-branch-protection.sh

set -euo pipefail

REPO="${REPO:-prachi-satbhai0741/AegisForge}"

# Checks that must pass before a dev -> main release pull request can merge.
# Space separated, and each name must match a JOB name in a workflow that
# actually runs on `pull_request` for main -- otherwise the PR waits
# forever for a check that never reports.
#
# Add build/test/lint jobs here as they land, e.g.
#   MAIN_REQUIRED_CHECKS="pr-flow-guard build test"
MAIN_REQUIRED_CHECKS="${MAIN_REQUIRED_CHECKS:-pr-flow-guard}"

# 0 = anyone may merge their own pull request once checks pass.
# Raise to 1 to require a second pair of eyes.
REQUIRED_APPROVALS="${REQUIRED_APPROVALS:-0}"

DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

# Colour only when attached to a terminal, so piped/CI output stays readable.
if [ -t 1 ]; then
  C_INFO=$'\033[0;36m'; C_OK=$'\033[0;32m'; C_WARN=$'\033[0;33m'
  C_ERR=$'\033[0;31m';  C_OFF=$'\033[0m'
else
  C_INFO=''; C_OK=''; C_WARN=''; C_ERR=''; C_OFF=''
fi

info() { printf '%s==>%s %s\n' "$C_INFO" "$C_OFF" "$*"; }
ok()   { printf '%s  ok%s %s\n'  "$C_OK"   "$C_OFF" "$*"; }
warn() { printf '%s  !!%s %s\n'  "$C_WARN" "$C_OFF" "$*"; }
die()  { printf '%sERROR%s %s\n' "$C_ERR"  "$C_OFF" "$*" >&2; exit 1; }

command -v gh >/dev/null 2>&1 || die "gh CLI not found. Install: https://cli.github.com"
gh auth status >/dev/null 2>&1 || die "gh is not authenticated. Run: gh auth login"

info "Repository: $REPO"

# ---------------------------------------------------------------------------
# Preflight: admin permission
# ---------------------------------------------------------------------------
perm="$(gh api "repos/$REPO" --jq '.permissions.admin' 2>/dev/null || echo "false")"
if [ "$perm" != "true" ]; then
  actor="$(gh api user --jq '.login' 2>/dev/null || echo 'unknown')"
  {
    printf '%sERROR%s %s\n' "$C_ERR" "$C_OFF" \
      "'$actor' does not have admin permission on $REPO."
    echo ""
    echo "Rulesets and branch protection require admin. Ask the repository owner"
    echo "(@prachi-satbhai0741) to either:"
    echo ""
    echo "  a) run this script themselves, or"
    echo "  b) grant admin:  Settings -> Collaborators -> $actor -> role: Admin"
  } >&2
  exit 1
fi
ok "admin permission confirmed"

# ---------------------------------------------------------------------------
# Preflight: plan. Rulesets and branch protection on PRIVATE repositories
# require GitHub Pro, Team, or Enterprise. GitHub Free (personal accounts and
# free organisations alike) gets them on PUBLIC repositories only.
# ---------------------------------------------------------------------------
is_private="$(gh api "repos/$REPO" --jq '.private' 2>/dev/null || echo "unknown")"
if [ "$is_private" = "true" ]; then
  owner_type="$(gh api "repos/$REPO" --jq '.owner.type' 2>/dev/null || echo "User")"
  if [ "$owner_type" = "Organization" ]; then
    plan="$(gh api "orgs/${REPO%%/*}" --jq '.plan.name // "unknown"' 2>/dev/null || echo "unknown")"
  else
    plan="$(gh api user --jq '.plan.name // "unknown"' 2>/dev/null || echo "unknown")"
  fi

  case "$plan" in
    free)
      warn "This is a PRIVATE repository on a GitHub Free plan."
      warn "Rulesets and branch protection on private repositories require"
      warn "Pro, Team, or Enterprise. The calls below will almost certainly"
      warn "fail with 403. See the options printed at the end."
      ;;
    unknown)
      warn "Private repository; could not read the plan. If the calls below"
      warn "fail with 403, the plan is the reason -- see the end of the output."
      ;;
    *)
      ok "private repository on plan '$plan' (rulesets supported)"
      ;;
  esac
fi

# ---------------------------------------------------------------------------
# Preflight: the release check must exist on main
# ---------------------------------------------------------------------------
if gh api "repos/$REPO/contents/.github/workflows/pr-flow-guard.yml?ref=main" >/dev/null 2>&1; then
  ok "pr-flow-guard.yml present on 'main'"
else
  warn "pr-flow-guard.yml is NOT on 'main' yet."
  warn "Merge it there first, or release PRs will wait forever for a check that never runs."
fi
info "Main release required checks: $MAIN_REQUIRED_CHECKS"
info "Dev integration required checks: none"

# ---------------------------------------------------------------------------
# Ruleset payloads
# ---------------------------------------------------------------------------
# main: release branch. Only `dev` may open a PR into it (enforced by the
# pr-flow-guard check). Merge commits only, so `dev` never diverges from `main`.
ruleset_json() {
  local branch="$1" merge_methods="$2" required_checks="$3"
  local checks_json="" status_rule_json="" c

  for c in $required_checks; do
    [ -n "$checks_json" ] && checks_json="${checks_json},"
    checks_json="${checks_json}{ \"context\": \"${c}\" }"
  done

  if [ -n "$checks_json" ]; then
    status_rule_json="$(cat <<JSON
,
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [ ${checks_json} ]
      }
    }
JSON
)"
  fi

  cat <<JSON
{
  "name": "aegisforge-${branch}",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/${branch}"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": ${REQUIRED_APPROVALS},
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ${merge_methods}
      }
    }${status_rule_json}
  ]
}
JSON
}

apply_ruleset() {
  local branch="$1" merge_methods="$2" required_checks="$3"
  local name="aegisforge-${branch}"
  local payload id

  payload="$(ruleset_json "$branch" "$merge_methods" "$required_checks")"

  if [ "$DRY_RUN" -eq 1 ]; then
    info "[dry-run] would apply ruleset '$name':"
    echo "$payload"
    return 0
  fi

  # Idempotent: update in place if a ruleset with this name already exists.
  id="$(gh api "repos/$REPO/rulesets" --jq ".[] | select(.name==\"$name\") | .id" 2>/dev/null || true)"

  if [ -n "$id" ]; then
    info "Updating existing ruleset '$name' (id $id)"
    if printf '%s' "$payload" | gh api --method PUT "repos/$REPO/rulesets/$id" --input - >/dev/null; then
      ok "'$branch' protected (ruleset updated)"
    else
      die "failed to update ruleset '$name'. See the note on plan limits at the end of this script."
    fi
  else
    info "Creating ruleset '$name'"
    if printf '%s' "$payload" | gh api --method POST "repos/$REPO/rulesets" --input - >/dev/null; then
      ok "'$branch' protected (ruleset created)"
    else
      die "failed to create ruleset '$name'. See the note on plan limits at the end of this script."
    fi
  fi
}

# main takes merge commits only: a squash would rewrite the commits and leave
# `dev` permanently diverged from `main`.
apply_ruleset "main" '["merge"]' "$MAIN_REQUIRED_CHECKS"

# dev takes squash or merge: squashing a member branch keeps dev history clean.
apply_ruleset "dev" '["squash","merge"]' ""

# ---------------------------------------------------------------------------
# Repository-level merge settings
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" -eq 0 ]; then
  info "Configuring repository merge settings"
  gh api --method PATCH "repos/$REPO" \
    -f allow_merge_commit=true \
    -f allow_squash_merge=true \
    -f allow_rebase_merge=false \
    -f delete_branch_on_merge=false \
    -f allow_auto_merge=true >/dev/null \
    && ok "merge settings applied (rebase off; branches kept after merge)" \
    || warn "could not update merge settings; set them by hand in Settings -> General"
fi

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" -eq 0 ]; then
  info "Active rulesets on $REPO:"
  gh api "repos/$REPO/rulesets" \
    --jq '.[] | "  \(.name)  target=\(.target)  enforcement=\(.enforcement)"'
fi

cat <<'DONE'

----------------------------------------------------------------------
Done. The flow is now:

  <member>  ->  dev  ->  main

  - direct pushes to main and dev are rejected
  - force pushes and deletion of main and dev are rejected
  - member -> dev PRs run no automated CI or required status checks
  - a PR into main that does not come from dev fails pr-flow-guard
  - dev -> main runs the release CI and must have green checks to merge
  - anyone may open, review and merge any PR, including their own
  - admins are NOT exempt (bypass_actors is empty)

Tell everyone to run once, in their clone:

  ./scripts/install-hooks.sh

That installs a local pre-push hook so a stray `git push origin main`
fails on their machine instead of being rejected by the server.

If a ruleset call failed with 403, this PRIVATE repository's plan very
likely does not include rulesets. GitHub restricts rulesets and branch
protection on PRIVATE repositories to GitHub Pro, Team, and Enterprise.
GitHub Free -- personal accounts AND free organisations -- gets them on
PUBLIC repositories only. Transferring to a free organisation does NOT
help.

Real options:
  - make the repository public (free, works immediately). Settle the
    docs/prd.md 17.1 licence question first -- the repo carries Apache-2.0.
  - the owner upgrades their personal account to GitHub Pro.
  - transfer to an organisation on GitHub Team (per-user cost).

Until one of those is true, main and dev are NOT protected. The pre-push
hook is the only guard, and it cannot stop a determined or accidental push --
a fresh clone has no hook, and nothing on GitHub audits pushes.
----------------------------------------------------------------------
DONE
