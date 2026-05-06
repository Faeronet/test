import { Arc, Circle, Group, Line, Text } from "react-konva";
import type { CADJSON, Primitive } from "../../lib/canvas";
import { LAYER_COLORS } from "../../lib/canvas";

type Props = {
  cad: CADJSON;
  visibleLayers: Set<string>;
};

export default function CadOverlay({ cad, visibleLayers }: Props) {
  return (
    <Group>
      {cad.primitives
        .filter((p) => visibleLayers.has(p.layer))
        .map((p) => renderOne(p))}
    </Group>
  );
}

function renderOne(p: Primitive) {
  const stroke = LAYER_COLORS[p.layer] ?? "#fff";
  const opacity = p.confidence != null ? Math.max(0.4, p.confidence) : 0.85;
  switch (p.type) {
    case "LINE": {
      if (!p.p1 || !p.p2) return null;
      return (
        <Line
          key={p.id}
          points={[p.p1[0], p.p1[1], p.p2[0], p.p2[1]]}
          stroke={stroke}
          strokeWidth={1}
          opacity={opacity}
        />
      );
    }
    case "CIRCLE": {
      if (!p.center || p.radius == null) return null;
      return (
        <Circle
          key={p.id}
          x={p.center[0]}
          y={p.center[1]}
          radius={p.radius}
          stroke={stroke}
          strokeWidth={1}
          opacity={opacity}
        />
      );
    }
    case "ARC": {
      if (!p.center || p.radius == null) return null;
      const start = p.start_angle_deg ?? 0;
      const end = p.end_angle_deg ?? 360;
      const angle = (end - start + 360) % 360;
      return (
        <Arc
          key={p.id}
          x={p.center[0]}
          y={p.center[1]}
          innerRadius={p.radius}
          outerRadius={p.radius}
          rotation={start}
          angle={angle}
          stroke={stroke}
          strokeWidth={1}
          opacity={opacity}
        />
      );
    }
    case "LWPOLYLINE": {
      const pts = (p.vertices ?? []).flatMap((v) => [v[0], v[1]]);
      return (
        <Line
          key={p.id}
          points={pts}
          stroke={stroke}
          strokeWidth={1}
          opacity={opacity}
          closed={!!p.closed}
        />
      );
    }
    case "TEXT": {
      if (!p.position) return null;
      return (
        <Text
          key={p.id}
          text={p.text ?? ""}
          x={p.position[0]}
          y={p.position[1]}
          fontSize={12}
          fill={stroke}
          opacity={opacity}
        />
      );
    }
    default:
      return null;
  }
}
