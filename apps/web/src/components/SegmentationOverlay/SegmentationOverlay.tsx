import { Group, Image as KImage } from "react-konva";
import { useEffect, useState } from "react";

type Props = {
  maskUrls: Record<string, string>;
  visible: Set<string>;
};

export default function SegmentationOverlay({ maskUrls, visible }: Props) {
  const [imgs, setImgs] = useState<Record<string, HTMLImageElement>>({});
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const out: Record<string, HTMLImageElement> = {};
      for (const [name, url] of Object.entries(maskUrls)) {
        if (!visible.has(name)) continue;
        await new Promise<void>((resolve) => {
          const im = new window.Image();
          im.crossOrigin = "anonymous";
          im.onload = () => {
            out[name] = im;
            resolve();
          };
          im.onerror = () => resolve();
          im.src = url;
        });
      }
      if (!cancelled) setImgs(out);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [maskUrls, visible]);

  return (
    <Group opacity={0.4}>
      {Object.entries(imgs).map(([name, im]) => (
        <KImage key={name} image={im} />
      ))}
    </Group>
  );
}
