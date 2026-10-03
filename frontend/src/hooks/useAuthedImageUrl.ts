import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

/**
 * Carica un'immagine che richiede il Bearer token (endpoint autenticati come
 * /products/:id/foto-titolo) e la espone come blob: URL utilizzabile in <img src>.
 * Necessario perché <img src="..."> non può inviare header custom — stesso motivo
 * per cui useBatchStream usa fetch invece del nativo EventSource.
 */
export function useAuthedImageUrl(path: string | null): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!path) {
      setUrl(null);
      return;
    }
    let objectUrl: string | null = null;
    let cancelled = false;

    apiFetch(path)
      .then((res) => (res.ok ? res.blob() : Promise.reject(new Error(`${res.status}`))))
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setUrl(null);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  return url;
}
