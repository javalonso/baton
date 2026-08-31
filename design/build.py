"""Generate standalone preview pages for the Baton design system.

Each preview inlines tokens.css so it renders correctly on its own, which is what the
design-system viewer expects. Run: python design/build.py
"""

from pathlib import Path

ROOT = Path(__file__).parent
TOKENS = (ROOT / "tokens.css").read_text(encoding="utf-8")
OUT = ROOT / "preview"

BASE = """
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: var(--space-8);
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: var(--size-md);
  line-height: var(--leading-body);
  -webkit-font-smoothing: antialiased;
}
h1 { font-size: var(--size-xl); line-height: var(--leading-tight); margin: 0 0 var(--space-2); }
.hint { color: var(--text-muted); font-size: var(--size-sm); margin: 0 0 var(--space-6); max-width: 62ch; }
.row { display: flex; flex-wrap: wrap; gap: var(--space-6); align-items: flex-start; }
.stack { display: flex; flex-direction: column; gap: var(--space-4); }
.label { font-size: var(--size-xs); color: var(--text-muted); text-transform: uppercase;
         letter-spacing: 0.06em; margin-bottom: var(--space-2); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg);
        box-shadow: var(--shadow-card); padding: var(--space-4); }
"""


def page(title: str, group: str, subtitle: str, body: str, extra_css: str = "") -> str:
    return f"""<!-- @dsCard group="{group}" -->
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Baton — {title}</title>
<style>
{TOKENS}
{BASE}
{extra_css}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="hint">{subtitle}</p>
{body}
</body>
</html>
"""


# --- 00 foundations ---------------------------------------------------------

SWATCHES = [
    ("Surface", "--surface", "--text", "17.7:1"),
    ("Background", "--bg", "--text", "16.5:1"),
    ("Sage", "--sage", "--on-sage", "6.3:1"),
    ("Amber fill", "--amber-fill", "--text", "8.6:1"),
    ("Urgent", "--urgent", "--on-urgent", "7.5:1"),
    ("Sage soft", "--sage-soft", "--text", "—"),
    ("Amber soft", "--amber-soft", "--text", "—"),
    ("Urgent soft", "--urgent-soft", "--text", "—"),
]

swatch_html = "".join(
    f"""<div class="swatch" style="background: var({bg}); color: var({fg});">
  <span class="sw-name">{name}</span><span class="sw-ratio">{ratio}</span></div>"""
    for name, bg, fg, ratio in SWATCHES
)

type_rows = "".join(
    f"""<div class="type-row"><span class="type-meta">{label}</span>
    <span style="font-size: var({tok});">Carmen has been off her pattern for 3 days</span></div>"""
    for label, tok in [
        ("2xl / 28", "--size-2xl"),
        ("xl / 22", "--size-xl"),
        ("lg / 18 — field floor", "--size-lg"),
        ("md / 17", "--size-md"),
        ("sm / 15", "--size-sm"),
        ("xs / 13", "--size-xs"),
    ]
)

target_html = """
<div class="row" style="align-items: flex-end;">
  <div><div class="label">Field · 56px</div>
    <div class="target" style="width: var(--target-field); height: var(--target-field);"></div></div>
  <div><div class="label">Portal · 44px</div>
    <div class="target" style="width: var(--target-portal); height: var(--target-portal);"></div></div>
  <div><div class="label">WCAG 2.2 floor · 24px</div>
    <div class="target" style="width: 24px; height: 24px;"></div></div>
</div>
"""

