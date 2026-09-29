import React, { useEffect, useRef } from "react";

type WaveformVisualizerProps = {
  mode: "idle" | "listening" | "speaking";
  analyser: AnalyserNode | null;
  color?: string;
  barCount?: number;
};

function drawMeter(
  canvas: HTMLCanvasElement,
  analyser: AnalyserNode | null,
  color: string,
  barCount: number,
) {
  const context = canvas.getContext("2d");
  if (!context) return;

  const { width, height } = canvas;
  context.clearRect(0, 0, width, height);
  const centerY = height / 2;
  const samples = analyser ? new Uint8Array(analyser.fftSize) : null;
  if (analyser && samples) analyser.getByteTimeDomainData(samples);

  const barWidth = width / barCount;
  for (let bar = 0; bar < barCount; bar += 1) {
    let energy = 0;
    if (samples) {
      const start = Math.floor((bar / barCount) * samples.length);
      const end = Math.max(start + 1, Math.floor(((bar + 1) / barCount) * samples.length));
      for (let index = start; index < end; index += 1) {
        const sample = (samples[index] - 128) / 128;
        energy += sample * sample;
      }
      energy = Math.sqrt(energy / (end - start));
    }

    // Keep a quiet baseline; bar movement comes only from measured microphone input.
    const barHeight = 2 + Math.min(1, energy * 2.8) * (height * 0.82);
    const x = bar * barWidth + 1;
    const gradient = context.createLinearGradient(0, centerY - barHeight / 2, 0, centerY + barHeight / 2);
    gradient.addColorStop(0, "rgba(192, 132, 252, 0.95)");
    gradient.addColorStop(0.5, color);
    gradient.addColorStop(1, "rgba(126, 34, 206, 0.85)");
    context.fillStyle = gradient;
    context.fillRect(x, centerY - barHeight / 2, Math.max(1, barWidth - 2), barHeight);
  }
}

export function WaveformVisualizer({
  mode,
  analyser,
  color = "#a855f7",
  barCount = 36,
}: WaveformVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let animationFrame: number | null = null;
    let stopped = false;
    const render = () => {
      if (stopped) return;
      drawMeter(canvas, mode === "listening" ? analyser : null, color, barCount);
      if (mode === "listening") animationFrame = requestAnimationFrame(render);
    };
    render();

    return () => {
      stopped = true;
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    };
  }, [analyser, barCount, color, mode]);

  const label = mode === "listening"
    ? analyser ? "Microphone input level" : "Waiting for microphone input"
    : mode === "speaking" ? "Assistant speaking" : "Voice meter idle";

  return (
    <div className={`waveform-visualizer-wrap ${mode}`} role="img" aria-label={label}>
      <canvas ref={canvasRef} width={280} height={36} className="waveform-canvas" aria-hidden="true" />
      <span className="waveform-label">{label}</span>
    </div>
  );
}
