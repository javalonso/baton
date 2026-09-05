/**
 * Who is signed in, and what language they read.
 *
 * The token lives in localStorage so a volunteer who closes the app between two doorsteps
 * does not type six digits again. On launch the app asks the API whether that token is still
 * good rather than trusting it, because a revoked volunteer should not see a stale roster.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, ApiError, getToken, setToken } from "./api";
import type { Session } from "./api";
import { translator } from "./i18n";
import type { Key, Locale } from "./i18n";

type SessionState = {
  session: Session | null;
  ready: boolean;
  locale: Locale;
  t: (key: Key) => string;
  signIn: (code: string) => Promise<void>;
  signOut: () => void;
  setLocale: (locale: Locale) => void;
};

const SessionContext = createContext<SessionState | null>(null);
const LOCALE_KEY = "baton.locale";

function preferredLocale(): Locale {
  const saved = localStorage.getItem(LOCALE_KEY);
  if (saved === "es" || saved === "en") return saved;
  return navigator.language.startsWith("en") ? "en" : "es";
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [locale, setLocaleState] = useState<Locale>(preferredLocale);

  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    api
      .me()
      .then((who) => setSession(who))
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) setToken(null);
      })
      .finally(() => setReady(true));
  }, []);

  const signIn = useCallback(async (code: string) => {
    const who = await api.login(code);
    setToken(who.token);
    setSession(who);
    // The volunteer's own language wins over the browser's. Somebody handed this phone to
    // somebody else at some point, and the roster knows which language they read.
    setLocaleState(who.locale);
    localStorage.setItem(LOCALE_KEY, who.locale);
  }, []);

  const signOut = useCallback(() => {
    setToken(null);
    setSession(null);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    localStorage.setItem(LOCALE_KEY, next);
  }, []);

  return (
    <SessionContext.Provider
      value={{ session, ready, locale, t: translator(locale), signIn, signOut, setLocale }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionState {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession outside SessionProvider");
  return value;
}
