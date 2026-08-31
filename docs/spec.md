# Baton — Product Spec

Status: draft, F1. This document drives both the design system and the code. If something is not
here, it is not in the 5-minute demo.

---

## 1. The organization

**Red Vecinal San Miguel** — a neighborhood volunteer care network in a mid-size Latin American
city. Not a company, not a clinic. A WhatsApp group that grew up.

| | |
|---|---|
| Older adults served | 24 |
| Active volunteers | 14 |
| Visits per week | ~95 |
| Paid staff | 1 part-time coordinator |
| Budget | Donations and a municipal grant |

This is the unit Baton serves. Every feature has to get better as these numbers grow — that is what
separates a Good Neighbor agent from a personal assistant.

### Personas

**Lucía Ramos, 54 — coordinator.** The only paid person, 20 hours a week. Runs the network from a
laptop at home and her phone everywhere else. She is the single point of failure: everything the
network knows lives in her head and in three notebooks. She is the human Baton escalates to, and the
only human who can approve an action.

**Marco Delgado, 26 — volunteer.** Two visits a week, on his way home from work. He has met four of
the 24 older adults. He does not know that Doña Carmen gets confused when she is dehydrated, or that
Don Rafael will say he ate when he did not. Today he learns that by accident, or not at all.

**Carmen Ibarra, 82 — the person being cared for.** Lives alone. Sharp, proud, hard of hearing on
the left. Takes losartan and metformin. Hates being treated like a child — which is why Baton never
speaks to her, only about her, and only to the people already caring for her.

---

## 2. Screens

Two clients, one API. Both are the same PWA with different roles.

### Volunteer app (mobile)

| ID | Screen | Purpose |
|---|---|---|
| V1 | **Today** | The visits assigned to me today. Card per person: name, photo, time, address, one-line status. |
| V2 | **Pre-visit brief** | The thing that does not exist today. Before knocking: what changed since the last visit, what to watch for, what calms this person, how to communicate. Generated, not written. |
| V3 | **Record** | One large button. Record 20–60s, stop, and the agent shows what it understood as a short list of chips the volunteer can tap to correct. Confirm. Never a form. |
| V4 | **Open shifts** | Gaps the agent needs covered. One tap to claim. |

### Coordinator portal (desktop)

| ID | Screen | Purpose |
|---|---|---|
| C1 | **Today** | People at risk, coverage gaps, unacknowledged alerts. The screen the video opens on. |
| C2 | **Alert detail** | Baseline vs. the last three days, the quotes that triggered it, a suggested action, and three buttons: acknowledge, dismiss, escalate. |
| C3 | **Person record** | Living record: timeline, current medications, baseline, contacts, and the button that generates the handoff sheet. |
| C4 | **Coverage** | Roster grid and load per volunteer. Makes the imbalance visible with numbers. |
| C5 | **Weekly report** | What the agent sends every Monday without being asked. |

### Design constraints

- Minimum tap target 56px. Volunteers use this standing up, one-handed, outdoors.
- One primary action per screen in the volunteer app. Never two competing buttons.
- No form fields in the capture flow. Correction is by tapping chips, not typing.
- High contrast throughout. Some volunteers are themselves over 60.
- Every alert states a suggested action. An alert without an action is noise.

---

## 3. Data model

Language-neutral storage. `source_lang` records the language the audio was spoken in; the display
locale is resolved at the edge.

```
Organization  id, name, timezone, locale_default
Elder         id, org_id, name, photo_url, dob, address, contacts[],
              conditions[], allergies[], communication_notes, decision_maker
Volunteer     id, org_id, name, phone, locale, active
Shift         id, org_id, elder_id, volunteer_id, scheduled_at, status
Visit         id, shift_id, elder_id, volunteer_id, started_at,
              audio_key, transcript, source_lang
Observation   id, visit_id, elder_id, category, value, confidence, quote
Baseline      elder_id, window_days, metrics{}, updated_at
Alert         id, elder_id, kind, severity, opened_at, evidence[],
              suggested_action, status, acknowledged_by
Medication    id, elder_id, name, dose, schedule, prescribed_at, refill_due
HandoffSheet  id, elder_id, generated_at, pdf_key
```

**Observation categories** — the closed vocabulary the intake agent extracts into. A closed
vocabulary is what makes change detection possible; free text is not comparable across days.

`food` · `fluids` · `sleep` · `mood` · `orientation` · `mobility` · `medication` · `pain` ·
`skin` · `social` · `household` · `incident` · `task`

Every observation carries the verbatim `quote` from the transcript that produced it. Nothing is
asserted without a source the coordinator can read.

---

## 4. Agents

Four Strands agents over shared tools in `core/`.

