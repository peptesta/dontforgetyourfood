interface Props {
  onClose: () => void;
  onTakePhoto: () => void;
}

/** Bottom sheet per scegliere come caricare lo scontrino. Oggi è attiva solo la foto;
 * immagine e documento sono previsti ma non ancora implementati. */
export default function ReceiptSourceSheet({ onClose, onTakePhoto }: Props) {
  return (
    <div className="fixed inset-0 z-20 flex items-end justify-center bg-black/50" onClick={onClose}>
      <div
        role="dialog"
        aria-label="Subir ticket"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-t-2xl bg-white p-4 pb-8 dark:bg-slate-900"
      >
        <h2 className="mb-3 text-base font-semibold text-slate-900 dark:text-slate-100">Subir ticket</h2>
        <div className="flex flex-col gap-2">
          <SourceOption icon="📷" label="Hacer foto" hint="También varias fotos, para tickets largos" onClick={onTakePhoto} />
          <SourceOption icon="🖼" label="Subir imagen" hint="Próximamente" disabled />
          <SourceOption icon="📄" label="Subir documento" hint="Próximamente" disabled />
        </div>
        <button
          type="button"
          onClick={onClose}
          className="mt-3 w-full rounded-lg py-2 text-sm text-slate-500 dark:text-slate-400"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}

function SourceOption({
  icon,
  label,
  hint,
  onClick,
  disabled,
}: {
  icon: string;
  label: string;
  hint: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-left disabled:opacity-50 dark:border-slate-700"
    >
      <span className="text-2xl">{icon}</span>
      <span>
        <span className="block font-medium text-slate-900 dark:text-slate-100">{label}</span>
        <span className="block text-xs text-slate-500 dark:text-slate-400">{hint}</span>
      </span>
    </button>
  );
}
