import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import type { AAImage } from "./types";
import { downloadAAImage } from "./downloadUtils";

interface LightboxProps {
  images: AAImage[];
  index: number;
  email: string;
  downloadFolder: string;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
}

export function Lightbox({ images, index, email, downloadFolder, onClose, onPrev, onNext }: LightboxProps) {
  const img = images[index];
  const [downloadingIds, setDownloadingIds] = useState<Set<string>>(new Set());
  const [downloadErrors, setDownloadErrors] = useState<Map<string, string>>(new Map());

  const isDownloading = downloadingIds.has(img.id);
  const currentError = downloadErrors.get(img.id) ?? "";

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") onPrev();
      else if (e.key === "ArrowRight") onNext();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, onPrev, onNext]);

  const handleDownload = async () => {
    const target = img;
    if (downloadingIds.has(target.id)) return;
    setDownloadingIds((prev) => new Set([...prev, target.id]));
    setDownloadErrors((prev) => { const m = new Map(prev); m.delete(target.id); return m; });
    try {
      await downloadAAImage({ email, imageId: target.id, modelName: target.modelName, downloadFolder });
    } catch (e) {
      setDownloadErrors((prev) => new Map([...prev, [target.id, String(e)]]));
    } finally {
      setDownloadingIds((prev) => { const s = new Set(prev); s.delete(target.id); return s; });
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
      onClick={onClose}
    >
      {/* Header */}
      <div className="absolute top-0 inset-x-0 flex items-center justify-between px-4 py-3 bg-gradient-to-b from-black/80 to-transparent pointer-events-none">
        <span className="text-white text-sm font-medium truncate max-w-[60%]">{img.modelName}</span>
        <span className="text-gray-400 text-sm shrink-0">{index + 1} / {images.length}</span>
        <button
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          className="w-8 h-8 flex items-center justify-center text-white/80 hover:text-white transition-colors pointer-events-auto"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Prev */}
      {index > 0 && (
        <button
          onClick={(e) => { e.stopPropagation(); onPrev(); }}
          className="absolute left-4 top-1/2 -translate-y-1/2 w-11 h-11 bg-white/10 hover:bg-white/25 rounded-full flex items-center justify-center text-white transition-colors backdrop-blur-sm"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      )}

      {/* Image */}
      <img
        src={img.imageUrl}
        alt={img.modelName}
        className="max-h-[85vh] max-w-[85vw] object-contain rounded-lg shadow-2xl select-none"
        onClick={(e) => e.stopPropagation()}
        draggable={false}
      />

      {/* Next */}
      {index < images.length - 1 && (
        <button
          onClick={(e) => { e.stopPropagation(); onNext(); }}
          className="absolute right-4 top-1/2 -translate-y-1/2 w-11 h-11 bg-white/10 hover:bg-white/25 rounded-full flex items-center justify-center text-white transition-colors backdrop-blur-sm"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}

      {/* Footer: download */}
      <div className="absolute bottom-0 inset-x-0 flex flex-col items-center gap-1.5 pb-5 pt-10 bg-gradient-to-t from-black/80 to-transparent">
        {currentError && <p className="text-red-400 text-xs">{currentError}</p>}
        <button
          onClick={(e) => { e.stopPropagation(); handleDownload(); }}
          disabled={isDownloading}
          className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 text-white text-sm rounded-lg transition-colors disabled:opacity-50 backdrop-blur-sm border border-white/10"
        >
          {isDownloading ? (
            <span className="w-4 h-4 border border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          )}
          Download PNG
        </button>
      </div>
    </div>,
    document.body
  );
}
