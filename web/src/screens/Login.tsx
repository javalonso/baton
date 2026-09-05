import { useState } from "react";
import { useSession } from "../lib/session";

/**
 * Six digits and nothing else.
 *
 * No email, no password, no reset flow. The people this is for are volunteers on their own
 * phones, and every field added here is a field somebody gets wrong standing in a doorway.
 */
export default function Login() {
  const { signIn, t, locale, setLocale } = useSession();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await signIn(code);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : t("Something went wrong"));
      setBusy(false);
    }
  }

  return (
    <div className="screen">
      <header>
        <h2>{t("Enter your code")}</h2>
        <p className="subtle">{t("Six digits from your coordinator")}</p>
      </header>

      {error && <div className="error">{error}</div>}

      <form onSubmit={submit} className="stack">
        <input
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
          inputMode="numeric"
          autoComplete="one-time-code"
          aria-label={t("Enter your code")}
          autoFocus
          style={{
            fontSize: "2.25rem",
            letterSpacing: "0.35em",
            textAlign: "center",
            padding: "var(--space-4)",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-md)",
            background: "var(--surface)",
            color: "var(--text)",
            fontVariantNumeric: "tabular-nums",
          }}
        />
        <button className="button" disabled={code.length < 4 || busy}>
          {busy ? t("Checking") : t("Sign in")}
        </button>
      </form>

      <div style={{ marginTop: "var(--space-8)", textAlign: "center" }}>
        <button
          className="button quiet small"
          onClick={() => setLocale(locale === "es" ? "en" : "es")}
        >
          {locale === "es" ? "English" : "Español"}
        </button>
      </div>
    </div>
  );
}