foundations = page(
    "Foundations",
    "Foundations",
    "Sage base, amber for attention, red reserved for urgency. Contrast ratios are measured, not "
    "estimated. Tap targets sit deliberately above the WCAG 2.2 floor because volunteers use the "
    "field app one-handed, outdoors, and many are over 60.",
    f"""
<div class="label">Color</div>
<div class="swatches">{swatch_html}</div>
<div class="label" style="margin-top: var(--space-8);">Type scale</div>
<div class="card">{type_rows}</div>
<div class="label" style="margin-top: var(--space-8);">Tap targets</div>
{target_html}
""",
    """
.swatches { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: var(--space-3); }
.swatch { border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-4);
          min-height: 92px; display: flex; flex-direction: column; justify-content: space-between; }
.sw-name { font-size: var(--size-sm); font-weight: 600; }
.sw-ratio { font-family: var(--font-mono); font-size: var(--size-xs); opacity: 0.85; }
.type-row { display: flex; align-items: baseline; gap: var(--space-4); padding: var(--space-2) 0;
            border-bottom: 1px solid var(--border); }
.type-row:last-child { border-bottom: 0; }
.type-meta { font-family: var(--font-mono); font-size: var(--size-xs); color: var(--text-muted);
             width: 14ch; flex: none; }
.target { background: var(--sage-soft); border: 2px solid var(--sage); border-radius: var(--radius-sm); }
""",
)


# --- 01 record button -------------------------------------------------------

record = page(
    "Record button",
    "Components",
    "The single gesture the whole product rests on. One primary action, 96px, reachable with a "
    "thumb. The recording state shows real elapsed time, and the processing state describes what "
    "the agent is actually doing — never a spinner on a fixed timer.",
    """
<div class="row">
  <div><div class="label">Idle</div>
    <button class="rec">
      <span class="dot"></span>
      <span class="rec-label">Record visit note</span>
    </button></div>

  <div><div class="label">Recording</div>
    <button class="rec is-live">
      <span class="bars"><i></i><i></i><i></i><i></i><i></i></span>
      <span class="rec-label">0:24 — tap to stop</span>
    </button></div>

  <div><div class="label">Processing</div>
    <button class="rec is-busy" disabled>
      <span class="spin"></span>
      <span class="rec-label">Listening to what you said…</span>
    </button></div>
</div>
""",
    """
.rec { display: flex; align-items: center; gap: var(--space-3); min-height: 96px;
       padding: 0 var(--space-8); border: 0; border-radius: var(--radius-pill);
       background: var(--sage); color: var(--on-sage); font-family: var(--font-sans);
       font-size: var(--size-lg); font-weight: 600; cursor: pointer;
       transition: background var(--dur) var(--ease); }
.rec:hover { background: var(--sage-hover); }
.rec:focus-visible { outline: 3px solid var(--text); outline-offset: 3px; }
.rec.is-live { background: var(--urgent); color: var(--on-urgent); }
.rec.is-busy { background: var(--surface-sunken); color: var(--text-muted);
               border: 2px solid var(--border-strong); cursor: default; }
.dot { width: 20px; height: 20px; border-radius: 50%; background: currentColor; flex: none; }
.bars { display: flex; align-items: center; gap: 3px; height: 24px; }
.bars i { width: 4px; border-radius: 2px; background: currentColor; animation: vu 900ms var(--ease) infinite alternate; }
.bars i:nth-child(1) { height: 10px; animation-delay: 0ms; }
.bars i:nth-child(2) { height: 20px; animation-delay: 120ms; }
.bars i:nth-child(3) { height: 14px; animation-delay: 240ms; }
.bars i:nth-child(4) { height: 22px; animation-delay: 360ms; }
.bars i:nth-child(5) { height: 12px; animation-delay: 480ms; }
@keyframes vu { to { transform: scaleY(0.45); } }
.spin { width: 20px; height: 20px; border-radius: 50%; border: 3px solid var(--border);
        border-top-color: var(--text-muted); animation: sp 900ms linear infinite; flex: none; }
@keyframes sp { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .bars i, .spin { animation: none; }
}
""",
)


# --- 02 observation chips ---------------------------------------------------

CHIPS = [
    ("Ate normally", "food", "sure"),
    ("Slept poorly", "sleep", "sure"),
    ("Seemed confused about the day", "orientation", "check"),
    ("Losartan — dose increased", "medication", "check"),
    ("Kitchen tap still dripping", "task", "sure"),
]

