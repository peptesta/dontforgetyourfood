import { useEffect, useMemo, useRef, useState } from "react";
import { uploadBatch, type Batch, type PhotoPair } from "../api/batches";
import { previewDatePhoto } from "../api/ocr";
import CameraCaptureGrid, { type DatePreviewState } from "../components/CameraCaptureGrid";
import { useCameraStream } from "../hooks/useCameraStream";
import { guideToVideoRect } from "../lib/cameraCrop";

interface Props {
  onUploaded: (batch: Batch, pairs: PhotoPair[]) => void;
}

interface Shot {
  file: File;
  preview: string;
}

// stessa soglia già usata altrove (Review, pipeline lato server) per "bassa confidenza"
const DATE_PREVIEW_CONFIDENCE_THRESHOLD = 0.6;

export default function UploadPage({ onUploaded }: Props) {
  const { videoRef, error: cameraError } = useCameraStream();
  const guideRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [titleShot, setTitleShot] = useState<Shot | null>(null);
  const [dateShot, setDateShot] = useState<Shot | null>(null);
  const [datePreview, setDatePreview] = useState<DatePreviewState | null>(null);
  const [pairs, setPairs] = useState<PhotoPair[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pairPreviews = useMemo(() => pairs.map((p) => URL.createObjectURL(p.title)), [pairs]);
  useEffect(() => {
    return () => pairPreviews.forEach((src) => URL.revokeObjectURL(src));
  }, [pairPreviews]);

  const capture = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.videoWidth === 0) return;

    const slot: "titolo" | "data" = !titleShot ? "titolo" : "data";
    const guideEl = guideRef.current;
    const { sx, sy, sw, sh } = guideEl
      ? guideToVideoRect(video, guideEl)
      : { sx: 0, sy: 0, sw: video.videoWidth, sh: video.videoHeight };

    canvas.width = Math.max(1, Math.round(sw));
    canvas.height = Math.max(1, Math.round(sh));
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const file = new File([blob], `${slot}-${Date.now()}.jpg`, { type: "image/jpeg" });
        const preview = URL.createObjectURL(blob);
        if (slot === "titolo") {
          setTitleShot({ file, preview });
        } else {
          setDateShot({ file, preview });
          // anteprima OCR in tempo reale, solo per la data: dà un feedback immediato
          // ("data letta" o "rifai la foto") invece di scoprirlo solo a fine batch.
          setDatePreview({ status: "loading" });
          previewDatePhoto(file)
            .then((result) => {
              const isGood = !!result.data_candidata && (result.confidence ?? 0) >= DATE_PREVIEW_CONFIDENCE_THRESHOLD;
              setDatePreview(isGood ? { status: "ok", date: result.data_candidata! } : { status: "low" });
            })
            .catch(() => setDatePreview({ status: "low" }));
        }
      },
      "image/jpeg",
      0.92,
    );
  };

  const retake = (slot: "titolo" | "data") => {
    if (slot === "titolo" && titleShot) {
      URL.revokeObjectURL(titleShot.preview);
      setTitleShot(null);
    }
    if (slot === "data" && dateShot) {
      URL.revokeObjectURL(dateShot.preview);
      setDateShot(null);
      setDatePreview(null);
    }
  };

  const confirmPair = () => {
    if (!titleShot || !dateShot) return;
    setPairs((prev) => [...prev, { title: titleShot.file, date: dateShot.file }]);
    setTitleShot(null);
    setDateShot(null);
    setDatePreview(null);
  };

  const removePair = (index: number) => {
    setPairs((prev) => prev.filter((_, i) => i !== index));
  };

  const onSubmit = async () => {
    if (pairs.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const batch = await uploadBatch(pairs);
      onUploaded(batch, pairs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al subir");
      setSubmitting(false);
    }
  };

  return (
    // h-svh (non min-h-svh) + flex-1 sul preview fotocamera: l'intera UI di cattura
    // occupa esattamente l'altezza disponibile invece di poterla superare, così sta
    // su uno schermo come quello di un iPhone 11 senza bisogno di scroll.
    <div className="mx-auto flex h-svh max-w-lg flex-col overflow-hidden px-4 pb-3 pt-3">
      <h1 className="shrink-0 text-lg font-semibold text-slate-900 dark:text-slate-100">Añadir productos</h1>
      <p className="mt-0.5 shrink-0 text-xs text-slate-500 dark:text-slate-400">
        Haz primero la foto del título y luego la de la fecha de caducidad. Confirma para pasar al siguiente producto.
      </p>

      <div className="mt-2 flex min-h-0 flex-1 flex-col">
        <CameraCaptureGrid
          videoRef={videoRef}
          guideRef={guideRef}
          titleShot={titleShot}
          dateShot={dateShot}
          datePreview={datePreview}
          onCapture={capture}
          onRetake={retake}
          onConfirmPair={confirmPair}
          cameraError={cameraError}
        />
      </div>
      <canvas ref={canvasRef} className="hidden" />

      {pairs.length > 0 && (
        <div className="mt-2 shrink-0">
          <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
            {pairs.length} producto{pairs.length === 1 ? "" : "s"} listo{pairs.length === 1 ? "" : "s"}
          </p>
          {/* riga a scorrimento orizzontale, altezza fissa: con molti prodotti in coda
              non deve far crescere la pagina in verticale */}
          <div className="mt-1 flex gap-2 overflow-x-auto">
            {pairPreviews.map((src, i) => (
              <div key={src} className="relative h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-slate-100 dark:bg-slate-800">
                <img src={src} alt="" className="h-full w-full object-cover" />
                <button
                  type="button"
                  onClick={() => removePair(i)}
                  className="absolute right-0.5 top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-black/60 text-[10px] text-white"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <p className="mt-1 shrink-0 text-xs text-red-600">{error}</p>}

      <button
        type="button"
        onClick={onSubmit}
        disabled={pairs.length === 0 || submitting}
        className="mt-2 w-full shrink-0 rounded-full bg-emerald-600 py-2.5 font-medium text-white shadow-lg transition hover:bg-emerald-700 disabled:opacity-50"
      >
        {submitting ? "Subiendo…" : `Enviar (${pairs.length})`}
      </button>
    </div>
  );
}
