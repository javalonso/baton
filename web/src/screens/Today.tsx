import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { ElderCard, TodayResponse } from "../lib/api";
import { relativeDays, timeOfDay } from "../lib/i18n";
import { useSession } from "../lib/session";

/**
 * V1. What one volunteer has to do today, in the order it happens.
 *
 * Nothing about anybody else's rounds, and no counts of how the network is doing. A
 * volunteer opening this on the bus needs to know where to go and who they are about to see.
 */
export default function Today() {
  const { t, locale } = useSession();
  const [data, setData] = useState<TodayResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.today(locale).then(setData).catch((problem) => setError(problem.message));
  }, [locale]);

  if (error) return <div className="screen"><div className="error">{error}</div></div>;

  if (!data) {
    return (
      <div className="screen">
        <div className="skeleton" style={{ width: "40%", height: "2rem" }} />
        <div className="card"><div className="skeleton" /><div className="skeleton" style={{ width: "60%" }} /></div>
        <div className="card"><div className="skeleton" /><div className="skeleton" style={{ width: "60%" }} /></div>
      </div>
    );
  }

  const person = (elderId: string): ElderCard | undefined =>
    data.people.find((p) => p.id === elderId);

  return (
    <div className="screen">
      <header>
        <h2>{t("Today")}</h2>
        <p className="subtle">
          {data.shifts.length} {data.shifts.length === 1 ? t("visit") : t("visits")}
        </p>
      </header>

      {data.shifts.length === 0 ? (
        <div className="empty">
          <strong>{t("Nothing scheduled today")}</strong>
          {t("Enjoy the quiet")}
        </div>
      ) : (
        data.shifts.map((shift) => {
          const who = person(shift.elder_id);
          return (
            <Link
              key={shift.id}
              to={`/brief/${shift.elder_id}?shift=${shift.id}`}
              state={{ name: shift.elder_name }}
              className="card tappable"
            >
              <span className="when">{timeOfDay(shift.scheduled_at, locale)}</span>
              <span className="name">{shift.elder_name}</span>
              {shift.address && <span className="meta">{shift.address}</span>}
              <span className="meta">
                {t("Last visit")}: {relativeDays(who?.days_since_visit ?? null, t)}
                {who?.last_visit_by ? ` · ${who.last_visit_by}` : ""}
              </span>
            </Link>
          );
        })
      )}

      <div style={{ marginTop: "var(--space-8)" }}>
        <Link className="button quiet" to="/open" style={{ textDecoration: "none" }}>
          {t("Open shifts")}
        </Link>
      </div>
    </div>
  );
}
