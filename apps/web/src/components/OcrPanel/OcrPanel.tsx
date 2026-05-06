import { Group, Rect, Text } from "react-konva";
import type { CADJSON } from "../../lib/canvas";

export default function OcrPanel({ cad }: { cad: CADJSON }) {
  const blocks = cad.ocr ?? [];
  return (
    <Group>
      {blocks.map((b) => {
        const [x1, y1, x2, y2] = b.bbox_px;
        return (
          <Group key={b.id}>
            <Rect
              x={x1}
              y={y1}
              width={Math.max(1, x2 - x1)}
              height={Math.max(1, y2 - y1)}
              stroke="#79c0ff"
              strokeWidth={1}
              opacity={0.6}
            />
            <Text
              x={x1}
              y={Math.max(0, y1 - 14)}
              text={b.text}
              fontSize={11}
              fill="#79c0ff"
            />
          </Group>
        );
      })}
    </Group>
  );
}
