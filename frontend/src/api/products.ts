import { apiJson } from "./client";

export interface Product {
  id: string;
  nome: string;
  data_scadenza: string;
  data_aggiunta: string;
  stato: string;
  added_by_user_id: string | null;
  ocr_confidence: number | null;
  foto_titolo_key: string | null;
}

export function listProducts(stato = "attivo"): Promise<Product[]> {
  return apiJson(`/products?stato=${encodeURIComponent(stato)}`);
}

export function updateProduct(
  id: string,
  data: { nome?: string; data_scadenza?: string },
): Promise<Product> {
  return apiJson(`/products/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function consumeProduct(id: string): Promise<Product> {
  return apiJson(`/products/${id}/consume`, { method: "POST" });
}

export function deleteProduct(id: string): Promise<void> {
  return apiJson(`/products/${id}`, { method: "DELETE" });
}
