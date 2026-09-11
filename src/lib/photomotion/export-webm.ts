export async function recordCanvasWebm(
  canvas: HTMLCanvasElement,
  audio: HTMLAudioElement,
  durationS: number,
  onTick?: (t: number) => void,
): Promise<Blob> {
  const stream = canvas.captureStream(30);
  const audioStream = (audio as HTMLAudioElement & { captureStream?: () => MediaStream }).captureStream?.()
    ?? (audio as HTMLAudioElement & { mozCaptureStream?: () => MediaStream }).mozCaptureStream?.();
  if (audioStream) {
    for (const track of audioStream.getAudioTracks()) stream.addTrack(track);
  }
  const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
    ? "video/webm;codecs=vp9,opus"
    : "video/webm";
  const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 8_000_000 });
  const chunks: BlobPart[] = [];
  rec.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data);
  };
  const done = new Promise<Blob>((resolve, reject) => {
    rec.onstop = () => resolve(new Blob(chunks, { type: mime }));
    rec.onerror = () => reject(new Error("Recorder failed"));
  });
  rec.start(200);
  const start = performance.now();
  await new Promise<void>((resolve) => {
    const tick = () => {
      const t = (performance.now() - start) / 1000;
      onTick?.(t);
      if (t >= durationS || rec.state !== "recording") {
        resolve();
        return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  if (rec.state === "recording") rec.stop();
  return done;
}

export function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
