import { useEffect, useState } from "react";
import type { EventEnvelope } from "./types";
import { api } from "./api";

/**
 * Subscribes to the SSE stream of pipeline events. Falls back to a noop
 * subscription if the browser does not support EventSource (which is rare —
 * all evergreen browsers do).
 */
export function useEventStream(batchId?: string): EventEnvelope[] {
  const [events, setEvents] = useState<EventEnvelope[]>([]);

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const url = batchId
      ? `${api.baseUrl}/api/events/stream?batch_id=${encodeURIComponent(batchId)}`
      : `${api.baseUrl}/api/events/stream`;
    const es = new EventSource(url);
    es.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data) as EventEnvelope;
        setEvents((prev) => [...prev.slice(-199), data]);
      } catch {
        /* ignore malformed messages */
      }
    };
    es.onerror = () => {
      // network blip — let EventSource auto-reconnect
    };
    return () => es.close();
  }, [batchId]);

  return events;
}
