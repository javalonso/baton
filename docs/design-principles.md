# Baton — Design Principles

The rules the design system is built on. Derived from 2026 practice, then narrowed to this product
and its two very different users: a volunteer standing on a doorstep, and a coordinator at a laptop.

---

## 1. Calm over capable

2026 practice has converged on calm interfaces: less visual clutter, fewer decisions per session,
generous white space, obvious defaults, and micro-interactions instead of gamification. Attention is
fragmented and users are overstimulated; an interface that demands attention loses.

For Baton this is not a style choice, it is the product. The escalation rules in
[`spec.md`](spec.md) are the same principle expressed as engineering: **interrupt a human only when a
human has to decide.** The interface must not undo in pixels what the agent policy achieves in logic.

**Rules**
- One primary action per screen in the volunteer app.
- A screen may show at most one alert at full weight. The rest collapse into a count.
- Nothing blinks, pulses, or badges unless a human has to act on it now.
- Empty states are a success condition, not a gap to fill. "Nothing needs you today" is a valid screen.

## 2. Transparent AI, or no AI

Users in 2026 are less impressed by what an agent can do than concerned with understanding how it
works. Hidden logic reads as evasive, not advanced. Interfaces are expected to reveal why a
suggestion appeared, how confident the system is, and how to override it.

Baton has an advantage here that most products do not: **every observation already carries the
verbatim quote that produced it.** Explainability is in the data model, not bolted on. The interface
only has to surface what is already there.

**Rules**
- Every agent-produced statement is one tap from its evidence.
- Confidence is shown when it is below certain, never as a decimal. "Heard clearly" / "Worth
  confirming" — words, not 0.72.
- Every agent action is reversible or acknowledgeable by a human. The agent never closes its own alert.
- Disclose the agent. The EU AI Act's Article 50 transparency obligations apply from 2 August 2026;
  people must be told when they are interacting with an AI system. Baton states it in plain language
  on first run and in the handoff sheet footer.

## 3. Accessibility is infrastructure

Not a compliance pass at the end. WCAG 2.2 AA is the floor, and this product's population sits well
below the average in vision, dexterity, and lighting conditions — volunteers are often over 60
themselves, working one-handed, outdoors, in a hurry.

**Floor — non-negotiable**

| | Standard | Baton |
|---|---|---|
| Text contrast | 4.5:1 normal, 3:1 large (WCAG AA) | 4.5:1 minimum everywhere, including large text |
| Tap targets | 24×24 CSS px (WCAG 2.2), 44pt iOS, 48dp Android | **56px** in the volunteer app, 44px in the portal |
| Body text | 16px minimum | 18px in the volunteer app |
| Motion | Respect `prefers-reduced-motion` | Required, and no motion carries meaning on its own |
| Input | Keyboard navigable, screen-reader labelled | Required on both clients |

**Rules**
- Never encode meaning in color alone. Every status has a shape or a word beside it.
- Never require typing in the field. Voice in, taps to correct.
- Test in sunlight. Literally — the capture screen is used outdoors.

## 4. Motion is structural, not decorative

Motion in 2026 explains process rather than performing. Over-animated interfaces read as aggressive.
Progress indicators clarify what the system is doing; they do not entertain.

**Rules**
- Motion is allowed for three things only: state transitions, progress of a real process, and
  drawing the eye to something that just changed.
- Durations come from tokens, not from per-component values.
- The agent thinking is a real process and should be shown honestly — not a fake spinner with a
  fixed timer.

## 5. One system, two postures

The volunteer app and the coordinator portal share tokens, type scale, and components. They differ
in density, not in language. A volunteer sees one thing at a time and taps; a coordinator sees
twenty-four people and scans.

---

## Agentic UX patterns, mapped to Baton

2026 agentic practice has settled on a small set of patterns. Baton implements four of the six and
deliberately skips two.

| Pattern | Where it lives in Baton |
|---|---|
| **Intent preview** — show what will happen before it happens | **V3.** After recording, the agent shows the observations it extracted as chips. The volunteer confirms or corrects before anything is written. |
| **Explainable rationale** — answer "why?" without being asked | **C2.** The alert shows the baseline, the deviation, and the verbatim quotes from the voice notes that triggered it. |
| **Action audit** — a chronological log of what the agent did | **C3.** The person timeline is the audit log. Every entry names its source visit and volunteer. |
| **Graceful escalation** — stop and ask on ambiguous or high-consequence decisions | The escalation table in `spec.md`. Industry guidance targets escalating 5–15% of tasks; Baton's rules should be tuned to land in that band — under it and the agent is reckless, over it and it is a notification app. |
| **Autonomy dial** — user-adjustable autonomy per task type | **Skipped.** With one coordinator and a fixed policy, a settings surface adds configuration without adding control. |
| **Adaptive interface** — layout shifts with task shape | **Skipped.** Two fixed postures serve this product better than an interface that moves under the user. |

### Failure modes to design against

Documented ways agentic products lose trust, each with the countermeasure Baton already has:

| Failure | Countermeasure |
|---|---|
| Acting without warning | Nothing is written from a voice note until the volunteer confirms the chips. |
| Invisible decisions | The timeline and the evidence quotes. |
| Confidently wrong | Confidence is surfaced, and the human acknowledges every alert. |
| Over-escalation | The escalation table exists precisely to keep the interrupt rate low. |
| Personalization breaking familiarity | The layout never changes shape. Content changes; structure does not. |

---

## What we deliberately avoid

Practices that read as dated in 2026, and two specific to how this project is being built:

- **Glassmorphism, heavy depth effects, skeuomorphism.** Theatrical, and they wreck contrast.
- **Vibrant accent colors and oversized type used as personality.** Personality comes from
  restraint and from the words.
- **Purple gradients on white or dark.** The single most recognizable "AI product" cliché.
- **The generative-model house style.** Current models default to warm cream backgrounds (around
  `#F4F1EA`), serif display type, italic accents, and a terracotta accent. It is a good look for an
  editorial site and wrong for a care operations tool. The palette below is specified explicitly to
  prevent drifting into it.
- **Generic system fonts as a default** (Inter, Roboto, Arial). A deliberate choice, or nothing.

---

## Direction, not yet tokens

The token set is defined in the design system project, not here. The direction it has to satisfy:

- **Legible before beautiful.** Every color decision is checked against 4.5:1 before it is checked
  against taste.
- **Quiet base, loud only for urgency.** Most of the interface is neutral. Saturation is a scarce
  resource spent on exactly one thing: something a human must look at now.
- **Warm, not clinical.** This is a neighborhood network, not a hospital. It should not look like an
  EMR, and it should not look like a startup dashboard either.
- **A type scale that survives 18px body text** without the layout collapsing.
