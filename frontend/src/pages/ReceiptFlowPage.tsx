import { useState } from "react";
import type { ReceiptParseResult } from "../api/receipts";
import ReceiptCapturePage from "./ReceiptCapturePage";
import ReceiptResultPage from "./ReceiptResultPage";

/** Orchestratore del flusso Carica scontrino: Cattura -> Risultato (Step 1). Gli Step
 * successivi (quantità, scadenze dei freschi, riepilogo, dispensa) si agganceranno qui. */
export default function ReceiptFlowPage() {
  const [result, setResult] = useState<ReceiptParseResult | null>(null);

  if (!result) return <ReceiptCapturePage onParsed={setResult} />;
  return <ReceiptResultPage result={result} onRetake={() => setResult(null)} />;
}
