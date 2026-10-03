import { format, parseISO } from "date-fns";
import type { RefObject } from "react";

interface Shot {
  file: File;
  preview: string;
}

export type DatePreviewState = { status: "loading" } | { status: "ok"; date: string } | { status: "low" };

interface Props {
  videoRef: RefObject<HTMLVideoElement | null>;
  guideRef: RefObject<HTMLDivElement | null>;
  titleShot: Shot | null;
  dateShot: Shot | null;
  datePreview: DatePreviewState | null;
  onCapture: () => void;
  onRetake: (slot: "titolo" | "data") => void;
  onConfirmPair: () => void;
  cameraError: string | null;
}

export default function CameraCaptureGrid({
  videoRef,
  guideRef,
  titleShot,
  dateShot,
  datePreview,
  onCapture,
  onRetake,
  onConfirmPair,
  cameraError,
}: Props) {
  const bothFilled = !!titleShot && !!dateShot;
  const nextLabel = !titleShot ? "Titolo" : "F. Cad.";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* flex-1 invece di un aspect-ratio fisso: il preview riempie lo spazio verticale
          rimasto dopo header/griglia/bottoni, così l'intera UI di cattura sta dentro
          uno schermo come quello di un iPhone 11 senza bisogno di scroll. */}
      <div className="relative min-h-[140px] flex-1 overflow-hidden rounded-xl bg-black">
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />
        {!bothFilled && (
          <div
            ref={guideRef}
            className="pointer-events-none absolute inset-x-[10%] top-1/2 h-1/3 -translate-y-1/2 rounded-lg border-2 border-dashed border-white/80"
          >
            <span className="absolute -top-6 left-0 rounded bg-black/60 px-2 py-0.5 text-xs font-medium text-white">
              {nextLabel}: tieni il testo dentro il riquadro
            </span>
          </div>
        )}
      </div>

      <div className="mt-2 grid shrink-0 grid-cols-2 gap-2">
        <GridSlot label="Titolo" shot={titleShot} active={!titleShot} onRetake={() => onRetake("titolo")} />
        <GridSlot
          label="F. Cad."
          shot={dateShot}
          active={!!titleShot && !dateShot}
          onRetake={() => onRetake("data")}
          preview={datePreview}
        />
      </div>

      {cameraError && <p className="mt-1 shrink-0 text-xs text-red-600">{cameraError}</p>}

      <div className="mt-2 flex shrink-0 justify-center">
        {bothFilled ? (
          <button
            type="button"
            onClick={onConfirmPair}
            className="rounded-full bg-emerald-600 px-6 py-2.5 font-medium text-white shadow-lg transition hover:bg-emerald-700"
          >
            Conferma prodotto
          </button>
        ) : (
          <button
            type="button"
            onClick={onCapture}
            disabled={!!cameraError}
            aria-label="Scatta foto"
            className="h-12 w-12 rounded-full border-4 border-slate-300 bg-white shadow-lg transition active:scale-95 disabled:opacity-50 dark:border-slate-700"
          />
        )}
      </div>
    </div>
  );
}

function GridSlot({
  label,
  shot,
  active,
  onRetake,
  preview,
}: {
  label: string;
  shot: Shot | null;
  active: boolean;
  onRetake: () => void;
  preview?: DatePreviewState | null;
}) {
  return (
    <div
      className={`relative flex h-20 items-center justify-center overflow-hidden rounded-lg border-2 bg-slate-100 dark:bg-slate-800 ${
        active ? "border-emerald-500" : "border-slate-200 dark:border-slate-700"
      }`}
    >
      {shot ? (
        <>
          <img src={shot.preview} alt={label} className="h-full w-full object-cover" />
          <button
            type="button"
            onClick={onRetake}
            className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-black/60 text-xs text-white"
          >
            ✕
          </button>
          {preview && <DatePreviewBadge preview={preview} />}
        </>
      ) : (
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</span>
      )}
    </div>
  );
}

function DatePreviewBadge({ preview }: { preview: DatePreviewState }) {
  if (preview.status === "loading") {
    return (
      <span className="absolute inset-x-0 bottom-0 truncate bg-black/60 px-1.5 py-0.5 text-center text-[10px] font-medium text-white">
        Verifica…
      </span>
    );
  }
  if (preview.status === "ok") {
    return (
      <span className="absolute inset-x-0 bottom-0 truncate bg-emerald-600/90 px-1.5 py-0.5 text-center text-[10px] font-medium text-white">
        ✓ {format(parseISO(preview.date), "d/MM/yyyy")}
      </span>
    );
  }
  return (
    <span className="absolute inset-x-0 bottom-0 truncate bg-amber-600/90 px-1.5 py-0.5 text-center text-[10px] font-medium text-white">
      ⚠ rifai la foto
    </span>
  );
}
