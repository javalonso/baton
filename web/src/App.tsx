import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Brief from "./screens/Brief";
import Login from "./screens/Login";
import OpenShifts from "./screens/OpenShifts";
import Record from "./screens/Record";
import Today from "./screens/Today";
import { SessionProvider, useSession } from "./lib/session";

/**
 * The volunteer app.
 *
 * Four screens and a way in. The coordinator portal is a separate surface with a different
 * shape -- desktop, dense, comparative -- and pretending both fit one navigation would make
 * each of them worse.
 */
function Shell() {
  const { session, ready, t, signOut, locale, setLocale } = useSession();

  if (!ready) return <div className="app" />;
  if (!session) {
    return (
      <div className="app">
        <Login />
      </div>
    );
  }

  return (
    <div className="app">
      <div className="topbar">
        <h1>{t("Baton")}</h1>
        <span className="who">{session.name}</span>
        <button
          className="button quiet small"
          onClick={() => setLocale(locale === "es" ? "en" : "es")}
        >
          {locale === "es" ? "EN" : "ES"}
        </button>
        <button className="button quiet small" onClick={signOut}>
          {t("Sign out")}
        </button>
      </div>

      <Routes>
        <Route path="/" element={<Today />} />
        <Route path="/brief/:elderId" element={<Brief />} />
        <Route path="/record/:elderId" element={<Record />} />
        <Route path="/open" element={<OpenShifts />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <Shell />
      </SessionProvider>
    </BrowserRouter>
  );
}
