"""Generate the synthetic dataset.

Deterministic: same seed, same dataset, so the demo and the tests describe the same world.
Nothing here is real. No real person's information is used.

Three scenarios are built in, and the second and third are the interesting pair — Rafael and
Dolores look identical if you only read the last eight days. Only their own histories tell
them apart, which is the entire argument for a per-person baseline.
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from core.models import Contact, Elder, Medication, Observation, Visit, Volunteer
from core.vocabulary import Category, Confidence, Trend

SEED = 20260914
TODAY = date(2026, 9, 14)
WEEKS = 6
OUT = Path(__file__).resolve().parents[1] / "data" / "seed.json"

FIRST = ["Carmen", "Rafael", "Dolores", "Esperanza", "Ignacio", "Refugio", "Baltazar", "Amparo",
         "Rosendo", "Consuelo", "Salvador", "Guadalupe", "Fermín", "Otilia", "Aurelio", "Remedios",
         "Ceferino", "Josefina", "Aureliano", "Herlinda", "Práxedis", "Soledad", "Eulalio", "Natividad"]
LAST = ["Ibarra", "Ortiz", "Mendoza", "Vargas", "Cordero", "Zamudio", "Lozano", "Ferrer",
        "Barrios", "Quintero", "Nájera", "Escamilla", "Padilla", "Tejeda", "Villalpando", "Rueda",
        "Cañedo", "Sandoval", "Arriaga", "Bermúdez", "Cisneros", "Delgadillo", "Espinoza", "Fajardo"]
VOLUNTEERS = ["Ana Ruiz", "Marco Delgado", "Sofía Lara", "Diego Peña", "Lucero Nava",
              "Tomás Aguilar", "Renata Fuentes", "Iván Cabrera", "Paola Serrano", "Hugo Miranda",
              "Elisa Bravo", "Nicolás Rivas", "Camila Trejo", "Andrés Vela"]

# (category, summary, quote, language) for ordinary, nothing-wrong observations.
CALM = [
    (Category.FOOD, "Ate a normal meal", "Comió bien, se acabó su plato", "es"),
    (Category.FOOD, "Ate normally", "She finished her lunch, no trouble", "en"),
    (Category.FLUIDS, "Drank normally", "Se tomó dos vasos de agua enfrente de mí", "es"),
    (Category.SLEEP, "Slept normally", "Durmió bien, dice que no se despertó", "es"),
    (Category.SLEEP, "Slept normally", "Said she slept straight through", "en"),
    (Category.MOOD, "In good spirits", "Andaba contenta, me contó de sus nietos", "es"),
    (Category.MOOD, "In good spirits", "Chatty today, in a good mood", "en"),
    (Category.MOBILITY, "Moving around normally", "Caminó a la cocina sin ayuda", "es"),
    (Category.SOCIAL, "Had a visitor", "Vino su sobrina el domingo", "es"),
    (Category.MEDICATION, "Took medication", "Se tomó sus pastillas mientras yo estaba", "es"),
]

WORSE = {
    Category.FLUIDS: [
        ("Declined water", "No quiso el agua, dijo que ya había tomado", "es"),
        ("Drinking less than usual", "El vaso estaba lleno igual que ayer", "es"),
        ("Barely drank anything", "She hardly drank anything while I was there", "en"),
    ],
    Category.ORIENTATION: [
        ("Asked what day it was, twice", "Me preguntó dos veces qué día era", "es"),
        ("Seemed confused about the time", "Pensaba que era de mañana y ya eran las seis", "es"),
        ("Did not seem to know where she was for a moment", "She looked lost for a second", "en"),
    ],
    Category.SLEEP: [
        ("Slept badly", "Dice que casi no durmió, como cuatro horas", "es"),
        ("Slept badly again", "He said he was up most of the night again", "en"),
    ],
    Category.MOOD: [
        ("Flat, did not want to talk", "No quiso platicar, muy callado", "es"),
        ("Low mood", "Mood is flat, not like him", "en"),
    ],
    Category.FOOD: [
        ("Ate very little", "Comió poquito, como medio plato", "es"),
        ("Barely touched the food", "She barely touched her food", "en"),
    ],
}


# What each condition is usually treated with. Deriving medication from the condition keeps
# the record coherent: a handoff sheet listing a blood-pressure tablet for someone with no
# blood-pressure entry is the kind of detail that costs a reader their trust in the page.
TREATMENT = {
    "hypertension": ("Losartán", "50 mg", "una al día por la mañana"),
    "type 2 diabetes": ("Metformina", "850 mg", "con la comida principal"),
    "arthritis": ("Paracetamol", "500 mg", "cuando le duele, máximo tres al día"),
}

# How to be with this person. Written by whoever knows them, never generated. These are the
# lines that do not exist anywhere today except in one volunteer's memory.
COMMUNICATION = [
    "Oye mejor del lado derecho. Siéntate de ese lado y háblale despacio, no más fuerte.",
    "Le calma la radio en la cocina. Si está inquieta, ponla antes de hablarle.",
    "No le gusta que le hablen como a una niña. Trátala de usted.",
    "Se pone nervioso con gente nueva. Di tu nombre al entrar y otra vez al sentarte.",
    "Prefiere que le avisen antes de tocarla. Pregunta antes de ayudarla a levantarse.",
    "Tarda en encontrar las palabras. No las completes por él, espera.",
]

RELATIONSHIPS = ["hija", "hijo", "sobrina", "nieto", "vecina", "hermana"]

# Kept apart from `FIRST` so a relative never shares a first name with somebody the network
# looks after. On a handoff sheet, "Rafael Ibarra (hijo)" next to a Rafael on the roster is
# a second of doubt for a reader who has none to spare.
FAMILY = ["Alma", "Bernardo", "Cristina", "Damián", "Elvira", "Fabián", "Gabriela", "Héctor",
          "Irene", "Joaquín", "Karina", "Leonel", "Mariana", "Nadia", "Óscar", "Patricia",
          "Quirino", "Rebeca", "Silvia", "Teodoro", "Ursula", "Valentín", "Ximena", "Yolanda"]


def _profile(prng: random.Random, elder: Elder) -> None:
    """Fill in the parts of a record that a handoff sheet needs and a visit note never has.

    Deliberately driven by its own generator: the visit history above must not shift because
    this was added, or every number already published about the dataset stops being true.
    """
    family = prng.choice(RELATIONSHIPS)
    elder.contacts = [
        Contact(
            name=f"{prng.choice(FAMILY)} {elder.name.split()[-1]}",
            relationship=family,
            phone=f"55 {prng.randint(1000, 9999)} {prng.randint(1000, 9999)}",
        )
    ]
    elder.decision_maker = f"{elder.contacts[0].name} ({family})"
    elder.communication_notes = prng.choice(COMMUNICATION)

    if prng.random() < 0.25:
        elder.allergies = [prng.choice(["penicilina", "sulfas", "mariscos"])]

    for condition in elder.conditions:
        treatment = TREATMENT.get(condition)
        if treatment is None:
            continue
        name, dose, schedule = treatment
        prescribed = TODAY - timedelta(days=prng.randint(20, 88))
        elder.medications.append(
            Medication(
                name=name,
                dose=dose,
                schedule=schedule,
                prescribed_at=prescribed,
                refill_due=prescribed + timedelta(days=90),
            )
        )


def _obs(category: Category, summary: str, quote: str, trend: Trend) -> Observation:
    return Observation(
        category=category,
        summary=summary,
        trend=trend,
        confidence=Confidence.CLEAR,
        quote=quote,
    )


def _worse(rng: random.Random, category: Category) -> Observation:
    summary, quote, _lang = rng.choice(WORSE[category])
    return _obs(category, summary, quote, Trend.WORSE)


def _calm(rng: random.Random, n: int) -> list[Observation]:
    picks = rng.sample(CALM, k=min(n, len(CALM)))
    return [_obs(c, s, q, Trend.USUAL) for c, s, q, _lang in picks]


def build() -> dict:
    rng = random.Random(SEED)
    org_id = "org-san-miguel"

    elders = [
        Elder(
            id=f"elder-{i + 1:02d}",
            org_id=org_id,
            name=f"{FIRST[i]} {LAST[i]}",
            address=f"Calle {LAST[i]} {rng.randint(10, 240)}",
            conditions=rng.sample(
                ["hypertension", "type 2 diabetes", "arthritis", "hearing loss", "low vision"],
                k=rng.randint(1, 2),
            ),
        )
        for i in range(24)
    ]
    # Its own generator, on purpose. See `_profile`.
    prng = random.Random(SEED + 7)
    for elder in elders:
        _profile(prng, elder)

    volunteers = [
        Volunteer(id=f"vol-{i + 1:02d}", org_id=org_id, name=name, locale="es" if i % 3 else "en")
        for i, name in enumerate(VOLUNTEERS)
    ]

    visits: list[Visit] = []
    counter = 0
    start = TODAY - timedelta(weeks=WEEKS)

    for elder in elders:
        idx = int(elder.id.split("-")[1])
        day = start
        while day <= TODAY:
            days_ago = (TODAY - day).days
            # The three scenarios must not depend on a dice roll — a visit is guaranteed on
            # the days that carry them.
            scripted = (elder.id == "elder-01" and days_ago <= 2) or (
                elder.id == "elder-02" and days_ago <= 7
            )
            # Otherwise, roughly three visits a week per person.
            if scripted or rng.random() < 0.43:
                # Scenario 3: one volunteer carries the network, four have gone quiet.
                if rng.random() < 0.31:
                    volunteer = volunteers[0]
                else:
                    pool = volunteers[1:10] if (TODAY - day).days < 14 else volunteers[1:]
                    volunteer = rng.choice(pool)

                observations = _calm(rng, rng.randint(2, 3))

                # Scenario 1 — Carmen: acute, three days, includes orientation.
                if elder.id == "elder-01" and days_ago <= 2:
                    observations = [
                        _worse(rng, Category.FLUIDS),
                        _worse(rng, Category.ORIENTATION),
                        _worse(rng, Category.FOOD),
                    ]
                # Scenario 2 — Rafael: slow drift, eight days, clean history behind it.
                elif elder.id == "elder-02" and days_ago <= 7:
                    observations = [
                        _worse(rng, Category.SLEEP),
                        _worse(rng, Category.MOOD),
                    ] + _calm(rng, 1)
                # Scenario 2b — Dolores: the control. Identical last eight days, but this is
                # simply how she has always been, so it is not news about her.
                elif elder.id == "elder-03" and rng.random() < 0.62:
                    observations = [
                        _worse(rng, Category.SLEEP),
                        _worse(rng, Category.MOOD),
                    ] + _calm(rng, 1)

                counter += 1
                visits.append(
                    Visit(
                        id=f"visit-{counter:05d}",
                        elder_id=elder.id,
                        volunteer_id=volunteer.id,
                        started_at=datetime.combine(day, datetime.min.time())
                        + timedelta(hours=rng.randint(9, 19), minutes=rng.choice([0, 15, 30, 45])),
                        transcript="",
                        source_lang="en" if rng.random() < 0.3 else "es",
                        observations=observations,
                        confirmed=True,
                    )
                )
            day += timedelta(days=1)
        _ = idx

    return {
        "generated_for": TODAY.isoformat(),
        "seed": SEED,
        "organization": {"id": org_id, "name": "Red Vecinal San Miguel", "timezone": "America/Mexico_City"},
        "elders": [e.model_dump(mode="json") for e in elders],
        "volunteers": [v.model_dump(mode="json") for v in volunteers],
        "visits": [v.model_dump(mode="json") for v in visits],
    }


if __name__ == "__main__":
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(OUT.parents[1])}: "
        f"{len(data['elders'])} elders, {len(data['volunteers'])} volunteers, "
        f"{len(data['visits'])} visits"
    )
