import { useState } from "react";
import type { AAGeneration } from "./types";
import { ImageTile } from "./ImageTile";
import { Lightbox } from "./Lightbox";

interface GenerationCardProps {
  gen: AAGeneration;
  email: string;
  downloadFolder: string;
}

export function GenerationCard({ gen, email, downloadFolder }: GenerationCardProps) {
  const [expanded, setExpanded] = useState(true);
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null);

  const viewableImages = gen.images.filter((img) => img.status === "generated");

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden shadow-sm">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
        >
          <span className="flex-1 min-w-0">
            <span className="block text-sm font-medium text-gray-800 truncate">{gen.prompt}</span>
            <span className="block text-xs text-gray-400 mt-0.5">
              {new Date(gen.createdAt).toLocaleString()} · {gen.images.length} images ·{" "}
              {gen.aspectRatio ?? ""}
            </span>
          </span>
          <svg
            className={`w-4 h-4 text-gray-300 shrink-0 mt-0.5 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {expanded && (
          <div className="px-4 pb-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
              {gen.images.map((img) => {
                const viewIdx = viewableImages.indexOf(img);
                return (
                  <ImageTile
                    key={img.id}
                    img={img}
                    email={email}
                    downloadFolder={downloadFolder}
                    onOpen={viewIdx >= 0 ? () => setLightboxIdx(viewIdx) : undefined}
                  />
                );
              })}
            </div>
          </div>
        )}
      </div>
      {lightboxIdx !== null && (
        <Lightbox
          images={viewableImages}
          index={lightboxIdx}
          email={email}
          downloadFolder={downloadFolder}
          onClose={() => setLightboxIdx(null)}
          onPrev={() => setLightboxIdx((i) => Math.max(0, i! - 1))}
          onNext={() => setLightboxIdx((i) => Math.min(viewableImages.length - 1, i! + 1))}
        />
      )}
    </>
  );
}
