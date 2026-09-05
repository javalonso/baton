/**
 * Two languages, one file.
 *
 * The product is bilingual because the network is: a volunteer speaks Spanish at the door
 * and the coordinator reads English at her desk, or the other way round, and neither should
 * have to switch. Stored data stays language-neutral; only these strings and the model's
 * prose have a language at all.
 *
 * Keys are sentences, not identifiers, so a missing translation reads as English rather than
 * as `screen.today.header.title`.
 */

export type Locale = "es" | "en";

const strings = {
  // -- shell
  "Baton": { es: "Baton", en: "Baton" },
  "Sign out": { es: "Cerrar sesión", en: "Sign out" },
  "Loading": { es: "Cargando", en: "Loading" },
  "Try again": { es: "Reintentar", en: "Try again" },
  "Something went wrong": { es: "Algo salió mal", en: "Something went wrong" },
  "Back": { es: "Atrás", en: "Back" },

  // -- login
  "Enter your code": { es: "Ingresa tu código", en: "Enter your code" },
  "Six digits from your coordinator": {
    es: "Seis dígitos que te dio tu coordinadora",
    en: "Six digits from your coordinator",
  },
  "Sign in": { es: "Entrar", en: "Sign in" },
  "Checking": { es: "Verificando", en: "Checking" },

  // -- V1 today
  "Today": { es: "Hoy", en: "Today" },
  "Nothing scheduled today": { es: "Nada agendado hoy", en: "Nothing scheduled today" },
  "Enjoy the quiet": { es: "Disfruta la calma", en: "Enjoy the quiet" },
  "visit": { es: "visita", en: "visit" },
  "visits": { es: "visitas", en: "visits" },
  "Last visit": { es: "Última visita", en: "Last visit" },
  "No visits yet": { es: "Sin visitas aún", en: "No visits yet" },
  "today": { es: "hoy", en: "today" },
  "yesterday": { es: "ayer", en: "yesterday" },
  "days ago": { es: "días", en: "days ago" },
  "Open shifts": { es: "Turnos abiertos", en: "Open shifts" },

  // -- V2 brief
  "Before you knock": { es: "Antes de tocar", en: "Before you knock" },
  "Since the last visit": { es: "Desde la última visita", en: "Since the last visit" },
  "What to watch for": { es: "Qué mirar", en: "What to watch for" },
  "How to be with them": { es: "Cómo tratarla", en: "How to be with them" },
  "Writing the brief": { es: "Escribiendo la ficha", en: "Writing the brief" },
  "This takes a moment the first time": {
    es: "La primera vez toma un momento",
    en: "This takes a moment the first time",
  },
  "Written by Baton": { es: "Escrito por Baton", en: "Written by Baton" },
  "From the record": { es: "Desde el registro", en: "From the record" },
  "Record the visit": { es: "Registrar la visita", en: "Record the visit" },

  // -- V3 record
  "Hold to talk": { es: "Mantén para hablar", en: "Hold to talk" },
  "Listening": { es: "Escuchando", en: "Listening" },
  "Tap when you are done": { es: "Toca cuando termines", en: "Tap when you are done" },
  "Or type it": { es: "O escríbelo", en: "Or type it" },
  "What happened on this visit?": {
    es: "¿Cómo fue la visita?",
    en: "What happened on this visit?",
  },
  "Send": { es: "Enviar", en: "Send" },
  "Reading what you said": { es: "Leyendo lo que dijiste", en: "Reading what you said" },
  "Is this right?": { es: "¿Está bien esto?", en: "Is this right?" },
  "Tap anything that is wrong to remove it": {
    es: "Toca lo que esté mal para quitarlo",
    en: "Tap anything that is wrong to remove it",
  },
  "Confirm": { es: "Confirmar", en: "Confirm" },
  "Saved": { es: "Guardado", en: "Saved" },
  "Thank you": { es: "Gracias", en: "Thank you" },
  "Your phone cannot listen here": {
    es: "Tu teléfono no puede escuchar aquí",
    en: "Your phone cannot listen here",
  },

  // -- V4 open shifts
  "Gaps this week": { es: "Huecos de esta semana", en: "Gaps this week" },
  "Nobody is scheduled for these": {
    es: "Nadie está agendado para estos",
    en: "Nobody is scheduled for these",
  },
  "Everything is covered": { es: "Todo está cubierto", en: "Everything is covered" },
  "Claim": { es: "Lo tomo", en: "Claim" },
  "Claiming": { es: "Tomando", en: "Claiming" },

  // -- observation categories, as a volunteer would say them
  "food": { es: "comida", en: "food" },
  "fluids": { es: "líquidos", en: "fluids" },
  "sleep": { es: "sueño", en: "sleep" },
  "mood": { es: "ánimo", en: "mood" },
  "orientation": { es: "orientación", en: "orientation" },
  "mobility": { es: "movilidad", en: "mobility" },
  "medication": { es: "medicamentos", en: "medication" },
  "pain": { es: "dolor", en: "pain" },
  "skin": { es: "piel", en: "skin" },
  "social": { es: "compañía", en: "social" },
  "household": { es: "casa", en: "household" },
  "incident": { es: "incidente", en: "incident" },
  "task": { es: "pendiente", en: "task" },

  // -- trends
  "better": { es: "mejor", en: "better" },
  "usual": { es: "como siempre", en: "usual" },
  "worse": { es: "peor", en: "worse" },
  "unclear": { es: "no queda claro", en: "unclear" },
} as const;

export type Key = keyof typeof strings;

export function translator(locale: Locale) {
  return (key: Key): string => strings[key]?.[locale] ?? key;
}

/** Time of day, in the reader's language. Dates in this product are always relative. */
export function timeOfDay(iso: string, locale: Locale): string {
  return new Date(iso).toLocaleTimeString(locale === "es" ? "es-MX" : "en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function dayAndTime(iso: string, locale: Locale): string {
  return new Date(iso).toLocaleString(locale === "es" ? "es-MX" : "en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** "today", "yesterday", "5 days ago" -- never a date somebody has to subtract from. */
export function relativeDays(days: number | null, t: (k: Key) => string): string {
  if (days === null) return t("No visits yet");
  if (days <= 0) return t("today");
  if (days === 1) return t("yesterday");
  return `${days} ${t("days ago")}`;
}
