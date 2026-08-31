# frontend

Desktop workspace UI and the public distribution site.

## Intended boundary

From [`docs/prd.md`](../docs/prd.md) sections 4.2, 10.1, and 10.2:

- **Multi-chat workspace** — the familiar local interface, with chats, files,
  and job state owned by the coordinator.
- **Model and capability installer UI** — compatibility state, installed state,
  licence and source information (11.6, 11.7).
- **Worker dashboard** — device identity, health, and selected model.
- **Job timeline and routing explanation** — which worker, which model, and why
  (the visible routing evidence in section 3).
- **Public site** (4.2, 10.1) — explains the product, publishes installer
  versions and SHA-256 checksums. It never runs inference, stores chats, or
  coordinates workers.

The UI must clearly distinguish **Connected Setup** from **Offline Runtime**
(16.3), and the site must not claim the application is secure, signed, or
production-ready before evidence exists (16.5).

## Status: no scaffolding yet

There is no `package.json`, no source tree, and no dependencies — on purpose.

`docs/prd.md` section 18 lists React/Vite for the site and Tauri for the
desktop shell, but Tauri is marked **decision required**, not settled. Choosing
a shell now would commit the team to a packaging framework before one real
end-to-end path exists.

Scaffolding lands when the team approves the PRD baseline and the technology
choices.
