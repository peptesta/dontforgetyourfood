import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Batch, PhotoPair } from "../api/batches";
import ProcessingPage from "./ProcessingPage";
import ReviewPage from "./ReviewPage";
import UploadPage from "./UploadPage";

type Step = "upload" | "processing" | "review";

/** Orchestratore del flusso Upload -> Processing -> Review: tiene le coppie di foto
 * (titolo + data) selezionate in memoria locale (React state) invece di passarle via
 * router, così sopravvivono ai passaggi di step senza mai transitare dal backend. */
export default function BatchFlowPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("upload");
  const [batch, setBatch] = useState<Batch | null>(null);
  const [pairs, setPairs] = useState<PhotoPair[]>([]);

  if (step === "upload") {
    return (
      <UploadPage
        onUploaded={(uploadedBatch, uploadedPairs) => {
          setBatch(uploadedBatch);
          setPairs(uploadedPairs);
          setStep("processing");
        }}
      />
    );
  }

  if (step === "processing" && batch) {
    return (
      <ProcessingPage
        batchId={batch.id}
        onDone={(finishedBatch) => {
          setBatch(finishedBatch);
          setStep("review");
        }}
      />
    );
  }

  if (step === "review" && batch) {
    return <ReviewPage batch={batch} pairs={pairs} onConfirmed={() => navigate("/", { replace: true })} />;
  }

  return null;
}
