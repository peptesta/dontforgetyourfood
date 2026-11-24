import { apiFetch } from "./client";

export interface DatePreviewResult {
  data_candidata: string | null;
  confidence: number | null;
  data_candidati_alternativi: string[] | null;
  errore: string | null;
}

/** Anteprima OCR in tempo reale sulla sola foto della data, chiamata subito dopo lo
 * scatto (prima della conferma del prodotto) per dare un feedback immediato — non
 * sostituisce la lettura definitiva che avviene comunque in POST /batches. */
export async function previewDatePhoto(file: File): Promise<DatePreviewResult> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiFetch("/ocr/date-preview", { method: "POST", body: formData });
  if (!response.ok) throw new Error(`Vista previa fallida (${response.status})`);
  return response.json();
}
