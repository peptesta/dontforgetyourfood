import { useState } from "react";
import { Link } from "react-router-dom";
import type { ReceiptLine, ReceiptParseResult } from "../api/receipts";

interface Props {
  result: ReceiptParseResult;
  onRetake: () => void;
}

/** Risultato dello Step 1: righe lette dallo scontrino, già ripulite dai doppioni e
 * abbinate al catalogo. Per ora è di sola lettura (si può solo scartare una riga):
 * quantità, scadenze e inserimento in dispensa sono gli Step successivi. */
export default function ReceiptResultPage({ result, onRetake }: Props) {
  const [discarded, setDiscarded] = useState<Set<string>>(new Set());
  const rows = result.righe.filter((r) => !discarded.has(r.id));
  const uncertain = rows.filter((r) => r.incerto).length;

  const warnings: string[] = [
    ...result.giunture_senza_sovrapposizione.map(
      (k) => `Nessuna riga in comune tra le foto ${k + 1} e ${k + 2}: potresti aver saltato dei prodotti.`,
    ),
    ...result.foto_senza_righe.map((k) => `Dalla foto ${k + 1} non è stato letto nessun prodotto.`),
    ...result.foto_con_errore.map((k) => `La foto ${k + 1} non è stata elaborata.`),
  ];

  return (
    <div className="mx-auto flex min-h-svh max-w-lg flex-col px-4 pb-28">
      <header className="py-4">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Prodotti letti</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {rows.length} prodott{rows.length === 1 ? "o" : "i"}
          {uncertain > 0 && ` · ${uncertain} da verificare`}
        </p>
      </header>

      {warnings.length > 0 && (
        <ul className="mb-3 flex flex-col gap-1 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">
          {warnings.map((w) => (
            <li key={w}>⚠ {w}</li>
          ))}
        </ul>
      )}

      {rows.length === 0 && (
        <p className="py-8 text-center text-slate-500 dark:text-slate-400">
          Nessun prodotto riconosciuto. Riprova con foto più nitide e dritte.
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {rows.map((row) => (
          <LineRow key={row.id} line={row} onDiscard={() => setDiscarded((prev) => new Set(prev).add(row.id))} />
        ))}
      </ul>

      <div className="fixed bottom-6 left-1/2 flex -translate-x-1/2 gap-2">
        <button
          type="button"
          onClick={onRetake}
          className="rounded-full border border-slate-300 bg-white px-5 py-3 font-medium text-slate-700 shadow-lg dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        >
          Rifai foto
        </button>
        <Link to="/" className="rounded-full bg-emerald-600 px-5 py-3 font-medium text-white shadow-lg hover:bg-emerald-700">
          Chiudi
        </Link>
      </div>
    </div>
  );
}

function LineRow({ line, onDiscard }: { line: ReceiptLine; onDiscard: () => void }) {
  return (
    <li className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="min-w-0 flex-1">
        <p className="font-medium text-slate-900 dark:text-slate-100">{line.nome}</p>
        {line.match ? (
          <p className="truncate text-xs text-emerald-700 dark:text-emerald-400">
            ≈ {line.match.label} ({Math.round(line.match.score)}%)
          </p>
        ) : (
          <p className="text-xs text-amber-700 dark:text-amber-400">Nessun abbinamento affidabile nel catalogo</p>
        )}
        <div className="mt-1 flex flex-wrap gap-1">
          {line.incerto && <Badge tone="amber">da verificare</Badge>}
          {line.possibile_doppione && <Badge tone="slate">possibile doppione</Badge>}
        </div>
      </div>
      {line.prezzo !== null && (
        <span className="shrink-0 text-sm tabular-nums text-slate-500 dark:text-slate-400">
          {line.prezzo.toFixed(2).replace(".", ",")} €
        </span>
      )}
      <button
        type="button"
        title="Scarta riga"
        onClick={onDiscard}
        className="shrink-0 rounded-lg p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950"
      >
        ✕
      </button>
    </li>
  );
}

function Badge({ tone, children }: { tone: "amber" | "slate"; children: string }) {
  const style =
    tone === "amber"
      ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
      : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300";
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${style}`}>{children}</span>;
}
