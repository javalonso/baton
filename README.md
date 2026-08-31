# Relevo

**An AI agent that carries the memory of a community care network.**

Built with the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) for the
[Agents for Humans Hackathon](https://agentsforhumans.devpost.com/) — *Good Neighbor Agents* track.

> ⚠️ **Not a medical device.** Relevo never diagnoses. It notices that a person's routine has
> changed and tells a human coordinator so a professional can decide. All data in this repository
> is synthetic. This is a hackathon prototype and is not HIPAA-compliant.

---

## The problem

A day center, a parish, or a neighborhood care network looks after dozens of older adults with
rotating volunteers. Everything anyone knows about each person — what upset their stomach, how
they slept, why a medication was stopped, what calms them down — lives in one caregiver's head.
When that person gets sick, travels, or hands off a shift, the knowledge is gone.

Two documented consequences:

- **76%** of family caregivers report no consistent help from others; more than 40% are the only
  caregiver, working 20 hours a week against 10 for those who share the load.
- Roughly **one third** of older adults with a urinary tract infection develop delirium. The first
  sign is a sudden change in behavior, not pain — and it is reversible if caught early. Dehydration
  and infection send more older people to the hospital than falls do.

Neither problem is a reminder problem. Both are memory and attention problems, and they scale with
the number of people the organization serves.

## What Relevo does

Five repetitive jobs, absorbed by an agent that runs in the background and only interrupts a human
when there is a real decision to make:

1. **Voice intake.** A volunteer sends a 20–60 second audio note when the visit ends. The agent
   transcribes it, extracts structured events (food, sleep, mood, medication, incidents, pending
   tasks) and updates a living record. No forms.
2. **One-page handoff sheet.** A PDF for the next shift or for the emergency room: diagnoses,
   current medications, allergies, what calms this person, how they communicate, contacts, and who
   decides.
3. **Change detection, not threshold alerts.** A daily pass compares each person against their own
   baseline and escalates when the pattern breaks — with a concrete suggested action, never a
   diagnosis.
4. **Shift coverage.** Detects unlogged visits and gaps in the roster and asks the group for a
   replacement, escalating to the coordinator only on a real conflict.
5. **Weekly report.** Who is at risk, which volunteers are carrying too much, which prescriptions
   are due for renewal.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) *(diagram in progress)*.

```
relevo/
├── core/     # domain models, repositories (DynamoDB / S3), business logic. No HTTP.
├── api/      # FastAPI  →  AWS Lambda + API Gateway. The only surface clients touch.
├── agents/   # Strands agents  →  Amazon Bedrock AgentCore Runtime.
├── infra/    # infrastructure as code
├── docs/     # architecture, data model, decisions
└── tests/
```

The agents' tools call `core/` directly rather than going back through the API, which keeps the
dependency graph acyclic. The API invokes agents on demand; **Amazon EventBridge Scheduler**
invokes the background pass on a daily cadence.

### AWS services

| Service | Role |
|---|---|
| Amazon Bedrock | Claude Haiku 4.5 for intake, Claude Opus 5 for reasoning |
| Bedrock AgentCore Runtime | Serverless agent hosting |
| Bedrock AgentCore Memory | Per-person behavioral baseline |
| Amazon Transcribe | Speech to text |
| Amazon DynamoDB | Records and events |
| Amazon S3 | Audio and generated PDFs |
| AWS Lambda + API Gateway | The API |
| Amazon EventBridge Scheduler | The daily background pass |

## Bilingual by design

Spanish and English. Data is stored language-neutral plus the `source_lang` of the original audio —
a caregiver may record in Spanish while the coordinator reads the portal in English. The locale is
resolved at the edge (`Accept-Language` or `?lang=`), never in the data layer.

## Running it

*In progress.*

## Use of AI assistants

This project was built with the help of Claude, in line with the hackathon rules. No pre-existing
code was incorporated.

## License

MIT — see [LICENSE](LICENSE).
