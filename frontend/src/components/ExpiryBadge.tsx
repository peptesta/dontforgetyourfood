import { differenceInCalendarDays, parseISO } from "date-fns";

export default function ExpiryBadge({ dataScadenza }: { dataScadenza: string }) {
  const days = differenceInCalendarDays(parseISO(dataScadenza), new Date());

  let label: string;
  let className: string;
  if (days < 0) {
    label = "Scaduto";
    className = "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300";
  } else if (days === 0) {
    label = "Scade oggi";
    className = "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300";
  } else if (days === 1) {
    label = "Scade domani";
    className = "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300";
  } else if (days <= 3) {
    label = `Scade tra ${days} giorni`;
    className = "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300";
  } else {
    label = `Scade tra ${days} giorni`;
    className = "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300";
  }

  return (
    <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${className}`}>{label}</span>
  );
}
