import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";
import type { Batch } from "../api/batches";

/**
 * Legge lo stream SSE di un batch. Usa fetch + ReadableStream invece del nativo
 * EventSource perché EventSource non supporta l'header Authorization: il backend
 * richiede il Bearer token come ogni altro endpoint autenticato.
 */
export function useBatchStream(batchId: string | null): { batch: Batch | null; error: string | null } {
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!batchId) return;

    const controller = new AbortController();

    (async () => {
      try {
        const response = await apiFetch(`/batches/${batchId}/stream`, {
          headers: { Accept: "text/event-stream" },
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          throw new Error(`Flujo no disponible (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        const applyEvent = (rawEvent: string) => {
          const dataLine = rawEvent.split("\n").find((line) => line.startsWith("data:"));
          if (!dataLine) return; // righe di keep-alive (": ping ...") non hanno "data:"
          try {
            setBatch(JSON.parse(dataLine.slice(5).trim()) as Batch);
          } catch {
            // riga malformata: ignorata, la prossima porterà lo stato aggiornato
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          // Uvicorn/sse-starlette terminano le righe con \r\n, non \n: si normalizza
          // subito così lo split su eventi/righe funziona indipendentemente dal server.
          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
          const rawEvents = buffer.split("\n\n");
          buffer = rawEvents.pop() ?? "";
          rawEvents.forEach(applyEvent);
        }
        // Se il server chiude la connessione senza una riga vuota finale dopo
        // l'ultimo evento (es. "completato"), il residuo va comunque elaborato.
        if (buffer.trim()) applyEvent(buffer);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError(err instanceof Error ? err.message : "Error en el flujo");
        }
      }
    })();

    return () => controller.abort();
  }, [batchId]);

  return { batch, error };
}
