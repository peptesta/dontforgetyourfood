import { format, parseISO } from "date-fns";
import { it } from "date-fns/locale";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Product } from "../api/products";
import ExpiryBadge from "../components/ExpiryBadge";
import ReceiptSourceSheet from "../components/ReceiptSourceSheet";
import { useAuth } from "../context/AuthContext";
import { useAuthedImageUrl } from "../hooks/useAuthedImageUrl";
import { useConsumeProduct, useDeleteProduct, useProducts } from "../hooks/useProducts";

export default function PantryListPage() {
  const { user, logout } = useAuth();
  const { data: products, isLoading, error } = useProducts();
  const consumeProduct = useConsumeProduct();
  const deleteProduct = useDeleteProduct();
  const [showInvite, setShowInvite] = useState(false);
  const [showReceiptSheet, setShowReceiptSheet] = useState(false);
  const navigate = useNavigate();

  return (
    <div className="mx-auto flex min-h-svh max-w-lg flex-col px-4 pb-28">
      <header className="flex items-center justify-between py-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">La tua dispensa</h1>
          {user && <p className="text-sm text-slate-500 dark:text-slate-400">{user.email}</p>}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowInvite((v) => !v)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300"
          >
            Invita
          </button>
          <Link
            to="/settings"
            title="Impostazioni"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300"
          >
            ⚙
          </Link>
          <button
            onClick={() => logout()}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300"
          >
            Esci
          </button>
        </div>
      </header>

      {showInvite && user && (
        <div className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
          Condividi questo codice con chi vuoi che veda la stessa dispensa:{" "}
          <span className="font-mono font-semibold">{user.household_invite_code}</span>
        </div>
      )}

      {isLoading && <p className="text-slate-500">Caricamento…</p>}
      {error && <p className="text-red-600">Errore nel caricamento dei prodotti.</p>}

      {products && products.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-slate-500 dark:text-slate-400">
          <p>La dispensa è vuota.</p>
          <p className="text-sm">Scatta qualche foto dopo la spesa per iniziare a tracciare le scadenze.</p>
        </div>
      )}

      <ul className="flex flex-col gap-2">
        {products?.map((product) => (
          <ProductRow
            key={product.id}
            product={product}
            onConsume={() => consumeProduct.mutate(product.id)}
            onDelete={() => deleteProduct.mutate(product.id)}
          />
        ))}
      </ul>

      <div className="fixed bottom-6 left-1/2 flex -translate-x-1/2 gap-2">
        <Link
          to="/batch"
          className="whitespace-nowrap rounded-full bg-emerald-600 px-5 py-3 font-medium text-white shadow-lg transition hover:bg-emerald-700"
        >
          + Aggiungi foto
        </Link>
        <button
          type="button"
          onClick={() => setShowReceiptSheet(true)}
          className="whitespace-nowrap rounded-full border border-emerald-600 bg-white px-5 py-3 font-medium text-emerald-700 shadow-lg transition hover:bg-emerald-50 dark:bg-slate-900 dark:text-emerald-400 dark:hover:bg-slate-800"
        >
          🧾 Carica scontrino
        </button>
      </div>

      {showReceiptSheet && (
        <ReceiptSourceSheet
          onClose={() => setShowReceiptSheet(false)}
          onTakePhoto={() => navigate("/receipt")}
        />
      )}
    </div>
  );
}

function ProductRow({
  product,
  onConsume,
  onDelete,
}: {
  product: Product;
  onConsume: () => void;
  onDelete: () => void;
}) {
  const thumbUrl = useAuthedImageUrl(product.foto_titolo_key ? `/products/${product.id}/foto-titolo` : null);

  return (
    <li className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      {thumbUrl ? (
        <img src={thumbUrl} alt="" className="h-12 w-12 shrink-0 rounded-lg object-cover" />
      ) : (
        <div className="h-12 w-12 shrink-0 rounded-lg bg-slate-100 dark:bg-slate-800" />
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-slate-900 dark:text-slate-100">{product.nome}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {format(parseISO(product.data_scadenza), "d MMMM yyyy", { locale: it })}
        </p>
      </div>
      <ExpiryBadge dataScadenza={product.data_scadenza} />
      <div className="flex shrink-0 gap-1">
        <button
          title="Segna come consumato"
          onClick={onConsume}
          className="rounded-lg p-2 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950"
        >
          ✓
        </button>
        <button
          title="Elimina"
          onClick={onDelete}
          className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950"
        >
          ✕
        </button>
      </div>
    </li>
  );
}
