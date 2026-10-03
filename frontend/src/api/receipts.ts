import { apiFetch } from "./client";

export interface CatalogMatch {
  label: string;
  brand: string;
  name: string;
  score: number;
  fresco: boolean | null;
}

export interface ReceiptLine {
  /** id stabile generato lato client: Step 2 si riferisce alle righe per id, non per posizione. */
  id: string;
  ordine: number;
  nome: string;
  prezzo: number | null;
  confidence: number;
  foto: number;
  /** quante righe dello scontrino erano questo prodotto (ripetizioni fuse in una). */
  occorrenze: number;
  match: CatalogMatch | null;
  candidati: CatalogMatch[];
  incerto: boolean;
}

export interface ReceiptParseResult {
  righe: ReceiptLine[];
  giunture_senza_sovrapposizione: number[];
  foto_senza_righe: number[];
  foto_con_errore: number[];
  /** nomi delle righe escluse perché non alimentari. */
  non_alimentari_scartati: string[];
}

type RawReceiptLine = Omit<ReceiptLine, "id">;

/** Legge i prodotti dalle foto (in ordine di scatto) della colonna prodotti dello
 * scontrino. Stateless lato server: niente viene salvato. */
export async function parseReceipt(files: File[]): Promise<ReceiptParseResult> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const response = await apiFetch("/receipts/parse", { method: "POST", body: formData });
  if (!response.ok) throw new Error(`Lettura scontrino fallita (${response.status})`);
  const data: Omit<ReceiptParseResult, "righe"> & { righe: RawReceiptLine[] } = await response.json();
  const batchId = Date.now().toString(36);
  return { ...data, righe: data.righe.map((r) => ({ ...r, id: `${batchId}-${r.ordine}` })) };
}