| Agent | Model | Trigger | Job |
|---|---|---|---|
| **Intake** | Claude Haiku 4.5 | Volunteer submits audio | Transcript to observations. Mechanical extraction, high volume, cheap. |
| **Watch** | Claude Opus 5 | EventBridge, daily 06:00 local | Compare each person against their own baseline. Open alerts. This is the background job the hackathon theme asks for. |
| **Roster** | Claude Haiku 4.5 | EventBridge, daily 20:00 local | Unlogged visits and coverage gaps. Ask the group before asking the coordinator. |
| **Brief** | Claude Opus 5 | On demand | Pre-visit brief (V2) and the one-page handoff PDF. |

### Change detection, not thresholds

Baton does not alert on "drank fewer than 6 glasses." It alerts when a person stops being like
themselves. The baseline is per person, over a 21-day rolling window. An alert opens when two or
more categories deviate for two or more consecutive days.

### Escalation rules

| Situation | Baton does |
|---|---|
| Single off day | Nothing. Records it. |
| Pattern break, 2+ days | Opens an alert on C1. No notification. |
| Pattern break including `orientation` | Alert marked urgent. Pushes to the coordinator. |
| Reported fall, bleeding, chest pain | Immediate escalation. Bypasses everything. |
| Unlogged visit | Messages the volunteer. Coordinator sees nothing. |
| Unlogged visit, second day | Opens a coverage gap on V4 for the group to claim. |
| Gap unclaimed 12h before the shift | Escalates to the coordinator. |
| Prescription refill due within 7 days | Adds it to the weekly report. Never an alert. |

The rule underneath all of it: **interrupt a human only when a human has to decide.**

### What Baton never does

Never diagnoses. Never contacts the older adult directly. Never contacts family without the
coordinator. Never resolves its own alerts. Suggested actions are phrased as an observation plus a
recommendation to consult, never as a finding.

> Correct: "Carmen has been off her pattern for 3 days: less fluid intake and more confusion. In
> older adults this often precedes a urinary infection or dehydration. Worth having someone assess
> her."
>
> Wrong: "Carmen has a urinary tract infection."

---

## 5. Seed dataset

Synthetic, generated once, committed to the repo so the demo is reproducible.

- 24 older adults, 14 volunteers, 6 weeks of visit history (~570 visits)
- Realistic noise: missed visits, terse audio notes, two volunteers who over-report
- Mixed languages: roughly 30% of notes recorded in English to exercise the bilingual path

**Three planted cases**, each carrying a different part of the demo:

1. **Carmen Ibarra** — fluid intake drops and orientation degrades over 3 days. The urgent alert,
   and the hero of the video.
2. **Rafael Ortiz** — sleep and mood drift over 8 days without either crossing a threshold. Only a
   per-person baseline catches this. Proves the change-not-threshold claim.
3. **Volunteer imbalance** — one volunteer is carrying 31% of all visits while four have not logged
   one in two weeks. Surfaced by the weekly report, not by anyone complaining.

---

## 6. Demo video — 5 minutes

Written before the code. If a feature does not appear here, it does not get built first.

| Time | Beat |
|---|---|
| 0:00–0:25 | **The problem, out loud.** Lucía on camera: 24 people, 14 volunteers, everything in one head and three notebooks. "If I get sick, this network stops knowing things." |
| 0:25–0:50 | **What Baton is.** One sentence. Coordinator dashboard C1 on screen: 24 people, 14 volunteers, 2 alerts. Establishes the organization scale immediately. |
| 0:50–1:40 | **Capture.** Marco finishes a visit, taps record, speaks for 25 seconds in Spanish. The chips appear. He corrects one, confirms. Under 40 seconds of his life. |
| 1:40–2:40 | **The background pass.** Cut to the next morning. Nobody opened the app. The Watch agent ran on schedule. AgentCore observability trace on screen showing the reasoning. Then the alert on C1: Carmen, 3 days off pattern, suggested action. |
| 2:40–3:20 | **The handoff sheet.** Lucía taps generate. One-page PDF. Cut to the emergency room: a nurse reading it instead of asking an 82-year-old to recall her own medication list. |
| 3:20–4:00 | **It scales.** C4 coverage grid, the load imbalance, and the weekly report the agent sent without being asked. This is the beat that proves the category. |
| 4:00–4:35 | **Architecture.** Diagram. Strands multi-agent, AgentCore Runtime and Memory, EventBridge, Bedrock. 30 seconds, no more. |
| 4:35–5:00 | **Impact and honesty.** 63M family caregivers. About $4 per person per month. Then, on screen: not a medical device, synthetic data, decision support for a human. |

Narration in English. The app is shown in both Spanish and English to demonstrate the bilingual
product.

---

## 7. Out of scope

Named here so scope creep has to argue with a document.

- Native mobile apps. The PWA is the deliverable.
- Real WhatsApp integration. Meta onboarding will not clear before the deadline.
- Financial fraud detection. Mature competitors exist; this is a v3 partnership, not a feature.
- Medication reminders. A saturated category, and not the problem Baton solves.
- Multi-organization tenancy. One organization, modeled correctly, is enough.
