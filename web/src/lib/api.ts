/**
 * The only way this app talks to anything.
 *
 * One place holds the token, one place turns a non-2xx into a thrown `ApiError`, and one
 * place knows the base URL. A screen that wants data calls a function here and handles two
 * outcomes: it worked, or it did not.
 */

const BASE = import.meta.env.VITE_API_URL ?? "/api";
const TOKEN_KEY = "baton.token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  locale?: string,
): Promise<T> {
  const token = getToken();
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (locale && !url.searchParams.has("lang")) url.searchParams.set("lang", locale);

  const response = await fetch(url.toString().replace(window.location.origin, ""), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });

  if (response.status === 204) return undefined as T;

  const body = await response.text();
  const parsed = body ? JSON.parse(body) : null;

  if (!response.ok) {
    // FastAPI puts the human-readable reason in `detail`, and the API writes those in the
    // caller's language. Showing it verbatim is the point: "somebody else got there first"
    // is a better message than anything this layer could invent.
    throw new ApiError(response.status, parsed?.detail ?? response.statusText);
  }
  return parsed as T;
}

export const api = {
  login: (code: string) =>
    request<Session>("/auth/login", { method: "POST", body: JSON.stringify({ code }) }),
  me: () => request<Session>("/auth/me"),

  today: (locale: string) => request<TodayResponse>("/me/today", {}, locale),
  brief: (elderId: string, locale: string, refresh = false) =>
    request<BriefResponse>(
      `/me/elders/${elderId}/brief${refresh ? "?refresh=true" : ""}`,
      {},
      locale,
    ),
  record: (body: RecordRequest, locale: string) =>
    request<RecordResponse>(
      "/me/visits",
      { method: "POST", body: JSON.stringify(body) },
      locale,
    ),
  confirm: (visitId: string, observations: Observation[], locale: string) =>
    request<RecordResponse>(
      `/me/visits/${visitId}`,
      { method: "PATCH", body: JSON.stringify({ observations, followups: [] }) },
      locale,
    ),
  openShifts: (locale: string) => request<ShiftCard[]>("/me/shifts/open", {}, locale),
  claim: (shiftId: string, locale: string) =>
    request<ClaimResponse>(`/me/shifts/${shiftId}/claim`, { method: "POST" }, locale),
};

// -- what the API sends ------------------------------------------------------

export type Session = {
  token: string;
  role: "volunteer" | "coordinator";
  id: string;
  name: string;
  org: string;
  locale: "es" | "en";
};

export type ShiftCard = {
  id: string;
  elder_id: string;
  elder_name: string;
  address: string;
  scheduled_at: string;
  status: string;
  volunteer_id: string | null;
  volunteer_name: string;
};

export type ElderCard = {
  id: string;
  name: string;
  address: string;
  last_visit: string | null;
  last_visit_by: string;
  days_since_visit: number | null;
  alert: string;
};

export type TodayResponse = {
  as_of: string;
  volunteer: string;
  shifts: ShiftCard[];
  people: ElderCard[];
};

export type Brief = {
  elder_id: string;
  locale: string;
  since_last_visit: string;
  watch_for: string;
  how_to_be_with_them: string;
  generated_at: string | null;
  written_by_model: boolean;
};

export type BriefResponse = {
  elder_id: string;
  elder_name: string;
  brief: Brief;
  last_visit: string | null;
  written_by_model: boolean;
  cached: boolean;
};

export type Observation = {
  category: string;
  summary: string;
  trend: "better" | "usual" | "worse" | "unclear";
  confidence: "clear" | "confirm";
  quote: string;
};

export type RecordRequest = {
  elder_id: string;
  shift_id?: string | null;
  transcript: string;
};

export type RecordResponse = {
  visit_id: string;
  elder_name: string;
  source_lang: string;
  observations: Observation[];
  followups: string[];
};

export type ClaimResponse = { shift: ShiftCard; message: string };
