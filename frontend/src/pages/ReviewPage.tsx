import { format } from "date-fns";
import { useMemo, useState } from "react";
import { confirmBatch, type Batch, type BatchItem, type ConfirmItem, type PhotoPair } from "../api/batches";

interface Props {
  batch: Batch;
  pairs: PhotoPair[];
  onConfirmed: () => void;
}

interface DraftItem {
  include: boolean;
  nome: string;
  dataScadenza: string;
}

export default function ReviewPage({ batch, pairs, onConfirmed }: Props) {
  // Le foto non sono mai salvate/rinviate dal backend: per la Review si riusano
  // gli stessi File già in memoria del browser dall'UploadPage.
  const titlePreviews = useMemo(() => pairs.map((p) => URL.createObjectURL(p.title)), [pairs]);
  const datePreviews = useMemo(() => pairs.map((p) => URL.createObjectURL(p.date)), [pairs]);

  const [drafts, setDrafts] = useState<Record<string, DraftItem>>(() => {
    const initial: Record<string, DraftItem> = {};
    for (const item of batch.items) {
      initial[item.id] = {
        include: item.stato === "completato",
        nome: item.nome_candidato ?? "",
        dataScadenza: item.data_candidata ?? "",
      };
    }
    return initial;
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateDraft = (itemId: string, patch: Partial<DraftItem>) => {
    setDrafts((prev) => ({ ...prev, [itemId]: { ...prev[itemId], ...patch } }));
  };

  const onSubmit = async () => {
    const items: ConfirmItem[] = batch.items
      .filter((item) => drafts[item.id]?.include && drafts[item.id]?.nome && drafts[item.id]?.dataScadenza)
      .map((item) => ({
        batch_item_id: item.id,
        nome: drafts[item.id].nome,
        data_scadenza: drafts[item.id].dataScadenza,
      }));
    if (items.length === 0) {
      setError("Selecciona al menos un producto con nombre y fecha válidos.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await confirmBatch(batch.id, items);
      onConfirmed();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo confirmar");
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-svh max-w-lg flex-col px-4 pb-28 pt-4">
      <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Revisa los resultados</h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Corrige el nombre o la fecha donde haga falta y desmarca lo que no quieras guardar.
      </p>

      <ul className="mt-4 flex flex-col gap-4">
        {batch.items.map((item) => (
          <ReviewCard
            key={item.id}
            item={item}
            titlePreview={titlePreviews[item.ordine_upload]}
            datePreview={datePreviews[item.ordine_upload]}
            draft={drafts[item.id]}
            onChange={(patch) => updateDraft(item.id, patch)}
          />
        ))}
      </ul>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <button
        type="button"
        onClick={onSubmit}
        disabled={submitting}
        className="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-full bg-emerald-600 px-6 py-3 font-medium text-white shadow-lg transition hover:bg-emerald-700 disabled:opacity-50"
      >
        {submitting ? "Guardando…" : "Confirmar y guardar"}
      </button>
    </div>
  );
}

function ReviewCard({
  item,
  titlePreview,
  datePreview,
  draft,
  onChange,
}: {
  item: BatchItem;
  titlePreview: string | undefined;
  datePreview: string | undefined;
  draft: DraftItem;
  onChange: (patch: Partial<DraftItem>) => void;
}) {
  const titleFailed = !!item.errore_titolo;
  const dateFailed = !!item.errore_data;
  const fullyFailed = item.stato === "errore";
  const lowConfidence = Math.min(item.confidence_titolo ?? 1, item.confidence_data ?? 1) < 0.6;
  const hasSuggestion = !!item.nome_suggerito && item.nome_suggerito !== draft.nome;

  return (
    <li
      className={`rounded-xl border p-3 dark:border-slate-800 ${
        draft.include
          ? "border-slate-200 bg-white dark:bg-slate-900"
          : "border-slate-100 bg-slate-50 opacity-60 dark:bg-slate-900/40"
      }`}
    >
      <div className="flex gap-3">
        <div className="flex shrink-0 gap-1.5">
          {titlePreview && <img src={titlePreview} alt="Título" className="h-20 w-20 rounded-lg object-cover" />}
          {datePreview && <img src={datePreview} alt="Fecha de caducidad" className="h-20 w-20 rounded-lg object-cover" />}
        </div>
        <div className="min-w-0 flex-1">
          {fullyFailed ? (
            <p className="text-sm text-red-600">No reconocido</p>
          ) : (
            <>
              {titleFailed && <p className="text-xs text-red-600">Título no reconocido: {item.errore_titolo}</p>}
              <input
                type="text"
                value={draft.nome}
                onChange={(e) => onChange({ nome: e.target.value })}
                placeholder="Nombre del producto"
                className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
              />
              {hasSuggestion && (
                <button
                  type="button"
                  onClick={() => onChange({ nome: item.nome_suggerito ?? draft.nome })}
                  className="mt-1.5 rounded-full border border-emerald-400 px-2 py-0.5 text-xs text-emerald-700 dark:border-emerald-700 dark:text-emerald-400"
                >
                  Quizás: {item.nome_suggerito}
                </button>
              )}

              {dateFailed && <p className="mt-2 text-xs text-red-600">Fecha no reconocida: {item.errore_data}</p>}
              <input
                type="date"
                value={draft.dataScadenza}
                onChange={(e) => onChange({ dataScadenza: e.target.value })}
                className="mt-2 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
              />
              {item.data_candidati_alternativi && item.data_candidati_alternativi.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {item.data_candidati_alternativi.map((alt) => (
                    <button
                      key={alt}
                      type="button"
                      onClick={() => onChange({ dataScadenza: alt })}
                      className="rounded-full border border-slate-300 px-2 py-0.5 text-xs text-slate-600 dark:border-slate-700 dark:text-slate-300"
                    >
                      {format(new Date(alt), "d/MM/yyyy")}
                    </button>
                  ))}
                </div>
              )}
              {lowConfidence && (
                <p className="mt-1 text-xs text-amber-600">Poca fiabilidad: revisa los datos.</p>
              )}
            </>
          )}
        </div>
        <label className="flex shrink-0 items-start pt-1">
          <input
            type="checkbox"
            checked={draft.include}
            onChange={(e) => onChange({ include: e.target.checked })}
            disabled={fullyFailed}
          />
        </label>
      </div>
    </li>
  );
}
