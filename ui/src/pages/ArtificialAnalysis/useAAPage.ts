import { useState } from "react";
import { useAAAccounts } from "./useAAAccounts";
import { useAAModels } from "./useAAModels";
import { useAAHistory } from "./useAAHistory";
import { useAAGenerate } from "./useAAGenerate";
import { useAADownloadFolder } from "./useAADownloadFolder";

export function useAAPage() {
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<"text_to_image" | "image_editing">("text_to_image");

  const accounts = useAAAccounts();
  const models = useAAModels(mode);
  const history = useAAHistory(accounts.selectedEmail);
  const generate = useAAGenerate();
  const folder = useAADownloadFolder();

  const handleGenerate = () =>
    generate.handleGenerate({
      selectedEmail: accounts.selectedEmail,
      selectedIds: models.selectedIds,
      prompt,
      gensPerModel: models.gensPerModel,
      dimension: models.dimension,
      mode,
      onSuccess: () => history.loadHistory(true),
    });

  return {
    ...accounts,
    ...models,
    ...history,
    generating: generate.generating,
    generateError: generate.generateError,
    handleGenerate,
    prompt,
    setPrompt,
    mode,
    setMode,
    ...folder,
  };
}
