import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import type { AAGeneration } from "./types";

export function useAAHistory(selectedEmail: string) {
  const [history, setHistory] = useState<AAGeneration[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [cursor, setCursor] = useState<string | undefined>();

  const loadHistory = useCallback(
    async (reset = false) => {
      if (!selectedEmail) return;
      setHistoryLoading(true);
      try {
        const c = reset ? undefined : cursor;
        const res = await api.aaGetGenerations(selectedEmail, 20, c);
        setHistory((prev) => (reset ? res.generations : [...prev, ...res.generations]));
        setHasMore(res.hasMore);
        setCursor(res.nextCursor ?? undefined);
      } catch {
        // ignore
      } finally {
        setHistoryLoading(false);
      }
    },
    [selectedEmail, cursor]
  );

  useEffect(() => {
    if (selectedEmail) loadHistory(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEmail]);

  return { history, historyLoading, hasMore, loadHistory };
}
