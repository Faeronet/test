import { useEffect, useRef, useState } from "react";
import { Stage, Layer, Image as KImage } from "react-konva";
import type Konva from "konva";
import type { CADJSON } from "../../lib/canvas";
import CadOverlay from "../CadOverlay/CadOverlay";
import OcrPanel from "../OcrPanel/OcrPanel";

type Props = {
  imageSrc?: string;
  cad?: CADJSON | null;
  visibleLayers: Set<string>;
  showOcr: boolean;
};

export default function DrawingViewer({ imageSrc, cad, visibleLayers, showOcr }: Props) {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [box, setBox] = useState<{ width: number; height: number }>({ width: 800, height: 600 });
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<Konva.Stage | null>(null);

  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const r = e.contentRect;
        setBox({ width: r.width, height: r.height });
      }
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!imageSrc) {
      setImg(null);
      return;
    }
    const im = new window.Image();
    im.crossOrigin = "anonymous";
    im.onload = () => setImg(im);
    im.src = imageSrc;
  }, [imageSrc]);

  const intrinsicW = img?.naturalWidth ?? cad?.document.image_size_px?.[0] ?? 1000;
  const intrinsicH = img?.naturalHeight ?? cad?.document.image_size_px?.[1] ?? 1000;
  const scale = Math.min(box.width / intrinsicW, box.height / intrinsicH);

  return (
    <div ref={wrapRef} className="canvas-wrap">
      <Stage ref={stageRef} width={box.width} height={box.height}>
        <Layer scale={{ x: scale, y: scale }}>
          {img ? <KImage image={img} /> : null}
          {cad ? <CadOverlay cad={cad} visibleLayers={visibleLayers} /> : null}
          {cad && showOcr ? <OcrPanel cad={cad} /> : null}
        </Layer>
      </Stage>
    </div>
  );
}