chip_html = "".join(
    f"""<button class="chip {'chip--check' if state == 'check' else ''}">
      <span class="chip-cat">{cat}</span>{text}
      {'<span class="chip-flag">worth confirming</span>' if state == 'check' else ''}
    </button>"""
    for text, cat, state in CHIPS
)

chips = page(
    "Observation chips",
    "Components",
    "The intent-preview pattern. After a voice note, the agent shows what it understood before "
    "anything is written. The volunteer taps to correct — never types. Anything the agent is less "
    "sure of is marked in words, not as a decimal.",
    f"""
<div class="card" style="max-width: 560px;">
  <p style="margin: 0 0 var(--space-4); font-size: var(--size-lg);">
    Here is what I heard. Tap anything that is wrong.
  </p>
  <div class="chips">{chip_html}</div>
  <div class="chip-actions">
    <button class="btn btn--primary">Confirm</button>
    <button class="btn btn--ghost">Record again</button>
  </div>
</div>
""",
    """
.chips { display: flex; flex-direction: column; gap: var(--space-2); }
.chip { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2);
        min-height: var(--target-field); width: 100%; text-align: left;
        padding: var(--space-3) var(--space-4); border-radius: var(--radius-md);
        border: 1px solid var(--border-strong); background: var(--surface);
        color: var(--text); font-family: var(--font-sans); font-size: var(--size-lg);
        cursor: pointer; transition: border-color var(--dur) var(--ease); }
.chip:hover { border-color: var(--sage); }
.chip:focus-visible { outline: 3px solid var(--text); outline-offset: 2px; }
.chip--check { background: var(--amber-soft); border-color: var(--amber); }
.chip-cat { font-family: var(--font-mono); font-size: var(--size-xs); color: var(--text-muted);
            border: 1px solid var(--border); border-radius: var(--radius-sm);
            padding: 2px 6px; flex: none; }
.chip-flag { font-size: var(--size-xs); color: var(--amber); font-weight: 600; margin-left: auto; }
.chip-actions { display: flex; gap: var(--space-3); margin-top: var(--space-6); }
.btn { min-height: var(--target-field); padding: 0 var(--space-6); border-radius: var(--radius-pill);
       font-family: var(--font-sans); font-size: var(--size-lg); font-weight: 600; cursor: pointer;
       border: 1px solid transparent; }
.btn--primary { background: var(--sage); color: var(--on-sage); }
.btn--primary:hover { background: var(--sage-hover); }
.btn--ghost { background: transparent; color: var(--text); border-color: var(--border-strong); }
.btn:focus-visible { outline: 3px solid var(--text); outline-offset: 3px; }
""",
)


# --- 03 person card ---------------------------------------------------------

