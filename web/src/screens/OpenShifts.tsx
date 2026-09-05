import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import type { ShiftCard } from "../lib/api";
import { dayAndTime } from "../lib/i18n";
import { useSession } from "../lib/session";

/**
 * V4. The gaps, and one tap to fill one.
 *
 * The second person to tap a shift is told plainly that somebody else got there first. That
 * message comes from the API in their own language, so this screen shows it verbatim rather
 * than inventing a friendlier version of a conflict.
 */
export default function OpenShifts() {
  const { t, locale } = useSession();
  const [shifts, setShifts] = useState<ShiftCard[] | null>(null);
  const [claiming, setClaiming] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  function load() {
    api.openShifts(locale).then(setShifts).catch((problem) => setError(problem.message));
  }

  useEffect(load, [locale]);

  async function claim(shiftId: string) {
    setClaiming(shiftId);
    setError("");
    try {
      const result = await api.claim(shiftId, locale);
      setNote(result.message);
      setShifts((current) => (current ?? []).filter((s) => s.id !== shiftId));
    } catch (problem) {
      if (problem instanceof ApiError && problem.status === 409) {
        setError(problem.message);
        load();
      } else {
        setError(problem instanceof Error ? problem.message : t("Something went wrong"));
      }
    } finally {
      setClaiming("");
    }
  }

  return (
    <div className="screen">
      <header>
        <Link to="/" className="badge" style={{ textDecoration: "none" }}>
          {t("Back")}
        </Link>
        <h2 style={{ marginTop: "var(--space-3)" }}>{t("Gaps this week")}</h2>
        <p className="subtle">{t("Nobody is scheduled for these")}</p>
      </header>

      {error && <div className="error">{error}</div>}
      {note && <div className="card" style={{ borderColor: "var(--sage)" }}>{note}</div>}

      {shifts?.length === 0 && (
        <div className="empty">
          <strong>{t("Everything is covered")}</strong>
        </div>
      )}

      {shifts?.map((shift) => (
        <div key={shift.id} className="card">
          <span className="name">{shift.elder_name}</span>
          <span className="meta">{dayAndTime(shift.scheduled_at, locale)}</span>
          {shift.address && <span className="meta">{shift.address}</span>}
          <div style={{ marginTop: "var(--space-3)" }}>
            <button
              className="button"
              disabled={claiming === shift.id}
              onClick={() => claim(shift.id)}
            >
              {claiming === shift.id ? t("Claiming") : t("Claim")}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
