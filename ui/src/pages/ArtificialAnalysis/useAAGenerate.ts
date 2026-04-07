import { useState } from "react";
import { api } from "../../api/client";
import type { DimensionOption } from "./types";

interface GenerateParams {
  selectedEmail: string;
  selectedIds: Set<string>;
  prompt: string;
  gensPerModel: number;
  dimension: DimensionOption;
  mode: "text_to_image" | "image_editing";
  onSuccess: () => void;
}

export function useAAGenerate() {
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");

  const handleGenerate = async ({
    selectedEmail,
    selectedIds,
    prompt,
    gensPerModel,
    dimension,
    onSuccess,
  }: GenerateParams) => {
    if (!selectedEmail || selectedIds.size === 0 || !prompt.trim()) return;
    setGenerating(true);
    setGenerateError("");
    try {
      await api.aaGenerate({
        email: selectedEmail,
        prompt: prompt.trim(),
        model_ids: Array.from(selectedIds),
        generations_per_model: gensPerModel,
        width: dimension.w,
        height: dimension.h,
      });
      setTimeout(() => onSuccess(), 2000);
      setTimeout(() => onSuccess(), 6000);
    } catch (e) {
      setGenerateError(String(e));
    } finally {
      setGenerating(false);
    }
  };

  return { generating, generateError, handleGenerate };
}
