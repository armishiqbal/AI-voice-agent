import React, { useEffect, useRef } from "react";

type WaveformVisualizerProps = {
  isActive: boolean;
  color?: string;
  barCount?: number;
};

export function WaveformVisualizer({
  isActive,
  color = "#a855f7",
  barCount = 36,
}: WaveformVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let phase = 0;

    const render = () => {
      phase += 0.08;
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      const barWidth = width / barCount;
      const centerY = height / 2;

      for (let i = 0; i < barCount; i++) {
        const x = i * barWidth;
        // Generate pseudo-audio frequency peaks
        let h = 4;
        if (isActive) {
          const wave1 = Math.sin(phase + i * 0.35);
          const wave2 = Math.cos(phase * 1.5 + i * 0.2);
          const envelope = Math.sin((i / barCount) * Math.PI); // taper ends
          h = Math.max(4, Math.abs(wave1 * wave2) * (height * 0.85) * envelope + 4);
        } else {
          // Subtle idle resting hum
          const envelope = Math.sin((i / barCount) * Math.PI);
          h = Math.max(3, (Math.sin(phase * 0.4 + i * 0.1) * 3 + 4) * envelope);
        }

        const gradient = ctx.createLinearGradient(0, centerY - h / 2, 0, centerY + h / 2);
        gradient.addColorStop(0, "rgba(192, 132, 252, 0.95)");
        gradient.addColorStop(0.5, color);
        gradient.addColorStop(1, "rgba(126, 34, 206, 0.85)");

        ctx.fillStyle = gradient;
        ctx.fillRect(x + 1.5, centerY - h / 2, barWidth - 3, h);
      }

      animRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [isActive, color, barCount]);

  return (
    <div className={`waveform-visualizer-wrap ${isActive ? "active" : "idle"}`}>
      <canvas ref={canvasRef} width={280} height={36} className="waveform-canvas" />
    </div>
  );
}
