import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getHouseholdSettings, updateHouseholdSettings } from "../api/households";

export default function SettingsPage() {
  const [correggiOrientamento, setCorreggiOrientamento] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHouseholdSettings()
      .then((s) => setCorreggiOrientamento(s.correggi_orientamento))
      .catch(() => setError("Impossibile caricare le impostazioni."));
  }, []);

  const toggle = async () => {
    if (correggiOrientamento === null || saving) return;
    const next = !correggiOrientamento;
    setSaving(true);
    setError(null);
    setCorreggiOrientamento(next); // ottimistico
    try {
      await updateHouseholdSettings(next);
    } catch {
      setCorreggiOrientamento(!next); // rollback
      setError("Salvataggio non riuscito, riprova.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-svh max-w-lg flex-col px-4 pb-28 pt-4">
      <div className="flex items-center gap-3">
        <Link
          to="/"
          className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300"
        >
          ←
        </Link>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Impostazioni</h1>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-medium text-slate-900 dark:text-slate-100">Correggi foto capovolte</p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Se attiva, il riconoscimento del testo raddrizza automaticamente le foto scattate capovolte o
              ruotate — puoi tenere il telefono come ti viene più comodo. Ha un costo: l'elaborazione di ogni
              foto richiede qualche centinaio di millisecondi in più.
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={correggiOrientamento ?? false}
            onClick={toggle}
            disabled={correggiOrientamento === null || saving}
            className={`relative h-7 w-12 shrink-0 rounded-full transition disabled:opacity-50 ${
              correggiOrientamento ? "bg-emerald-600" : "bg-slate-300 dark:bg-slate-700"
            }`}
          >
            <span
              className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform ${
                correggiOrientamento ? "translate-x-[22px]" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
    </div>
  );
}
