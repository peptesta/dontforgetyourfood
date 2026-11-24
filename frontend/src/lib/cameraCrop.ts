/** Mappa il riquadro guida (coordinate CSS) alle coordinate pixel native del video,
 * tenendo conto di object-fit: cover — il video viene scalato uniformemente per
 * riempire il contenitore e la parte eccedente viene ritagliata centrata, quindi il
 * rapporto videoWidth/clientWidth da solo non basta. */
export function guideToVideoRect(video: HTMLVideoElement, guideEl: HTMLDivElement) {
  const displayRect = video.getBoundingClientRect();
  const guideRect = guideEl.getBoundingClientRect();

  const scale = Math.max(displayRect.width / video.videoWidth, displayRect.height / video.videoHeight);
  const offsetX = (video.videoWidth * scale - displayRect.width) / 2;
  const offsetY = (video.videoHeight * scale - displayRect.height) / 2;

  return {
    sx: (guideRect.left - displayRect.left + offsetX) / scale,
    sy: (guideRect.top - displayRect.top + offsetY) / scale,
    sw: guideRect.width / scale,
    sh: guideRect.height / scale,
  };
}
