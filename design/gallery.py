"""Build a single-page gallery of the Baton design system.

Each component is embedded in a same-origin `srcdoc` iframe so its CSS stays isolated,
auto-sized on load, and re-rendered when the theme is switched.

Usage: python design/gallery.py [output.html]
Emits body-level markup only (no doctype/html/head/body), ready to publish as an artifact.
"""

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
PREVIEW = ROOT / "preview"

COMPONENTS = [
    (
        "00-foundations.html",
        "Foundations",
        "Color, type scale and tap targets. Every contrast ratio on this page was measured, "
        "not estimated — check them.",
        520,
    ),
    (
        "01-record-button.html",
        "Record button",
        "The one gesture the product rests on. 96px tall, thumb-reachable. The processing state "
        "names what the agent is doing instead of spinning on a timer.",
        320,
    ),
    (
        "02-observation-chips.html",
        "Observation chips",
        "Intent preview: the agent shows what it understood before anything is written. Lower "
        "confidence is stated in words, never as a decimal.",
        560,
    ),
    (
        "03-person-card.html",
        "Person card",
        "The volunteer's list. Shown in both product languages — status always carries a word and "
        "a shape, never color alone.",
        300,
    ),
    (
        "04-alert-card.html",
        "Alert card",
        "The component the product is judged on. Deviation, the volunteers' own words as evidence, "
        "and a recommendation to have someone assess her. It never names a condition.",
        740,
    ),
    (
        "05-coverage-row.html",
        "Coverage row",
        "Load per volunteer over six weeks. Makes an imbalance visible in numbers so nobody has to "
        "be the one who complains.",
        340,
    ),
]

STYLE = """
<style>
  :root {
    --g-bg: #F6F8F5;
    --g-surface: #FFFFFF;
    --g-sunken: #EEF2EC;
    --g-border: #D9E0D8;
    --g-border-strong: #7F8C82;
    --g-text: #141A16;
    --g-muted: #4C5A51;
    --g-sage: #2F6B4F;
    --g-sage-soft: #E3EDE6;
    --g-amber: #8A5A05;
    --g-font: ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif;
    --g-mono: ui-monospace, "SF Mono", Menlo, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --g-bg: #0E1210;
      --g-surface: #171C19;
      --g-sunken: #0A0D0B;
      --g-border: #2A322C;
      --g-border-strong: #74837A;
      --g-text: #E9EFE9;
      --g-muted: #A3B0A6;
      --g-sage: #7CC49A;
      --g-sage-soft: #1E2C24;
      --g-amber: #F0B25C;
    }
  }
  :root[data-theme="dark"] {
    --g-bg: #0E1210;
    --g-surface: #171C19;
    --g-sunken: #0A0D0B;
    --g-border: #2A322C;
    --g-border-strong: #74837A;
    --g-text: #E9EFE9;
    --g-muted: #A3B0A6;
    --g-sage: #7CC49A;
    --g-sage-soft: #1E2C24;
    --g-amber: #F0B25C;
  }

  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--g-bg);
    color: var(--g-text);
    font-family: var(--g-font);
    font-size: 17px;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 56px 24px 96px; }

  header.masthead {
    display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-end;
    justify-content: space-between;
    padding-bottom: 24px; border-bottom: 1px solid var(--g-border); margin-bottom: 8px;
  }
  .brand { display: flex; flex-direction: column; gap: 6px; }
  .kicker {
    font-family: var(--g-mono); font-size: 12px; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--g-muted);
  }
  h1 { font-size: 34px; line-height: 1.15; margin: 0; text-wrap: balance; letter-spacing: -0.015em; }
  .lede { max-width: 60ch; color: var(--g-muted); margin: 4px 0 0; font-size: 17px; }

  .toggle {
    display: inline-flex; align-items: center; gap: 8px; min-height: 44px;
    padding: 0 18px; border-radius: 999px; cursor: pointer;
    background: transparent; color: var(--g-text);
    border: 1px solid var(--g-border-strong);
    font-family: var(--g-font); font-size: 15px; font-weight: 600;
  }
  .toggle:hover { border-color: var(--g-sage); }
  .toggle:focus-visible { outline: 3px solid var(--g-text); outline-offset: 3px; }

  .facts { display: flex; flex-wrap: wrap; gap: 8px; margin: 28px 0 48px; }
  .fact {
    font-family: var(--g-mono); font-size: 12.5px; color: var(--g-muted);
    background: var(--g-sunken); border: 1px solid var(--g-border);
    border-radius: 8px; padding: 6px 10px;
  }
  .fact b { color: var(--g-text); font-weight: 600; }

  .items { display: flex; flex-direction: column; gap: 56px; }
  .item { display: flex; flex-direction: column; gap: 14px; }
  .item-head { display: flex; flex-direction: column; gap: 6px; }
  .item-name {
    display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
    font-size: 22px; font-weight: 650; letter-spacing: -0.01em;
  }
  .item-file { font-family: var(--g-mono); font-size: 12px; color: var(--g-muted); font-weight: 400; }
  .item-note { margin: 0; color: var(--g-muted); max-width: 68ch; font-size: 16px; }

  .frame {
    border: 1px solid var(--g-border); border-radius: 14px; overflow: hidden;
    background: var(--g-surface);
  }
  .frame iframe { display: block; width: 100%; border: 0; background: transparent; }

  footer.foot {
    margin-top: 72px; padding-top: 24px; border-top: 1px solid var(--g-border);
    color: var(--g-muted); font-size: 15px; display: flex; flex-wrap: wrap; gap: 8px 24px;
  }
  footer.foot a { color: var(--g-sage); }

  @media (max-width: 620px) {
    .wrap { padding: 32px 16px 64px; }
    h1 { font-size: 27px; }
  }
  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
  }
</style>
"""


