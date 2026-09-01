# Contributing to AegisForge

> ### ⚠️ Server-side protection is NOT active yet
>
> This document describes the workflow the repository is **moving to**. Right
> now `main` and `dev` have **no ruleset and no branch protection** — anyone
> with write access can still push to them directly. The local `pre-push` hook
> guards both branches but is skippable and absent in a fresh clone, and it is
> now the **only** guard. A direct push is still perfectly visible — the commit
> lands in branch history and the repository activity feed like any other — but
> nothing prevents it and nothing announces it. Someone has to look.
>
> Protection goes live when a repository admin runs
> `./scripts/setup-branch-protection.sh` **and it succeeds**. That may require
> a plan change first — rulesets on a private repository need GitHub Pro, Team,
> or Enterprise. See [Enforcement](#enforcement).
>
> **Follow the workflow anyway.** It is the team's rule whether or not GitHub
> is enforcing it yet. Delete this banner once protection is confirmed active.

This document is the branch, review, and ownership workflow required by
[`AGENTS.md`](AGENTS.md).

## The one rule

```
  your branch  ──PR──>  dev  ──PR──>  main
```

**Nobody pushes to `main`. Nobody pushes to `dev`.** Not the repo owner, not
in an emergency, not "just this once". Both branches accept commits only
through a pull request.

That is the *only* hard rule. Everything else is open: anyone may open, review,
or merge a PR, including their own. Member → `dev` PRs run no automated CI.
Automated checks run only on the `dev` → `main` release PR, which merges when
those checks are green. No approval quota or owner sign-off is required.

## One-time setup

Clone, then install the local hooks:

```bash
git clone https://github.com/prachi-satbhai0741/AegisForge.git
cd AegisForge
./scripts/install-hooks.sh
```

That installs a `pre-push` hook that stops a stray `git push origin main`
on your own machine, with a message telling you what to do instead. Until
server-side protection is active this hook is the *only* thing standing
between a tired developer and `main`, so please install it.

Check it worked — this command **should fail**:

```bash
git push --dry-run origin HEAD:main
```

## Branches

| Branch | Owner | Purpose |
|---|---|---|
| `main` | PR-only *(protection pending)* | Release. Only receives a checked PR from `dev`. |
| `dev` | PR-only *(protection pending)* | Integration. Receives member PRs without automated CI. |
| `aditya` | @adityatadge31 | Personal work branch |
| `prachi` | @prachi-satbhai0741 | Personal work branch |
| `sahil` | @sahilranade45 | Personal work branch |
| `tanvi` | @tanvishinde3010 | Personal work branch |
| `vedant` | @vedantsur09 | Personal work branch |
| `yug` | @Yugu-48 | Personal work branch |

Work on your own branch. If you have several things in flight, open topic
branches underneath your name — `aditya/coordinator-api`, `yug/ocr-worker`.
Both the bare name and the `name/topic` form are accepted into `dev`.

Do not push to someone else's branch. Open a PR against it if you need to
contribute there.

## Daily flow

```bash
# 1. Start from the latest dev
git switch dev && git pull
git switch -c <your-name>/<topic>     # or: git switch <your-name>

# 2. Work, commit
git add -p
git commit -m "coordinator: add capability registry"

# 3. Push your branch
git push -u origin <your-name>/<topic>

# 4. Open a PR into dev
gh pr create --base dev --fill
```

Fill in the PR template properly. The evidence and safety sections are not
decoration — see "Review" below.

Member → `dev` PRs do not start automated CI. The team may review and merge
them directly; the accumulated `dev` branch is checked at release time.

## Releasing to `main`

Only `dev` opens a PR into `main`. This is the only PR type that starts
automated CI. Any other source branch fails `pr-flow-guard`.

```bash
gh pr create --base main --head dev --title "Release: <what is in it>"
```

`main` merges use a **merge commit**, never a squash — a squash would rewrite
the commits and leave `dev` permanently diverged from `main`. PRs into `dev`
may be squashed.

## Merging

Member → `dev` PRs have no automated CI gate. The `dev` → `main` release PR
merges when its checks are green. No approving review is required, and you may
merge your own PR at either stage.

There is deliberately no `CODEOWNERS` file. It would auto-request a review on
every PR touching an owned path, and since no review is required those requests
are pure notification noise. Ask for a review when you want one.

Work on `dev` until it is genuinely ready, then take it to `main` in one PR.
Anyone can open and merge that release PR.

Reviewing is still worth doing. When you do, check:

- **Evidence.** [Evaluation rules](docs/evaluation.md#1-evidence-labels):
  decisions are evidence-backed and dated. A claim with no reproducible
  observation behind it is not ready.
- **Honest labels.** Features are labelled planned, prototyped, verified,
  deferred, or rejected. "Prototyped" presented as "verified" is a bug.
- **No mocked paths sold as real.** The
  [Day 1 gate](docs/evaluation.md#day-1-baseline-and-one-local-engine) requires
  no mocked inference in the claimed path.
- **AI output was actually read.** Do not merge generated output nobody has
  reviewed.
- **Nothing forbidden was committed.** See below.

## Never commit

From [security.md](docs/security.md#11-repository-content):

- Model weights
- Generated installers or release binaries
- Signing keys or tokens
- Private documents
- Real confidential scans
- Local chat databases
- Environment files containing secrets

Use synthetic or explicitly approved non-sensitive test fixtures.

## Enforcement

Two layers, weakest to strongest:

| Layer | What it does | Can it be bypassed? |
|---|---|---|
| [`.githooks/pre-push`](.githooks/pre-push) | Blocks direct pushes to `main`/`dev` locally | Yes — `--no-verify`, or a clone that never ran the installer |
| Branch ruleset | Server-side rejection — **not applied yet** | Once applied, no: `bypass_actors` is empty, so admins are included |

There is deliberately **no** GitHub Actions audit of pushes. Automated checks
run only on pull requests targeting `main`, so Actions minutes are spent on the
release gate and nothing else. The trade-off is worth stating plainly: until
the ruleset is applied, nothing prevents a direct push to `main` or `dev` and
nothing alerts you to one. The commit is not hidden — it appears in `git log`,
in the branch's commit list, and in the repository activity feed — but finding
it depends on somebody checking. Install the hook, and treat the rule as a team
commitment.

Both rulesets require a PR. Only the `main` ruleset requires passing status
checks; the `dev` ruleset has none. Neither requires approvals —
`required_approving_review_count` is `0` by design.

**It is not applied yet.** Rulesets and branch protection on a *private*
repository require GitHub Pro, Team, or Enterprise; GitHub Free gets them on
public repositories only, and moving to a free organisation does not change
that. So one of these has to happen first:

- make the repository public — free and immediate, but settle
  [OD-02](docs/prd.md#11-open-decisions) first, since the repo carries
  Apache-2.0
- the owner upgrades to GitHub Pro
- transfer to an organisation on GitHub Team

Run `./scripts/setup-branch-protection.sh`; its preflight reports the plan and
tells you which case you are in.

The ruleset is applied by
[`scripts/setup-branch-protection.sh`](scripts/setup-branch-protection.sh) and
requires **repository admin**. Until it succeeds, direct pushes to both `main`
and `dev` rely entirely on the local hook and team discipline.

### Adding a build or test gate

Right now the only main-release check is `pr-flow-guard`. As build, test, and
lint jobs land, configure them to run for PRs targeting `main`, then add their
**job names** to the main release list:

```bash
MAIN_REQUIRED_CHECKS="pr-flow-guard build test lint" ./scripts/setup-branch-protection.sh
```

The name must match the workflow's `jobs.<id>.name` and that job must run on
`pull_request` for `main`, or the release PR waits forever on a check that
never reports.

### Why pr-flow-guard exists

The `pr-flow-guard` release check enforces that a PR into `main` comes only
from `dev`. It runs and is required on `main` only. Member → `dev` naming and
ownership remain a team convention rather than an automated check.

## Emergency changes

There is no bypass path by design. If `main` is genuinely broken:

1. Say so in the team channel first.
2. An admin sets the `aegisforge-main` ruleset to **Disabled** in
   Settings → Rules → Rulesets.
3. Make the fix.
4. Re-enable the ruleset immediately.

Do not add a permanent bypass actor.

## Adding or removing a team member

Update the branch table above, and create or delete their branch. Nothing else
references the member list: `pr-flow-guard` only checks that a pull request into
`main` comes from `dev`, so member branches need no allowlist.

The change lands like any other: PR into `dev`, then `dev` into `main`.
