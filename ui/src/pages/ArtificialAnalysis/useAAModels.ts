import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { ASPECT_RATIO_DIMENSIONS } from "./types";
import type { AAModel, AspectRatioKey, DimensionOption } from "./types";

export function useAAModels(mode: "text_to_image" | "image_editing") {
  const [models, setModels] = useState<AAModel[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [modelSearch, setModelSearch] = useState("");
  const [aspectRatio, setAspectRatio] = useState<AspectRatioKey>("1:1 (Square)");
  const [dimension, setDimension] = useState<DimensionOption>(ASPECT_RATIO_DIMENSIONS["1:1 (Square)"][2]);
  const [gensPerModel, setGensPerModel] = useState(1);

  useEffect(() => {
    api.aaGetModels(mode).then(setModels).catch((e) => { throw e; });
  }, [mode]);

  const toggleModel = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectTop = (n: number) => {
    const top = models
      .filter((m) => (mode === "text_to_image" ? m.hasTtiEndpoint : m.hasItiEndpoint))
      .slice(0, n)
      .map((m) => m.id);
    setSelectedIds(new Set(top));
  };

  const filteredModels = models.filter(
    (m) =>
      m.name.toLowerCase().includes(modelSearch.toLowerCase()) ||
      m.creator.toLowerCase().includes(modelSearch.toLowerCase())
  );

  const estCost = (() => {
    let total = 0;
    for (const id of selectedIds) {
      const m = models.find((x) => x.id === id);
      if (!m) continue;
      const price = mode === "text_to_image" ? m.ttiPricePerGeneration : m.itiPricePerGeneration;
      total += (price ?? 0) * gensPerModel;
    }
    return total;
  })();

  return {
    models,
    filteredModels,
    selectedIds,
    setSelectedIds,
    modelSearch,
    setModelSearch,
    toggleModel,
    selectTop,
    aspectRatio,
    setAspectRatio,
    dimension,
    setDimension,
    gensPerModel,
    setGensPerModel,
    estCost,
  };
}