def build() -> str:
    items, sources = [], []
    for idx, (fname, name, note, height) in enumerate(COMPONENTS):
        html = (PREVIEW / fname).read_text(encoding="utf-8")
        sources.append(html)
        items.append(
            f"""    <section class="item">
      <div class="item-head">
        <div class="item-name">{escape(name)} <span class="item-file">{escape(fname)}</span></div>
        <p class="item-note">{escape(note)}</p>
      </div>
      <div class="frame">
        <iframe title="{escape(name)}" data-idx="{idx}" height="{height}"
                sandbox="allow-same-origin" srcdoc="{escape(html, quote=True)}"></iframe>
      </div>
    </section>"""
        )

    script_sources = ",\n".join(
        "    " + repr(s).replace("\\n", "\\n") if False else "    " + _js_string(s)
        for s in sources
    )

    return f"""{STYLE}
<div class="wrap">
  <header class="masthead">
    <div class="brand">
      <span class="kicker">Baton · design system</span>
      <h1>Six components, one set of tokens</h1>
      <p class="lede">A field app used one-handed on a doorstep and a portal used at a desk, sharing
      one palette. Sage carries the calm states, amber asks for attention, red is spent only when a
      human has to look now.</p>
    </div>
    <button class="toggle" id="themeToggle" type="button" aria-pressed="false">
      <span id="themeLabel">Dark</span>
    </button>
  </header>

  <div class="facts">
    <span class="fact">Text contrast <b>4.5:1</b> minimum</span>
    <span class="fact">Interactive borders <b>3:1</b></span>
    <span class="fact">Field tap target <b>56px</b></span>
    <span class="fact">Field body text <b>18px</b></span>
    <span class="fact">WCAG 2.2 floor <b>24px</b></span>
  </div>

  <main class="items">
{chr(10).join(items)}
  </main>

  <footer class="foot">
    <span>Generated from <code>design/tokens.css</code> — previews are built, not hand-edited.</span>
    <a href="https://github.com/javalonso/baton">github.com/javalonso/baton</a>
  </footer>
</div>

<script>
  const SOURCES = [
{script_sources}
  ];

  const root = document.documentElement;
  const btn = document.getElementById('themeToggle');
  const label = document.getElementById('themeLabel');

  function currentTheme() {{
    const stamped = root.getAttribute('data-theme');
    if (stamped) return stamped;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }}

  function render(theme) {{
    document.querySelectorAll('iframe[data-idx]').forEach((frame) => {{
      const src = SOURCES[Number(frame.dataset.idx)];
      frame.srcdoc = src.replace('<html lang="en">', '<html lang="en" data-theme="' + theme + '">');
    }});
    label.textContent = theme === 'dark' ? 'Light' : 'Dark';
    btn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
  }}

  function fit(frame) {{
    try {{
      const doc = frame.contentDocument;
      if (doc && doc.body) frame.style.height = (doc.body.scrollHeight + 8) + 'px';
    }} catch (e) {{ /* keep the fallback height */ }}
  }}

  document.querySelectorAll('iframe[data-idx]').forEach((frame) => {{
    frame.addEventListener('load', () => fit(frame));
  }});

  btn.addEventListener('click', () => {{
    const next = currentTheme() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    render(next);
  }});

  render(currentTheme());
  window.addEventListener('resize', () => {{
    document.querySelectorAll('iframe[data-idx]').forEach(fit);
  }});
</script>
"""


def _js_string(s: str) -> str:
    """Serialize a Python string as a safe JS single-quoted literal."""
    out = (
        s.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace("</script", "<\\/script")
    )
    return "'" + out + "'"


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else PREVIEW / "gallery-fragment.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build(), encoding="utf-8")
    print(f"wrote {target}")