person = page(
    "Person card",
    "Components",
    "The volunteer's Today list. Status is carried by a word and a shape, never by color alone. "
    "The same component in both product languages — content changes, structure does not.",
    """
<div class="row">
  <a class="person" href="#">
    <span class="avatar" aria-hidden="true">CI</span>
    <span class="person-main">
      <span class="person-name">Carmen Ibarra</span>
      <span class="person-meta">4:30 PM · Calle Morelos 118</span>
      <span class="status status--urgent"><span class="status-mark">!</span>Off pattern 3 days</span>
    </span>
  </a>

  <a class="person" href="#" lang="es">
    <span class="avatar" aria-hidden="true">RO</span>
    <span class="person-main">
      <span class="person-name">Rafael Ortiz</span>
      <span class="person-meta">6:00 PM · Av. Juárez 42</span>
      <span class="status status--calm"><span class="status-mark">✓</span>Todo en orden</span>
    </span>
  </a>
</div>
""",
    """
.person { display: flex; gap: var(--space-4); align-items: center; min-height: 96px; width: 320px;
          padding: var(--space-4); background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--radius-lg); box-shadow: var(--shadow-card);
          text-decoration: none; color: var(--text); }
.person:hover { border-color: var(--border-strong); }
.person:focus-visible { outline: 3px solid var(--text); outline-offset: 3px; }
.avatar { width: 56px; height: 56px; flex: none; border-radius: 50%; background: var(--sage-soft);
          color: var(--sage); display: grid; place-items: center; font-weight: 700;
          font-size: var(--size-md); }
.person-main { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.person-name { font-size: var(--size-lg); font-weight: 600; }
.person-meta { font-size: var(--size-sm); color: var(--text-muted); }
.status { display: inline-flex; align-items: center; gap: var(--space-2); margin-top: var(--space-2);
          font-size: var(--size-sm); font-weight: 600; }
.status-mark { width: 20px; height: 20px; flex: none; display: grid; place-items: center;
               border-radius: 50%; font-size: var(--size-xs); }
.status--urgent { color: var(--urgent); }
.status--urgent .status-mark { background: var(--urgent); color: var(--on-urgent); }
.status--calm { color: var(--text-muted); }
.status--calm .status-mark { background: var(--sage-soft); color: var(--sage); }
""",
)


# --- 04 alert card ----------------------------------------------------------

alert = page(
    "Alert card",
    "Components",
    "The component the product is judged on. It states the deviation, shows the volunteers' own "
    "words as evidence, and recommends consulting someone — it never names a condition. Every "
    "claim is one tap from its source.",
    """
<article class="alert">
  <header class="alert-head">
    <span class="pill pill--urgent">Needs a decision</span>
    <span class="alert-when">Opened today, 6:04 AM · by the daily check</span>
  </header>

  <h2 class="alert-title">Carmen Ibarra has been off her pattern for 3 days</h2>

  <div class="metrics">
    <div class="metric">
      <span class="metric-name">Fluids</span>
      <span class="metric-cmp"><b>Down</b> vs. her usual</span>
    </div>
    <div class="metric">
      <span class="metric-name">Orientation</span>
      <span class="metric-cmp"><b>Confused</b> 3 of 3 visits</span>
    </div>
  </div>

  <div class="label" style="margin-top: var(--space-6);">What volunteers said</div>
  <blockquote class="quote" lang="es">
    “No quiso el agua, dijo que ya había tomado.”
    <cite>Marco D. · yesterday, 5:12 PM</cite>
  </blockquote>
  <blockquote class="quote" lang="es">
    “Me preguntó dos veces qué día era.”
    <cite>Ana R. · 2 days ago, 11:40 AM</cite>
  </blockquote>

  <div class="suggest">
    In older adults this pattern often precedes a urinary infection or dehydration.
    <b>Worth having someone assess her.</b>
  </div>

  <div class="alert-actions">
    <button class="btn btn--primary">Acknowledge</button>
    <button class="btn btn--ghost">Assign a visit</button>
    <button class="btn btn--ghost">Dismiss</button>
  </div>
</article>
""",
    """
.alert { max-width: 620px; background: var(--surface); border: 1px solid var(--border);
         border-left: 4px solid var(--urgent); border-radius: var(--radius-lg);
         box-shadow: var(--shadow-card); padding: var(--space-6); }
.alert-head { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.pill { font-size: var(--size-xs); font-weight: 700; letter-spacing: 0.04em;
        text-transform: uppercase; padding: 4px 10px; border-radius: var(--radius-pill); }
.pill--urgent { background: var(--urgent); color: var(--on-urgent); }
.alert-when { font-size: var(--size-xs); color: var(--text-muted); }
.alert-title { font-size: var(--size-xl); line-height: var(--leading-tight);
               margin: var(--space-4) 0 var(--space-4); }
.metrics { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.metric { flex: 1 1 180px; background: var(--surface-sunken); border-radius: var(--radius-md);
          padding: var(--space-3) var(--space-4); }
.metric-name { display: block; font-size: var(--size-xs); color: var(--text-muted);
               text-transform: uppercase; letter-spacing: 0.06em; }
.metric-cmp { font-size: var(--size-md); }
.quote { margin: 0 0 var(--space-2); padding: var(--space-3) var(--space-4);
         background: var(--surface-sunken); border-radius: var(--radius-md);
         font-size: var(--size-md); }
.quote cite { display: block; margin-top: var(--space-2); font-style: normal;
              font-size: var(--size-xs); color: var(--text-muted); }
.suggest { margin-top: var(--space-6); padding: var(--space-4); background: var(--amber-soft);
           border-radius: var(--radius-md); font-size: var(--size-md); }
.alert-actions { display: flex; gap: var(--space-3); flex-wrap: wrap; margin-top: var(--space-6); }
.btn { min-height: var(--target-portal); padding: 0 var(--space-5, 1.25rem);
       border-radius: var(--radius-pill); font-family: var(--font-sans); font-size: var(--size-md);
       font-weight: 600; cursor: pointer; border: 1px solid transparent; }
.btn--primary { background: var(--sage); color: var(--on-sage); }
.btn--primary:hover { background: var(--sage-hover); }
.btn--ghost { background: transparent; color: var(--text); border-color: var(--border-strong); }
.btn:focus-visible { outline: 3px solid var(--text); outline-offset: 3px; }
""",
)


