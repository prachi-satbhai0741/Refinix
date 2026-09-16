# Contributing to Refinix

> ### ⚠️ Server-side protection is NOT active yet
>
> This document describes the workflow the repository is **moving to**. Right
> now `main` and `dev` have **no ruleset and no branch protection** — anyone
> with write access can still push to them directly. The local `pre-push` hook
> guards both branches but is skippable and absent in a fresh clone, and it is
> now the **only preventive** guard. A direct push still lands immediately;
> Main CI reports its result afterward but cannot undo or block the push.
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
Automated checks run on the `dev` → `main` release PR and again after its commit
lands on `main`. No approval quota or owner sign-off is required.

## Repository rename status

The requested GitHub name is `prachi-satbhai0741/refinix`. On 2026-09-13 the
available authenticated account had write access but no administrator permission,
so the remote rename remains pending. A repository administrator can open
Settings → General → Repository name, enter `refinix`, and choose Rename.
[GitHub requires administrator permission for this operation](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository).

After confirming the renamed repository still has id `1352342428`, update each
existing clone's origin to `https://github.com/prachi-satbhai0741/refinix.git`.
Existing local directory names can stay unchanged; renaming the GitHub repository
does not require moving a working checkout or migrating `.aegisforge` user data.
Update the clone URL below after the remote rename is verified.

## One-time setup

The selected repository name is `refinix`. Until a repository administrator
completes the GitHub rename, clone the existing URL into a `refinix` directory,
then install the local hooks:

```bash
git clone https://github.com/prachi-satbhai0741/AegisForge.git refinix
cd refinix
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

## Contribution flow

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
pre-merge CI. Any other source branch fails `pr-flow-guard`. Main CI also runs
after every commit that lands on `main`, whether by merge or direct push.

```bash
gh pr create --base main --head dev --title "Release: <what is in it>"
```

`main` merges use a **merge commit**, never a squash — a squash would rewrite
the commits and leave `dev` permanently diverged from `main`. PRs into `dev`
may be squashed.

Merging source into main does not publish or install an application update.
The planned [application release contract](docs/releases.md) requires a designated
version, qualified platform builds, signing and update metadata. The current CI
checks source; these documents do not add or authorise publishing automation.

## Merging

Member → `dev` PRs have no automated CI gate. The `dev` → `main` release PR
merges when its checks are green. No approving review is required, and you may
merge your own PR at either stage.

There is deliberately no `CODEOWNERS` file. It would auto-request a review on
every PR touching an owned path, and since no review is required those requests
are pure notification noise. Ask for a review when you want one.

Work on `dev` until it is genuinely ready, then take it to `main` in one PR.
Anyone can open and merge that release PR.

For each release band, follow the [execution review and device-based human
checkpoints](tasks.md#numbered-execution-tasks) before promotion.
These are work-acceptance gates; they do not add a GitHub approval quota or
change the workflow triggers. Git publication remains a human action unless
explicitly authorised under [AGENTS.md](AGENTS.md#git).

Reviewing is still worth doing. When you do, check:

- **Evidence.** [Evaluation rules](docs/evaluation.md#1-evidence-labels):
  decisions are evidence-backed and dated. A claim with no reproducible
  observation behind it is not ready.
- **Honest labels.** Features are labelled planned, prototyped, verified,
  deferred, or rejected. "Prototyped" presented as "verified" is a bug.
- **No mocked paths sold as real.** The
  [C05 gate](docs/evaluation.md#c05-contracts-and-local-execution) requires
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

Three layers, weakest to strongest:

| Layer | What it does | Can it be bypassed? |
|---|---|---|
| [`.githooks/pre-push`](.githooks/pre-push) | Blocks direct pushes to `main`/`dev` locally | Yes — `--no-verify`, or a clone that never ran the installer |
| [Main CI](.github/workflows/ci.yml) | Tests pull requests into `main` and commits that land on `main` | Yes as prevention — push checks run only after the commit lands |
| Branch ruleset | Server-side rejection — **not applied yet** | Once applied, no: `bypass_actors` is empty, so admins are included |

Main CI audits every push to `main`, but it does not turn a failed check into a
rejected push. Until the ruleset is applied, nothing server-side prevents a
direct push to `main` or `dev`. Install the hook and treat the PR-only rule as a
team commitment.

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

### Main CI and required checks

The `ci` job runs the pinned Python and browser-side suites on pull requests
targeting `main` and on pushes to `main`. To make it a merge gate when applying
the main ruleset, include its **job name** in the release list:

```bash
MAIN_REQUIRED_CHECKS="pr-flow-guard ci" ./scripts/setup-branch-protection.sh
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
