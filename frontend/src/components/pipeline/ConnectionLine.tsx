"use client";

interface ConnectionLineProps {
  from: { x: number; y: number };
  to: { x: number; y: number };
  color?: string;
}

export function ConnectionLine({ from, to, color = "#6366f1" }: ConnectionLineProps) {
  const dx = Math.abs(to.x - from.x) * 0.5;
  const path = `M ${from.x} ${from.y} C ${from.x + dx} ${from.y}, ${to.x - dx} ${to.y}, ${to.x} ${to.y}`;

  return (
    <path
      d={path}
      fill="none"
      stroke={color}
      strokeWidth={2}
      strokeDasharray="6 3"
      opacity={0.6}
    />
  );
}
