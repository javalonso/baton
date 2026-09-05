import { useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import type { Observation } from "../lib/api";
import { available, listen } from "../lib/dictation";
import type { Recorder } from "../lib/dictation";
import type { Key } from "../lib/i18n";
import { useSession } from "../lib/session";

type Stage = "speaking" | "reading" | "checking" | "done";

/**
 * V3. Speak, then correct. Never a form.
 *
 * The volunteer talks, the agent proposes what it heard as chips, and the volunteer taps
 * away anything wrong. What they are left with is what the record keeps -- their version
 * wins, because they are the one who was in the room.
 */
export default function Record() {
  const { elderId = "" } = useParams();
  const [params] = useSearchParams();
  const shiftId = params.get("shift");
  const navigate = useNavigate();
  const { t, locale } = useSession();

  const [stage, setStage] = useState<Stage>("speaking");
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [visitId, setVisitId] = useState("");
  const [observations, setObservations] = useState<Observation[]>([]);
  const [removed, setRemoved] = useState<Set<number>>(new Set());
  const [error, setError] = useState("");
  const recorder = useRef<Recorder | null>(null);

  const canSpeak = available();

  function toggleListening() {
    if (listening) {
      recorder.current?.stop();
      return;
    }
    const started = listen(
      locale,
      (text) => setTranscript(text),
      () => setListening(false),
    );
    if (!started) {
      setError(t("Your phone cannot listen here"));
      return;
    }
    recorder.current = started;
    setTranscript("");
    setListening(true);
    started.start();
  }

  async function send() {
    setStage("reading");
    setError("");
    try {
      const result = await api.record(
        { elder_id: elderId, shift_id: shiftId, transcript },
        locale,
      );
      setVisitId(result.visit_id);
      setObservations(result.observations);
      setStage("checking");
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : t("Something went wrong"));
      setStage("speaking");
    }
  }

  async function confirm() {
    const kept = observations.filter((_, index) => !removed.has(index));
    try {
      await api.confirm(visitId, kept, locale);
      setStage("done");
      setTimeout(() => navigate("/"), 1600);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : t("Something went wrong"));
    }
  }

  function toggleChip(index: number) {
    setRemoved((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  if (stage === "done") {
    return (
      <div className="screen">
        <div className="empty">
          <strong>{t("Saved")}</strong>
          {t("Thank you")}
        </div>
      </div>
    );
  }

  return (
    <div className="screen">
      <header>
        <h2>{t("Record the visit")}</h2>
        <p className="subtle">{t("What happened on this visit?")}</p>
      </header>

      {error && <div className="error">{error}</div>}

      {stage === "speaking" && (
        <>
          {canSpeak && (
            <div className="record">
              <button
                className="record-button"
                data-listening={listening}
                onClick={toggleListening}
                aria-pressed={listening}
              >
                {listening ? t("Listening") : t("Hold to talk")}
              </button>
              <p className="subtle">{listening ? t("Tap when you are done") : ""}</p>
            </div>
          )}

          <label className="subtle" htmlFor="note">
            {canSpeak ? t("Or type it") : t("What happened on this visit?")}
          </label>
          <textarea
            id="note"
            value={transcript}
            onChange={(event) => setTranscript(event.target.value)}
            placeholder={t("What happened on this visit?")}
          />

          <div className="footer-actions">
            <button className="button" disabled={!transcript.trim()} onClick={send}>
              {t("Send")}
            </button>
          </div>
        </>
      )}

      {stage === "reading" && (
        <div className="empty">
          <strong>{t("Reading what you said")}</strong>
          <div className="skeleton" style={{ marginTop: "var(--space-6)" }} />
          <div className="skeleton" style={{ width: "70%" }} />
        </div>
      )}

      {stage === "checking" && (
        <>
          <p className="subtle">{t("Tap anything that is wrong to remove it")}</p>
          <div className="chips">
            {observations.map((observation, index) => (
              <button
                key={`${observation.category}-${index}`}
                className="chip"
                data-trend={observation.trend}
                data-removed={removed.has(index)}
                onClick={() => toggleChip(index)}
              >
                <span className="category">
                  {t(observation.category as Key)} · {t(observation.trend as Key)}
                </span>
                <span className="summary">{observation.summary}</span>
                <span className="quote">&ldquo;{observation.quote}&rdquo;</span>
              </button>
            ))}
          </div>

          <div className="footer-actions">
            <button className="button" onClick={confirm}>
              {t("Confirm")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
