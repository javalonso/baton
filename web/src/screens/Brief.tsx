import { useEffect, useState } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import type { BriefResponse } from "../lib/api";
import { useSession } from "../lib/session";

/**
 * V2. The screen that does not exist in this work today.
 *
 * The first person to open a given person on a given day waits about twenty seconds for a
 * reasoning model to read their history. Everybody after that gets it immediately, because
 * the API caches the prose per person per day. So this screen tells the truth about which
 * one is happening rather than showing a spinner and hoping.
 */
export default function Brief() {
  const { elderId = "" } = useParams();
  const [params] = useSearchParams();
  const shiftId = params.get("shift");
  // The card that was tapped already knew the name. Carrying it through means the twenty
  // seconds of waiting is spent under a heading rather than under a blank.
  const known = (useLocation().state as { name?: string } | null)?.name ?? "";
  const { t, locale } = useSession();
  const [data, setData] = useState<BriefResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    api.brief(elderId, locale).then(setData).catch((problem) => setError(problem.message));
  }, [elderId, locale]);

  return (
    <div className="screen brief">
      <header>
        <Link to="/" className="badge" style={{ textDecoration: "none" }}>
          {t("Back")}
        </Link>
        <h2 style={{ marginTop: "var(--space-3)" }}>{data?.elder_name ?? known}</h2>
        <p className="subtle">{t("Before you knock")}</p>
      </header>

      {error && <div className="error">{error}</div>}

      {!data && !error && (
        <div>
          <p className="subtle" style={{ marginBottom: "var(--space-4)" }}>
            {t("Writing the brief")} · {t("This takes a moment the first time")}
          </p>
          <div className="skeleton" style={{ width: "35%" }} />
          <div className="skeleton" />
          <div className="skeleton" style={{ width: "80%" }} />
          <div className="skeleton" style={{ width: "35%", marginTop: "var(--space-6)" }} />
          <div className="skeleton" />
        </div>
      )}

      {data && (
        <>
          <section>
            <h3>{t("Since the last visit")}</h3>
            <p>{data.brief.since_last_visit}</p>
          </section>
          <section>
            <h3>{t("What to watch for")}</h3>
            <p>{data.brief.watch_for}</p>
          </section>
          <section>
            <h3>{t("How to be with them")}</h3>
            <p>{data.brief.how_to_be_with_them}</p>
          </section>

          <span className="badge">
            {data.written_by_model ? t("Written by Baton") : t("From the record")}
          </span>

          <div className="footer-actions">
            <Link
              className="button"
              style={{ textDecoration: "none" }}
              to={`/record/${elderId}${shiftId ? `?shift=${shiftId}` : ""}`}
            >
              {t("Record the visit")}
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
