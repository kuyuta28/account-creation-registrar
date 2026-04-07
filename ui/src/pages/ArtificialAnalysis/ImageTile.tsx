import { useState } from "react";
import type { AAImage } from "./types";
import { downloadAAImage } from "./downloadUtils";

interface ImageTileProps {
  img: AAImage;
  email: string;
  downloadFolder: string;
  onOpen?: () => void;
}

export function ImageTile({ img, email, downloadFolder, onOpen }: ImageTileProps) {
  const [loaded, setLoaded] = useState(false);
  const [err, setErr] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  const handleDownload = async () => {
    if (downloading) return;
    setDownloading(true);
    setDownloadError("");
    try {
      await downloadAAImage({ email, imageId: img.id, modelName: img.modelName, downloadFolder });
    } catch (e) {
      setDownloadError(String(e));
    } finally {
      setDownloading(false);
    }
  };

  if (img.status === "failed") {
    return (
      <div className="aspect-square rounded-lg bg-red-50 flex flex-col items-center justify-center p-2 text-center">
        <span className="text-xs text-red-400">{img.modelName}</span>
        <span className="text-xs text-red-300 mt-1">{img.errorMessage ?? "Failed"}</span>
      </div>
    );
  }

  if (img.status === "pending") {
    return (
      <div className="aspect-square rounded-lg bg-gray-50 flex flex-col items-center justify-center gap-1">
        <div className="w-5 h-5 border-2 border-violet-200 border-t-violet-500 rounded-full animate-spin" />
        <span className="text-xs text-gray-400 truncate px-1 max-w-full">{img.modelName}</span>
      </div>
    );
  }

  return (
    <div
      className={`group relative aspect-square rounded-lg overflow-hidden bg-gray-100 ${onOpen ? "cursor-pointer" : ""}`}
      onClick={onOpen}
    >
      {!loaded && !err && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-violet-200 border-t-violet-500 rounded-full animate-spin" />
        </div>
      )}
      {err ? (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <span className="text-xs text-gray-400">Failed to load</span>
        </div>
      ) : (
        <img
          src={img.imageUrl}
          alt={img.modelName}
          onLoad={() => setLoaded(true)}
          onError={() => setErr(true)}
          className={`w-full h-full object-cover transition-opacity ${loaded ? "opacity-100" : "opacity-0"}`}
        />
      )}
      <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/60 to-transparent px-2 py-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <p className="text-xs text-white truncate">{img.modelName}</p>
        {downloadError && (
          <p className="text-xs text-red-300 truncate" title={downloadError}>{downloadError}</p>
        )}
      </div>
      {loaded && (
        <div className="absolute top-1.5 right-1.5 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <a
            href={img.imageUrl}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="w-6 h-6 bg-white/90 rounded-md flex items-center justify-center hover:bg-white"
            title="Open full size"
          >
            <svg className="w-3.5 h-3.5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
          <button
            onClick={(e) => { e.stopPropagation(); handleDownload(); }}
            disabled={downloading}
            className="w-6 h-6 bg-white/90 rounded-md flex items-center justify-center hover:bg-white disabled:opacity-50"
            title="Download"
          >
            {downloading ? (
              <span className="w-3 h-3 border border-gray-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-3.5 h-3.5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