# --- 05 coverage row --------------------------------------------------------

ROWS = [
    ("Ana Ruiz", 29, "31% of all visits", "over"),
    ("Marco Delgado", 8, "steady", "ok"),
    ("Sofía Lara", 6, "steady", "ok"),
    ("Diego Peña", 0, "no visits logged in 2 weeks", "idle"),
]
MAXV = 29

row_html = "".join(
    f"""<tr>
      <th scope="row">{name}</th>
      <td class="bar-cell"><span class="bar bar--{state}" style="width: {round(v / MAXV * 100)}%"></span></td>
      <td class="count">{v}</td>
      <td class="note note--{state}">{note}</td>
    </tr>"""
    for name, v, note, state in ROWS
)

coverage = page(
    "Coverage row",
    "Components",
    "Load per volunteer over six weeks. The point of this screen is not scheduling — it is making "
    "an imbalance visible with numbers, so nobody has to be the one who complains.",
    f"""
<table class="coverage">
  <caption class="label">Visits logged · last 6 weeks</caption>
  <tbody>{row_html}</tbody>
</table>
""",
    """
.coverage { width: 100%; max-width: 660px; border-collapse: collapse; background: var(--surface);
            border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.coverage caption { text-align: left; padding: var(--space-4) var(--space-4) 0; }
.coverage th, .coverage td { padding: var(--space-3) var(--space-4); text-align: left;
                             border-bottom: 1px solid var(--border); font-weight: 400;
                             font-size: var(--size-md); }
.coverage tr:last-child th, .coverage tr:last-child td { border-bottom: 0; }
.coverage th { font-weight: 600; width: 30%; }
.bar-cell { width: 34%; }
.bar { display: block; height: 12px; border-radius: var(--radius-pill); background: var(--sage);
       min-width: 3px; }
.bar--over { background: var(--amber-fill); }
.bar--idle { background: var(--border-strong); }
.count { font-family: var(--font-mono); width: 8%; }
.note { font-size: var(--size-sm); color: var(--text-muted); }
.note--over { color: var(--amber); font-weight: 600; }
""",
)


PAGES = {
    "00-foundations.html": foundations,
    "01-record-button.html": record,
    "02-observation-chips.html": chips,
    "03-person-card.html": person,
    "04-alert-card.html": alert,
    "05-coverage-row.html": coverage,
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, html in PAGES.items():
        (OUT / name).write_text(html, encoding="utf-8")
        print(f"wrote preview/{name}")
