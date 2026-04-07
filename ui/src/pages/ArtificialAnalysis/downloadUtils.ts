import { save } from "@tauri-apps/plugin-dialog";
import { writeFile } from "@tauri-apps/plugin-fs";
import { api } from "../../api/client";

export function buildFilename(modelName: string): string {
  const now = new Date();
  const ts =
    [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, "0"),
      String(now.getDate()).padStart(2, "0"),
    ].join("") +
    "_" +
    [
      String(now.getHours()).padStart(2, "0"),
      String(now.getMinutes()).padStart(2, "0"),
      String(now.getSeconds()).padStart(2, "0"),
    ].join("");
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase();
  const safeName = modelName.replace(/[\\\/:*?"<>|]/g, "_");
  return `${safeName}_${ts}_${rand}.png`;
}

export async function downloadAAImage(params: {
  email: string;
  imageId: string;
  modelName: string;
  downloadFolder: string;
}): Promise<void> {
  const { email, imageId, modelName, downloadFolder } = params;
  const filename = buildFilename(modelName);

  let savePath: string | null;
  if (downloadFolder) {
    savePath = `${downloadFolder}\\${filename}`;
  } else {
    savePath = await save({
      defaultPath: filename,
      filters: [{ name: "PNG Image", extensions: ["png"] }],
    });
    if (!savePath) return;
  }

  const buf = await api.aaImageDownload(email, imageId, modelName);
  await writeFile(savePath, new Uint8Array(buf));
}
