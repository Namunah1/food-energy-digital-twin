"use client";

import { Handle, Position } from "@xyflow/react";
import { riskColor } from "@/lib/utils";
import { memo } from "react";

export interface RiskNodeData {
  label: string;
  foodSecurity: number;
  size: number;
  overload: boolean;
  [key: string]: unknown;
}

function RiskNodeInner({ data, selected }: { data: RiskNodeData; selected: boolean }) {
  const color = riskColor(data.foodSecurity);
  return (
    <div className="flex flex-col items-center gap-1" style={{ width: data.size + 40 }}>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div
        className="rounded-full flex items-center justify-center transition-transform"
        style={{
          width: data.size,
          height: data.size,
          background: color,
          opacity: data.overload ? 0.95 : 0.7,
          border: selected ? "2px solid #EDF2F6" : `1px solid ${color}`,
          boxShadow: selected ? "0 0 0 4px rgba(63,199,190,0.15)" : undefined,
        }}
      />
      <span className="text-[10px] font-mono text-ink-2 whitespace-nowrap select-none">{data.label}</span>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

export const RiskNode = memo(RiskNodeInner);
