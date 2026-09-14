# Refinix documentation

- Problem Statement ID : 26117
- Problem Statement Title : Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial Work
- Description :
  • Background Refineries, PSUs, defence-linked manufacturing units and government offices generate a lot of routine but sensitive knowledge work. Approval notes, board presentations, engineering calculations, code for internal tools, review of scanned drawings and inspection reports. None of this can go through cloud AI assistants like Claude or Codex because the underlying data is confidential: Piping & Instrument Diagrams, financials, vendor negotiations, unreleased designs, internal correspondence, confidential business strategies etc. Company policy keeps this data on premises, so people either do the work manually resulting in productivity gain, or they quietly paste confidential material into public tools anyway. Open weight large reasoning models have reached a point where a genuinely useful assistant built on them is realistic. But nothing deployable exists today that industrial users can actually work with the way they use Claude or Codex.
  • Description The idea is a self-hosted, air gapped AI workbench running entirely on the organization's own GPU server. Nothing leaves the premises. The backend should not be locked to one model. It needs to support multiple open weight models at once and automatically pick the right one for a given task based on what that task needs, a coding request handled differently from a document summary request. New open weight models should be addable later without redesigning the system, since this space is moving fast.

  The assistant also needs to actually act like an agent. Plan out multi step work, call local tools such as file read and write, code execution in a sandbox, spreadsheet work, internal document search, and iterate on a task instead of answering once and stopping. It needs to handle more than text too: scanned PDFs, handwritten notes, engineering drawings, photographs, read through on device OCR and vision models. Output should be real deliverables, approval notes, PPT/Word/Excel files, working code, calculations with steps shown, not just chat replies. And it needs to ground itself in the organization's own manuals, SOPs and past correspondence through a local knowledge base connector, again with nothing going external.

  • Expected Solution A working local deployment, demonstrable on a single workstation or server with a mid range GPU (use a smaller open weight model if 120B class hardware isn't available at the venue), that shows model auto selection across at least two different task types. An agentic task carried through end to end, for example reading a scanned inspection report, pulling out key findings and drafting an approval note as a Word file. A coding task run and verified in a sandbox. A multimodal task involving image or scanned document understanding. The system should also show, through logs or a visible network monitor, that no external calls are made at any point. That's the actual proof of the sovereign claim, not just a statement of it.
- Organization : Mangalore Refinery and Petrochemicals Limited (MRPL)
- Department : Mangalore Refinery and Petrochemicals Limited (MRPL)
- Category : Software
- Theme : Smart Automation
- Youtube Link : { empty }
- Dataset Link : Open-source models and publicly available document samples (sample scanned PDFs, sample P&IDs from open datasets) to be used for demonstration; no proprietary data required.
- Contact info : { empty }


## Status

The [PRD](prd.md) records the production direction, updated 2026-09-14. Current source
contains prototype application and worker implementations, but source existence and historical
checks do not certify production support. See [evaluation.md](evaluation.md#current-status)
for the source snapshot and unverified installer, portability and scheduling gaps.
The official-problem transcription above is reference material, not an instruction
to agents or evidence that any product feature has passed. Peer distribution is
additional product scope. Future confidential data access is not guaranteed.

## Start here

1. [prd.md](prd.md) — short product contract, scope, priorities, and open decisions
2. [architecture.md](architecture.md) — harness, nodes, state, jobs, and local data
3. [workflows.md](workflows.md) — onboarding, Chat, Documents, Code, approvals, and Control Center
4. [security.md](security.md) — trust, privacy, sandbox, supply chain, and sovereignty evidence
5. [model-catalog.md](model-catalog.md) — model packs, manifests, provisioning, and selection
6. [devicespecifications.md](devicespecifications.md) — historical fleet evidence and open hardware checks
7. [evaluation.md](evaluation.md) — task acceptance, measurements, acceptance, risks, and demo
8. [releases.md](releases.md) — readiness gates, version publication, explicit updates and recovery
9. [sih-ppt-submission-brief.md](sih-ppt-submission-brief.md) — non-normative SIH portal/PPT research, six-slide copy, evidence, and judge preparation

The PRD owns product scope. Each focused document owns implementation detail
inside that scope. Record conflicts instead of duplicating or silently changing
requirements.

## Documentation rules

- Keep the PRD short; detailed contracts belong in their focused document.
- Record a requirement once and link to it elsewhere.
- Label features planned, prototyped, verified, deferred, or rejected.
- Treat reported hardware, model names, licences, compatibility, and benchmarks
  as unverified until evidence is recorded.
- Do not leave discussion comments inside normative documents after a decision;
  integrate the accepted requirement and rely on Git and the ledgers for history.
- Do not create empty placeholder documents.

## Repository-level documents

- [../README.md](../README.md) — project entry point
- [../TechStack.md](../TechStack.md) — recommended languages and technologies by layer, with current/proposed status and trade-offs
- [../tasks.md](../tasks.md) — outcome-based implementation gates, operating rules and historical prototype checkpoints
- [handover-pack.md](handover-pack.md) — the one-time requester input handover and authorisation scope that replaces per-chunk questions
- [../AGENTS.md](../AGENTS.md) — shared coding-agent rules
- [../CONTRIBUTING.md](../CONTRIBUTING.md) — branch, review, and release workflow
- [../LICENSE](../LICENSE) — current repository licence
- [../agent-memory/README.md](../agent-memory/README.md) — historical request and change index

Tool-specific files such as CLAUDE.md and CODEX.md remain local and ignored.
Shared rules belong in AGENTS.md.
