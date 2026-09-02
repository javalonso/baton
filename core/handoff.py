"""The one page.

This sheet gets read in two situations, and both are bad ones: a volunteer taking a shift
for someone they have never met, and a triage nurse asking questions nobody in the room can
answer. Neither reader is going to scroll, search or log in, which is why it is one page of
paper and why the layout is fixed rather than flowed.

No model touches this file. Every line on the sheet is either a field somebody wrote down or
a sentence the brief agent already produced and `core.safety` already cleared. Laying it out
is arithmetic, and arithmetic belongs in code.

The left column is fact and the right column is prose, because the two get read by different
people in a hurry. A nurse reads the left. The next volunteer reads the right.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from core.models import Brief, Elder

PAGE_W, PAGE_H = letter
MARGIN = 46
GUTTER = 26
LEFT_W = 236
RIGHT_W = PAGE_W - (2 * MARGIN) - LEFT_W - GUTTER
RIGHT_X = MARGIN + LEFT_W + GUTTER

INK = (0.10, 0.11, 0.12)
MUTED = (0.42, 0.44, 0.46)
RULE = (0.80, 0.82, 0.84)
URGENT = (0.65, 0.16, 0.16)

LABELS = {
    "es": {
        "sheet": "Hoja de relevo",
        "conditions": "Diagnósticos en el expediente",
        "allergies": "Alergias",
        "medications": "Medicamentos vigentes",
        "contacts": "Contactos",
        "decision": "Quién decide",
        "since": "Qué cambió desde la última visita",
        "watch": "Qué vigilar hoy",
        "calm": "Cómo estar con ella o él",
        "none": "Nada registrado",
        "no_allergies": "Ninguna registrada",
        "refill": "resurtir",
        "generated": "Generada",
        "disclaimer": (
            "Escrita por vecinos, no por personal médico. Describe lo observado; "
            "no diagnostica ni indica tratamiento."
        ),
    },
    "en": {
        "sheet": "Handoff sheet",
        "conditions": "On the record",
        "allergies": "Allergies",
        "medications": "Current medications",
        "contacts": "Contacts",
        "decision": "Who decides",
        "since": "What changed since the last visit",
        "watch": "What to watch for today",
        "calm": "How to be with them",
        "none": "Nothing recorded",
        "no_allergies": "None recorded",
        "refill": "refill",
        "generated": "Generated",
        "disclaimer": (
            "Written by neighbours, not by clinicians. It describes what was observed; "
            "it does not diagnose or prescribe."
        ),
    },
}


def _age(dob: date | None, as_of: date) -> int | None:
    if dob is None:
        return None
    had_birthday = (as_of.month, as_of.day) >= (dob.month, dob.day)
    return as_of.year - dob.year - (0 if had_birthday else 1)


class _Column:
    """A cursor that draws downward and refuses to run off the page.

    Every section asks whether it fits before it draws. A sheet that silently spills onto a
    second page is worse than one that stops early, because the reader never learns that the
    part they needed was the part that got cut.
    """

    def __init__(self, pdf: canvas.Canvas, x: float, width: float, top: float, bottom: float):
        self.pdf = pdf
        self.x = x
        self.width = width
        self.y = top
        self.bottom = bottom

    def room_for(self, height: float) -> bool:
        return self.y - height >= self.bottom

    def heading(self, text: str) -> None:
        if not self.room_for(20):
            return
        self.y -= 15
        self.pdf.setFillColorRGB(*MUTED)
        self.pdf.setFont("Helvetica-Bold", 7.6)
        self.pdf.drawString(self.x, self.y, text.upper())
        self.y -= 5
        self.pdf.setStrokeColorRGB(*RULE)
        self.pdf.setLineWidth(0.5)
        self.pdf.line(self.x, self.y, self.x + self.width, self.y)
        self.y -= 3

    def body(self, text: str, size: float = 9.6, leading: float = 12.6, bold: bool = False) -> None:
        if not text:
            return
        font = "Helvetica-Bold" if bold else "Helvetica"
        lines = simpleSplit(text, font, size, self.width)
        self.pdf.setFillColorRGB(*INK)
        self.pdf.setFont(font, size)
        for line in lines:
            if not self.room_for(leading):
                return
            self.y -= leading
            self.pdf.drawString(self.x, self.y, line)

    def note(self, text: str, size: float = 8.4) -> None:
        if not text or not self.room_for(11):
            return
        self.pdf.setFillColorRGB(*MUTED)
        self.pdf.setFont("Helvetica", size)
        self.y -= 11
        self.pdf.drawString(self.x, self.y, text)

    def gap(self, height: float = 6) -> None:
        self.y -= height


def _medication_line(name: str, dose: str, schedule: str) -> str:
    parts = [p for p in (name, dose) if p]
    head = " ".join(parts)
    return f"{head}. {schedule}" if schedule else head


def render(
    elder: Elder,
    brief: Brief,
    out_path: Path | str,
    as_of: date,
    locale: str = "es",
    urgent: bool = False,
) -> Path:
    """Draw the sheet and return where it landed."""
    words = LABELS.get(locale, LABELS["es"])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = canvas.Canvas(str(out_path), pagesize=letter)
    pdf.setTitle(f"{words['sheet']} · {elder.name}")

    # -- masthead ------------------------------------------------------------
    y = PAGE_H - MARGIN
    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(MARGIN, y, words["sheet"].upper())
    if urgent:
        pdf.setFillColorRGB(*URGENT)
        pdf.drawRightString(PAGE_W - MARGIN, y, "!")

    y -= 30
    pdf.setFillColorRGB(*INK)
    pdf.setFont("Helvetica-Bold", 23)
    pdf.drawString(MARGIN, y, elder.name)

    age = _age(elder.dob, as_of)
    subtitle = ", ".join(p for p in (f"{age}" if age else "", elder.address) if p)
    if subtitle:
        y -= 15
        pdf.setFillColorRGB(*MUTED)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(MARGIN, y, subtitle)

    y -= 12
    pdf.setStrokeColorRGB(*INK)
    pdf.setLineWidth(1.2)
    pdf.line(MARGIN, y, PAGE_W - MARGIN, y)

    floor = MARGIN + 34
    left = _Column(pdf, MARGIN, LEFT_W, y, floor)
    right = _Column(pdf, RIGHT_X, RIGHT_W, y, floor)

    # -- left column: what a nurse would ask for -----------------------------
    left.heading(words["allergies"])
    left.body(
        ", ".join(elder.allergies) if elder.allergies else words["no_allergies"],
        bold=bool(elder.allergies),
    )
    left.gap()

    left.heading(words["medications"])
    if elder.medications:
        for med in elder.medications:
            left.body(_medication_line(med.name, med.dose, med.schedule))
            if med.refill_due:
                left.note(f"{words['refill']}: {med.refill_due.isoformat()}")
            left.gap(3)
    else:
        left.body(words["none"])
    left.gap()

    left.heading(words["conditions"])
    left.body(", ".join(elder.conditions) if elder.conditions else words["none"])
    left.gap()

    left.heading(words["contacts"])
    if elder.contacts:
        for contact in elder.contacts:
            left.body(f"{contact.name} ({contact.relationship})")
            left.note(contact.phone)
            left.gap(3)
    else:
        left.body(words["none"])

    if elder.decision_maker:
        left.gap()
        left.heading(words["decision"])
        left.body(elder.decision_maker)

    # -- right column: what the next volunteer needs -------------------------
    right.heading(words["since"])
    right.body(brief.since_last_visit or words["none"])
    right.gap(10)

    right.heading(words["watch"])
    right.body(brief.watch_for or words["none"])
    right.gap(10)

    right.heading(words["calm"])
    right.body(brief.how_to_be_with_them or elder.communication_notes or words["none"])

    # -- footer --------------------------------------------------------------
    pdf.setStrokeColorRGB(*RULE)
    pdf.setLineWidth(0.5)
    pdf.line(MARGIN, MARGIN + 22, PAGE_W - MARGIN, MARGIN + 22)
    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica", 7.4)
    stamp = (brief.generated_at or datetime.combine(as_of, datetime.min.time())).strftime(
        "%Y-%m-%d %H:%M"
    )
    pdf.drawString(MARGIN, MARGIN + 12, f"{words['generated']} {stamp} · Baton")
    for i, line in enumerate(simpleSplit(words["disclaimer"], "Helvetica", 7.4, PAGE_W - 2 * MARGIN)):
        pdf.drawString(MARGIN, MARGIN + 3 - (i * 9), line)

    pdf.showPage()
    pdf.save()
    return out_path
