# Baton — volunteer app

Four screens for somebody standing outside a door, and a way in.

```bash
npm install
npm run dev          # http://localhost:5173, proxies /api to 127.0.0.1:8000
```

The API has to be running. From the repository root:

```bash
uvicorn api.main:app --port 8000
```

## Why it looks like this

Targets are 56px and body text is 18px. This is used one-handed, outdoors, sometimes in
the rain, by people who are not twenty-five. Neither number is negotiable to fit more on a
screen: if something did not fit, it was not important enough to be there.

Colours come from `design/tokens.css` in the repository root, imported directly rather than
copied. The palette was verified for contrast once and belongs in one file.

## The screens

| | |
|---|---|
| **V1 Today** | This volunteer's rounds, in the order they happen. Nothing about anybody else. |
| **V2 Brief** | What changed, what to watch for, how to be with them. Written by the model, cached per person per day, so only the first person through a door waits. |
| **V3 Record** | Speak, then correct. Chips carry the quote they came from; tap any that are wrong. |
| **V4 Open shifts** | One tap to fill a gap. The second person to tap is told plainly. |

## Language

Follows the volunteer, not the browser: the roster knows which language each person reads,
and phones get handed around. Stored data stays language-neutral; only these strings and
the model's prose have a language at all.

## Speech

`src/lib/dictation.ts` uses the browser's own speech recognition, so no audio is uploaded
by Baton. In Chrome the recognition itself is a Google service, which is a real
consideration for health notes; the module is a seam so that swapping it for Amazon
Transcribe changes one file.
