import { apiFetch, apiJson } from "./client";

export interface PhotoPair {
  title: File;
  date: File;
}

export interface BatchItem {
  id: string;
  ordine_upload: number;
  // "in_coda" | "in_elaborazione" | "completato" | "parziale" | "errore"
  stato: string;
  nome_candidato: string | null;
  nome_suggerito: string | null;
  data_candidata: string | null;
  data_candidati_alternativi: string[] | null;
  ocr_raw_text_titolo: string | null;
  ocr_raw_text_data: string | null;
  confidence_titolo: number | null;
  confidence_data: number | null;
  errore_titolo: string | null;
  errore_data: string | null;
  confermato: boolean;
}

export interface Batch {
  id: string;
  stato: string;
  creato_il: string;
  totale_prodotti: number;
  completate: number;
  items: BatchItem[];
}

export async function uploadBatch(pairs: PhotoPair[]): Promise<Batch> {
  const formData = new FormData();
  pairs.forEach((pair) => {
    formData.append("title_files", pair.title);
    formData.append("date_files", pair.date);
  });
  const response = await apiFetch("/batches", { method: "POST", body: formData });
  if (!response.ok) {
    throw new Error(`Caricamento fallito (${response.status})`);
  }
  return response.json();
}

export function getBatch(id: string): Promise<Batch> {
  return apiJson(`/batches/${id}`);
}

export interface ConfirmItem {
  batch_item_id: string;
  nome: string;
  data_scadenza: string;
}

export interface ConfirmResponse {
  products: { batch_item_id: string; product_id: string }[];
}

export function confirmBatch(id: string, items: ConfirmItem[]): Promise<ConfirmResponse> {
  return apiJson(`/batches/${id}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
}
