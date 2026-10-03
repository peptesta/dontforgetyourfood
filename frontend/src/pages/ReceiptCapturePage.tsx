import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { parseReceipt, type ReceiptParseResult } from "../api/receipts";
import { useCameraStream } from "../hooks/useCameraStream";
import { guideToVideoRect } from "../lib/cameraCrop";

interface Props {
  onParsed: (result: ReceiptParseResult) => void;
}

// quanta parte bassa dell'ultima foto mostrare in trasparenza sopra la colonna, per
// aiutare l'utente a includere le ultime righe già scattate nella foto successiva
const OVERLAP_HINT_FRACTION = 0.2;

/** Cattura di uno o più scatti della colonna prodotti dello scontrino. Gli scatti
 * restano in memoria locale fino a "Fine": solo allora vengono inviati al server. */
export default function ReceiptCapturePage({ onParsed }: Props) {
  const { videoRef, error: cameraError } = useCameraStream();
  const guideRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [shots, setShots] = useState<File[]>([]);
  const [overlapHint, setOverlapHint] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const previews = useMemo(() => shots.map((f) => URL.createObjectURL(f)), [shots]);
  useEffect(() => () => previews.forEach((src) => URL.revokeObjectURL(src)), [previews]);

  const capture = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const guideEl = guideRef.current;
    if (!video || !canvas || !guideEl || video.videoWidth === 0) return;

    const { sx, sy, sw, sh } = guideToVideoRect(video, guideEl);
    canvas.width = Math.max(1, Math.round(sw));
    canvas.height = Math.max(1, Math.round(sh));
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);

    // fascia bassa dell'ultimo scatto, mostrata sopra la colonna per allineare il prossimo
    const stripHeight = Math.max(1, Math.round(canvas.height * OVERLAP_HINT_FRACTION));
    const strip = document.createElement("canvas");
    strip.width = canvas.width;
    strip.height = stripHeight;
    strip.getContext("2d")?.drawImage(canvas, 0, canvas.height - stripHeight, canvas.width, stripHeight, 0, 0, canvas.width, stripHeight);
    const hint = strip.toDataURL("image/jpeg", 0.7);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        setShots((prev) => [...prev, new File([blob], `scontrino-${prev.length + 1}-${Date.now()}.jpg`, { type: "image/jpeg" })]);
        setOverlapHint(hint);
      },
      "image/jpeg",
      0.92,
    );
  };

  const removeShot = (index: number) => {
    setShots((prev) => prev.filter((_, i) => i !== index));
    // l'ultimo scatto è cambiato: la fascia di aiuto non è più valida
    setOverlapHint(null);
  };

  const onDone = async () => {
    if (shots.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      onParsed(await parseReceipt(shots));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lettura fallita");
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex h-svh max-w-lg flex-col overflow-hidden px-4 pb-3 pt-3">
      <div className="flex shrink-0 items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Carica scontrino</h1>
        <Link to="/" className="text-sm text-slate-500 dark:text-slate-400">
          Annulla
        </Link>
      </div>
      <p className="mt-0.5 shrink-0 text-xs text-slate-500 dark:text-slate-400">
        Inquadra la colonna con nomi e prezzi dei prodotti. Per scontrini lunghi scatta più foto, andando verso il
        basso e ripetendo le ultime 2-3 righe.
      </p>

      <div className="relative mt-2 min-h-[140px] flex-1 overflow-hidden rounded-xl bg-black">
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />
        {/* la colonna guida: il box-shadow gigante scurisce tutto ciò che sta fuori */}
        <div
          ref={guideRef}
          className="pointer-events-none absolute inset-x-[16%] inset-y-[3%] rounded-lg border-2 border-dashed border-white/90 shadow-[0_0_0_9999px_rgba(0,0,0,0.55)]"
        >
          {overlapHint && (
            <img src={overlapHint} alt="" className="absolute inset-x-0 top-0 w-full opacity-40" />
          )}
          <span className="absolute -top-0 left-1/2 -translate-x-1/2 translate-y-1 rounded bg-black/60 px-2 py-0.5 text-[11px] font-medium text-white">
            {shots.length === 0 ? "Nomi e prezzi qui dentro" : "Allinea con le ultime righe"}
          </span>
        </div>
      </div>
      <canvas ref={canvasRef} className="hidden" />

      {shots.length > 0 && (
        <div className="mt-2 shrink-0">
          <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
            {shots.length} foto scattat{shots.length === 1 ? "a" : "e"}
          </p>
          <div className="mt-1 flex gap-2 overflow-x-auto">
            {previews.map((src, i) => (
              <div key={src} className="relative h-14 w-10 shrink-0 overflow-hidden rounded-lg bg-slate-100 dark:bg-slate-800">
                <img src={src} alt={`Foto ${i + 1}`} className="h-full w-full object-cover" />
                <button
                  type="button"
                  onClick={() => removeShot(i)}
                  aria-label={`Rimuovi foto ${i + 1}`}
                  className="absolute right-0.5 top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-black/60 text-[10px] text-white"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {(cameraError || error) && <p className="mt-1 shrink-0 text-xs text-red-600">{cameraError ?? error}</p>}

      <div className="mt-2 flex shrink-0 items-center justify-center gap-4">
        <button
          type="button"
          onClick={capture}
          disabled={!!cameraError || submitting}
          aria-label="Scatta foto"
          className="h-12 w-12 rounded-full border-4 border-slate-300 bg-white shadow-lg transition active:scale-95 disabled:opacity-50 dark:border-slate-700"
        />
        <button
          type="button"
          onClick={onDone}
          disabled={shots.length === 0 || submitting}
          className="rounded-full bg-emerald-600 px-6 py-2.5 font-medium text-white shadow-lg transition hover:bg-emerald-700 disabled:opacity-50"
        >
          {submitting ? "Lettura…" : `Fine (${shots.length})`}
        </button>
      </div>
    </div>
  );
}
