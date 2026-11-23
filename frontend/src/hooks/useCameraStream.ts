import { useEffect, useRef, useState, type RefObject } from "react";

/**
 * Richiede lo stream della fotocamera posteriore una sola volta e lo collega a un
 * elemento <video>. Chiamato una sola volta per l'intera sessione di cattura (in
 * UploadPage), non per ogni scatto/prodotto: lo stream resta attivo mentre l'utente
 * passa da un prodotto al successivo.
 */
export function useCameraStream(): { videoRef: RefObject<HTMLVideoElement | null>; error: string | null } {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;

    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      })
      .then((s) => {
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Cámara no disponible");
      });

    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { videoRef, error };
}
