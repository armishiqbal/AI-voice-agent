import React, { useEffect, useState } from "react";

type OrbitalLaserBeamsProps = {
  activeNodeId: string | null;
  stageRef: React.RefObject<HTMLDivElement | null>;
};

const NODE_COLORS: Record<string, { stroke: string; glow: string; rgb: string }> = {
  "buyer-search": { stroke: "#34d399", glow: "#10b981", rgb: "52, 211, 153" },
  "karachi-search": { stroke: "#22d3ee", glow: "#06b6d4", rgb: "34, 211, 238" },
  "lahore-search": { stroke: "#c084fc", glow: "#a855f7", rgb: "192, 132, 252" },
  "islamabad-commercial": { stroke: "#38bdf8", glow: "#0284c7", rgb: "56, 189, 248" },
  "installment-plans": { stroke: "#4ade80", glow: "#22c55e", rgb: "74, 222, 128" },
  "rental-search": { stroke: "#f472b6", glow: "#ec4899", rgb: "244, 114, 182" },
  "schedule-visit": { stroke: "#fb7185", glow: "#e11d48", rgb: "251, 113, 133" },
  "property-locations": { stroke: "#2dd4bf", glow: "#14b8a6", rgb: "45, 212, 191" },
};

export function OrbitalLaserBeams({ activeNodeId, stageRef }: OrbitalLaserBeamsProps) {
  const [coords, setCoords] = useState<{
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    color: { stroke: string; glow: string; rgb: string };
  } | null>(null);

  useEffect(() => {
    if (!activeNodeId || !stageRef.current) {
      setCoords(null);
      return;
    }

    const updateCoords = () => {
      const stage = stageRef.current;
      if (!stage) return;
      const stageRect = stage.getBoundingClientRect();

      // Find the active node element
      const nodeEl = stage.querySelector(`[data-node-id="${activeNodeId}"] .node-dot-pin`) as HTMLElement | null;
      // Find the center of the orbit canvas
      const orbEl = stage.querySelector(".orbit-canvas-wrap") as HTMLElement | null;

      if (!nodeEl || !orbEl) {
        setCoords(null);
        return;
      }

      const nodeRect = nodeEl.getBoundingClientRect();
      const orbRect = orbEl.getBoundingClientRect();

      const x1 = nodeRect.left + nodeRect.width / 2 - stageRect.left;
      const y1 = nodeRect.top + nodeRect.height / 2 - stageRect.top;
      const x2 = orbRect.left + orbRect.width / 2 - stageRect.left;
      const y2 = orbRect.top + orbRect.height / 2 - stageRect.top;

      const color = NODE_COLORS[activeNodeId] || { stroke: "#22d3ee", glow: "#06b6d4", rgb: "34, 211, 238" };

      setCoords({ x1, y1, x2, y2, color });
    };

    updateCoords();
    const interval = window.setInterval(updateCoords, 100);
    window.addEventListener("resize", updateCoords);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("resize", updateCoords);
    };
  }, [activeNodeId, stageRef]);

  if (!coords) return null;

  const { x1, y1, x2, y2, color } = coords;

  // Calculate gentle curved control point
  const dx = x2 - x1;
  const dy = y2 - y1;
  const cx = x1 + dx * 0.5 - dy * 0.15;
  const cy = y1 + dy * 0.5 + dx * 0.15;

  const pathD = `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;

  return (
    <svg
      className="orbital-laser-svg"
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 4,
        overflow: "visible",
      }}
      aria-hidden="true"
    >
      <defs>
        <filter id="beam-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <linearGradient id="laser-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={color.stroke} stopOpacity="0.9" />
          <stop offset="50%" stopColor="#ffffff" stopOpacity="1" />
          <stop offset="100%" stopColor={color.glow} stopOpacity="0.9" />
        </linearGradient>
      </defs>

      {/* Broad Outer Energy Halo */}
      <path
        d={pathD}
        fill="none"
        stroke={`rgba(${color.rgb}, 0.28)`}
        strokeWidth="10"
        strokeLinecap="round"
        filter="url(#beam-glow)"
      />

      {/* Mid Energetic Plasma Stream */}
      <path
        d={pathD}
        fill="none"
        stroke={color.stroke}
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeDasharray="14 8"
        className="laser-animated-beam"
      />

      {/* Super-bright Core Laser Line */}
      <path
        d={pathD}
        fill="none"
        stroke="#ffffff"
        strokeWidth="1.6"
        strokeLinecap="round"
      />

      {/* High-Velocity Traveling Energy Photon Packets */}
      <circle r="4.5" fill="#ffffff" filter="url(#beam-glow)">
        <animateMotion path={pathD} dur="0.75s" repeatCount="indefinite" />
      </circle>
      <circle r="3" fill={color.stroke} filter="url(#beam-glow)">
        <animateMotion path={pathD} dur="0.75s" begin="0.37s" repeatCount="indefinite" />
      </circle>

      {/* Source Pin Transmitter Aura */}
      <circle cx={x1} cy={y1} r="9" fill="none" stroke={color.stroke} strokeWidth="1.5" opacity="0.8">
        <animate attributeName="r" values="4;16" dur="1.2s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.9;0" dur="1.2s" repeatCount="indefinite" />
      </circle>

      {/* Orbit Impact Concentric Shockwave Rings */}
      <circle cx={x2} cy={y2} r="18" fill="none" stroke={color.stroke} strokeWidth="2" opacity="0.8">
        <animate attributeName="r" values="8;36" dur="1s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.8;0" dur="1s" repeatCount="indefinite" />
      </circle>
      <circle cx={x2} cy={y2} r="5" fill="#ffffff" filter="url(#beam-glow)" />
    </svg>
  );
}
