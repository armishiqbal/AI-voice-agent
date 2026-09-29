import React, { useEffect, useRef } from "react";

type NeuralOrbProps = {
  voicePhase: "checking" | "blocked" | "idle" | "connecting" | "authenticating" | "starting_microphone" | "listening" | "transcribing" | "thinking" | "speaking" | "error";
  isAudioActive?: boolean;
  onClick?: () => void;
  audioAnalyser?: AnalyserNode | null;
};

// Generates points evenly distributed on a sphere using the Fibonacci spiral
function createSpherePoints(count: number, radius: number) {
  const points: { x: number; y: number; z: number; baseRadius: number; phase: number }[] = [];
  const phi = Math.PI * (Math.sqrt(5) - 1); // golden ratio angle

  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2; // y goes from 1 to -1
    const radiusAtY = Math.sqrt(1 - y * y);
    const theta = phi * i;

    const x = Math.cos(theta) * radiusAtY;
    const z = Math.sin(theta) * radiusAtY;

    points.push({
      x: x * radius,
      y: y * radius,
      z: z * radius,
      baseRadius: radius,
      phase: Math.random() * Math.PI * 2,
    });
  }
  return points;
}

export function NeuralOrb({ voicePhase, isAudioActive = false, onClick, audioAnalyser }: NeuralOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const rotRef = useRef({ rotX: 0.22, rotY: 0, rotZ: 0 });
  const pointsRef = useRef(createSpherePoints(850, 130));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    if (animFrameRef.current !== null) cancelAnimationFrame(animFrameRef.current);
    let time = 0;
    const freqData = new Uint8Array(64);
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    const render = () => {
      time += 0.016;
      const width = canvas.width;
      const height = canvas.height;
      const centerX = width / 2;
      const centerY = height / 2;

      ctx.clearRect(0, 0, width, height);

      // 0. Extract physical frequency spectrum if analyser is active
      let realAudioEnergy = 0;
      if (audioAnalyser) {
        try {
          audioAnalyser.getByteFrequencyData(freqData);
          let sum = 0;
          for (let i = 0; i < 32; i++) {
            sum += freqData[i];
          }
          realAudioEnergy = sum / (32 * 255);
        } catch {
          realAudioEnergy = 0;
        }
      }

      // Determine animation speed, color and radius pulse based on voicePhase
      let speedY = 0.007;
      let speedX = 0.003;
      let pulseAmp = 3.5;
      let waveFreq = 2.5;
      let coreColor = "rgba(139, 92, 246, 0.22)";
      let particleHue = 272; // luxury violet
      let ringGlow = "rgba(168, 85, 247, 0.4)";

      if (voicePhase === "listening") {
        speedY = 0.014;
        pulseAmp = 15;
        waveFreq = 7;
        coreColor = "rgba(52, 211, 153, 0.35)"; // green reactive
        particleHue = 160; // cyan-green
        ringGlow = "rgba(52, 211, 153, 0.7)";
      } else if (voicePhase === "transcribing") {
        speedY = 0.02;
        speedX = 0.008;
        pulseAmp = 8;
        waveFreq = 5;
        coreColor = "rgba(56, 189, 248, 0.38)";
        particleHue = 195;
        ringGlow = "rgba(56, 189, 248, 0.72)";
      } else if (voicePhase === "thinking") {
        speedY = 0.028;
        speedX = 0.015;
        pulseAmp = 9;
        waveFreq = 9;
        coreColor = "rgba(99, 102, 241, 0.5)";
        particleHue = 245; // electric indigo
        ringGlow = "rgba(99, 102, 241, 0.7)";
      } else if (voicePhase === "speaking") {
        speedY = 0.015;
        pulseAmp = isAudioActive ? 18 : 12;
        waveFreq = 5.5;
        coreColor = "rgba(236, 72, 153, 0.45)"; // magenta-rose
        particleHue = 300; // magenta
        ringGlow = "rgba(236, 72, 153, 0.7)";
      } else if (voicePhase === "error") {
        speedY = 0.003;
        coreColor = "rgba(239, 68, 68, 0.25)";
        particleHue = 0; // red
        ringGlow = "rgba(239, 68, 68, 0.5)";
      }

      if (realAudioEnergy > 0.01) {
        pulseAmp = Math.max(pulseAmp, 10 + realAudioEnergy * 32);
        waveFreq = Math.max(waveFreq, 6 + realAudioEnergy * 8);
      }

      rotRef.current.rotY += speedY;
      rotRef.current.rotX += speedX;

      const cosY = Math.cos(rotRef.current.rotY);
      const sinY = Math.sin(rotRef.current.rotY);
      const cosX = Math.cos(rotRef.current.rotX);
      const sinX = Math.sin(rotRef.current.rotX);

      // 1. Draw glowing inner core
      const corePulse = 110 + Math.sin(time * 3) * 10 + (realAudioEnergy * 25);
      const coreGradient = ctx.createRadialGradient(
        centerX,
        centerY,
        6,
        centerX,
        centerY,
        corePulse
      );
      coreGradient.addColorStop(0, coreColor);
      coreGradient.addColorStop(0.4, coreColor.replace(/[\d\.]+\)$/, "0.15)"));
      coreGradient.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = coreGradient;
      ctx.beginPath();
      ctx.arc(centerX, centerY, 110 + Math.sin(time * 3) * 10, 0, Math.PI * 2);
      ctx.fill();

      // 2. Draw Futuristic Orbital Rings (Compass & Gimbal Rings)
      ctx.save();
      ctx.translate(centerX, centerY);

      // Ring 1: Outer Tilted Orbit Ring
      ctx.strokeStyle = ringGlow;
      ctx.lineWidth = 1.4;
      ctx.setLineDash([6, 10, 2, 10]);
      ctx.beginPath();
      ctx.ellipse(0, 0, 195, 68, Math.PI / 6 + time * 0.18, 0, Math.PI * 2);
      ctx.stroke();

      // Orbit Satellite 1 on Ring 1
      const sat1Angle = time * 0.6;
      const sat1X = Math.cos(sat1Angle) * 195;
      const sat1Y = Math.sin(sat1Angle) * 68;
      const rotAngle1 = Math.PI / 6 + time * 0.18;
      const finalSat1X = sat1X * Math.cos(rotAngle1) - sat1Y * Math.sin(rotAngle1);
      const finalSat1Y = sat1X * Math.sin(rotAngle1) + sat1Y * Math.cos(rotAngle1);

      ctx.fillStyle = ringGlow;
      ctx.shadowColor = ringGlow;
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(finalSat1X, finalSat1Y, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Ring 2: Counter-Rotating Intersecting Gimbal Ring
      ctx.strokeStyle = "rgba(192, 132, 252, 0.35)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([14, 18]);
      ctx.beginPath();
      ctx.ellipse(0, 0, 175, 54, -Math.PI / 4 - time * 0.14, 0, Math.PI * 2);
      ctx.stroke();

      // Orbit Satellite 2 on Ring 2
      const sat2Angle = -time * 0.8;
      const sat2X = Math.cos(sat2Angle) * 175;
      const sat2Y = Math.sin(sat2Angle) * 54;
      const rotAngle2 = -Math.PI / 4 - time * 0.14;
      const finalSat2X = sat2X * Math.cos(rotAngle2) - sat2Y * Math.sin(rotAngle2);
      const finalSat2Y = sat2X * Math.sin(rotAngle2) + sat2Y * Math.cos(rotAngle2);

      ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
      ctx.beginPath();
      ctx.arc(finalSat2X, finalSat2Y, 3, 0, Math.PI * 2);
      ctx.fill();

      // Ring 3: Equatorial Horizon Ring with radar tick arcs
      ctx.strokeStyle = "rgba(139, 92, 246, 0.5)";
      ctx.lineWidth = 1.6;
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(0, 0, 215, 0.2 + time * 0.08, 1.3 + time * 0.08);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(0, 0, 215, Math.PI + 0.2 + time * 0.08, Math.PI + 1.3 + time * 0.08);
      ctx.stroke();

      // Ring 4: Outer Faint Boundary Ring with Degree Ticks
      ctx.strokeStyle = "rgba(168, 85, 247, 0.18)";
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 14]);
      ctx.beginPath();
      ctx.arc(0, 0, 235, 0, Math.PI * 2);
      ctx.stroke();

      ctx.restore();

      // 3. Render 3D Dotted Particle Sphere
      const points = pointsRef.current;
      const fov = 380;
      const cameraZ = 270;

      // Project and sort by depth for realistic volumetric rendering
      const projected: { x2d: number; y2d: number; z: number; size: number; alpha: number }[] = [];

      for (let i = 0; i < points.length; i++) {
        const pt = points[i];

        // Acoustic frequency displacement along the sphere surface
        const freqSample = realAudioEnergy > 0.01 ? (freqData[i % 32] / 255) * 20 : 0;
        const wave = Math.sin(time * waveFreq + pt.phase) * pulseAmp + freqSample;
        const currentR = pt.baseRadius + wave;
        const normFactor = currentR / pt.baseRadius;

        let px = pt.x * normFactor;
        let py = pt.y * normFactor;
        let pz = pt.z * normFactor;

        // Rotation around Y
        const x1 = px * cosY + pz * sinY;
        const z1 = -px * sinY + pz * cosY;

        // Rotation around X
        const y2 = py * cosX - z1 * sinX;
        const z2 = py * sinX + z1 * cosX;

        // Perspective projection
        const scale = fov / (fov + z2 + cameraZ);
        const x2d = centerX + x1 * scale;
        const y2d = centerY + y2 * scale;

        // Depth-based size and opacity
        const depthNorm = (z2 + pt.baseRadius) / (pt.baseRadius * 2); // 0 (far) to 1 (near)
        const size = Math.max(0.6, (1.3 + depthNorm * 2.4) * scale * 1.15);
        const alpha = Math.max(0.14, Math.min(1, 0.18 + depthNorm * 0.82));

        projected.push({ x2d, y2d, z: z2, size, alpha });
      }

      // Sort from back to front
      projected.sort((a, b) => a.z - b.z);

      // Draw particle cloud
      for (let i = 0; i < projected.length; i++) {
        const p = projected[i];
        ctx.fillStyle = `hsla(${particleHue}, 88%, ${60 + (p.alpha * 32)}%, ${p.alpha})`;
        ctx.beginPath();
        ctx.arc(p.x2d, p.y2d, p.size, 0, Math.PI * 2);
        ctx.fill();
      }

      // 4. Central Pulsating Flare
      const flareSize = 16 + Math.sin(time * 4) * 5 + (realAudioEnergy * 28);
      const flareGrad = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, flareSize);
      flareGrad.addColorStop(0, "rgba(255, 255, 255, 0.95)");
      flareGrad.addColorStop(0.35, `hsla(${particleHue}, 100%, 75%, 0.65)`);
      flareGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = flareGrad;
      ctx.beginPath();
      ctx.arc(centerX, centerY, flareSize, 0, Math.PI * 2);
      ctx.fill();

      animFrameRef.current = document.hidden || reducedMotion.matches
        ? null
        : requestAnimationFrame(render);
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        if (animFrameRef.current !== null) cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
        return;
      }
      render();
    };
    const handleMotionPreferenceChange = () => {
      if (animFrameRef.current !== null) cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
      render();
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    reducedMotion.addEventListener("change", handleMotionPreferenceChange);
    render();

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      reducedMotion.removeEventListener("change", handleMotionPreferenceChange);
      if (animFrameRef.current !== null) cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    };
  }, [voicePhase, isAudioActive, audioAnalyser]);

  return (
    <button
      type="button"
      className="neural-orb-container"
      onClick={onClick}
      aria-label={voicePhase === "connecting" || voicePhase === "authenticating" || voicePhase === "starting_microphone"
        ? "Voice chat is connecting"
        : voicePhase === "listening" || voicePhase === "transcribing" || voicePhase === "thinking" || voicePhase === "speaking"
          ? "Stop voice chat"
          : "Start or retry voice chat"}
      aria-busy={voicePhase === "connecting" || voicePhase === "authenticating" || voicePhase === "starting_microphone" || voicePhase === "transcribing" || voicePhase === "thinking"}
      aria-pressed={voicePhase === "listening" || voicePhase === "transcribing" || voicePhase === "thinking" || voicePhase === "speaking"}
      title="Start or stop voice chat"
    >
      <canvas
        ref={canvasRef}
        width={500}
        height={500}
        className={`neural-orb-canvas state-${voicePhase}`}
      />
    </button>
  );
}
