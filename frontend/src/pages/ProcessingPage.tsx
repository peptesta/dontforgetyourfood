import { useEffect } from "react";
import type { Batch } from "../api/batches";
import { useBatchStream } from "../hooks/useBatchStream";

interface Props {
  batchId: string;
  onDone: (batch: Batch) => void;
}

export default function ProcessingPage({ batchId, onDone }: Props) {
  const { batch, error } = useBatchStream(batchId);

  useEffect(() => {
    if (batch?.stato === "completato") {
      onDone(batch);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch?.stato]);

  const total = batch?.totale_prodotti ?? 0;
  const done = batch?.completate ?? 0;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div className="mx-auto flex min-h-svh max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Riconoscimento in corso…</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        {done} di {total} prodotti elaborati
      </p>
      <div className="h-2 w-full max-w-xs overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <div className="h-full rounded-full bg-emerald-600 transition-all" style={{ width: `${percent}%` }} />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
