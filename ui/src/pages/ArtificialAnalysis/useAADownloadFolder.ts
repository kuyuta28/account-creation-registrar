import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";

export function useAADownloadFolder() {
  const [downloadFolder, setDownloadFolder] = useState<string>(
    () => localStorage.getItem("aa_download_folder") ?? ""
  );

  const handlePickFolder = async () => {
    const selected = await open({ directory: true, multiple: false, title: "Chọn thư mục lưu ảnh" });
    if (typeof selected === "string" && selected) {
      setDownloadFolder(selected);
      localStorage.setItem("aa_download_folder", selected);
    }
  };

  return { downloadFolder, handlePickFolder };
}
