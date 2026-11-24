import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nome, setNome] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(email, password, nome, inviteCode);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear la cuenta");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-svh max-w-sm flex-col justify-center gap-6 px-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Crea una cuenta</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Deja vacío el código de invitación para crear una nueva despensa, o introdúcelo para unirte a
          la de otra persona.
        </p>
      </div>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <input
          type="text"
          placeholder="Tu nombre"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base outline-none focus:border-emerald-500 dark:border-slate-700 dark:bg-slate-800"
        />
        <input
          type="email"
          required
          autoComplete="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base outline-none focus:border-emerald-500 dark:border-slate-700 dark:bg-slate-800"
        />
        <input
          type="password"
          required
          minLength={8}
          autoComplete="new-password"
          placeholder="Contraseña (mín. 8 caracteres)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base outline-none focus:border-emerald-500 dark:border-slate-700 dark:bg-slate-800"
        />
        <input
          type="text"
          placeholder="Código de invitación (opcional)"
          value={inviteCode}
          onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base uppercase outline-none focus:border-emerald-500 dark:border-slate-700 dark:bg-slate-800"
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-emerald-600 px-4 py-2.5 font-medium text-white transition hover:bg-emerald-700 disabled:opacity-50"
        >
          {loading ? "Creando…" : "Crear cuenta"}
        </button>
      </form>
      <p className="text-center text-sm text-slate-500 dark:text-slate-400">
        ¿Ya tienes una cuenta?{" "}
        <Link to="/login" className="font-medium text-emerald-600 underline">
          Entrar
        </Link>
      </p>
    </div>
  );
}
