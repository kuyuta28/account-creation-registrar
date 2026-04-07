import { ASPECT_RATIO_DIMENSIONS, AR_LABELS } from "./types";
import { useAAPage } from "./useAAPage";
import { GenerationCard } from "./GenerationCard";

export default function ArtificialAnalysisPage() {
  const {
    accounts,
    selectedEmail,
    setSelectedEmail,
    balance,
    sessionError,
    filteredModels,
    selectedIds,
    setSelectedIds,
    modelSearch,
    setModelSearch,
    toggleModel,
    selectTop,
    prompt,
    setPrompt,
    aspectRatio,
    setAspectRatio,
    dimension,
    setDimension,
    gensPerModel,
    setGensPerModel,
    mode,
    setMode,
    generating,
    generateError,
    handleGenerate,
    estCost,
    history,
    historyLoading,
    hasMore,
    loadHistory,
    downloadFolder,
    handlePickFolder,
  } = useAAPage();

  return (
    <div className="h-full flex flex-col bg-gray-50 overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-white border-b border-gray-100 shrink-0 flex-wrap">
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-5 h-5 rounded bg-violet-600 flex items-center justify-center">
            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
          <span className="text-sm font-semibold text-gray-800">Artificial Analysis</span>
          <span className="text-xs text-gray-400 font-mono">Image Lab</span>
        </div>
        <span className="flex-1" />
        {accounts.length > 0 ? (
          <div className="flex items-center gap-2 shrink-0">
            <select
              value={selectedEmail}
              onChange={(e) => setSelectedEmail(e.target.value)}
              className="text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-1 focus:ring-violet-400 max-w-[200px]"
            >
              {accounts.map((a) => (
                <option key={a.email} value={a.email}>
                  {a.email}
                </option>
              ))}
            </select>
            {balance !== null && (
              <span className="text-xs font-mono text-emerald-600 bg-emerald-50 px-2 py-1 rounded-md border border-emerald-100">
                ${parseFloat(balance).toFixed(4)} credits
              </span>
            )}
            {sessionError && (
              <span className="text-xs text-red-500 truncate max-w-[160px]" title={sessionError}>
                ⚠ {sessionError}
              </span>
            )}
          </div>
        ) : (
          <span className="text-xs text-gray-400 italic">No saved sessions</span>
        )}
        {/* Download folder picker */}
        <div className="flex items-center gap-1.5 shrink-0 border-l border-gray-100 pl-3 ml-1">
          <svg className="w-3.5 h-3.5 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
          </svg>
          <span
            className="text-xs text-gray-500 max-w-[160px] truncate"
            title={downloadFolder || "Chưa chọn thư mục"}
          >
            {downloadFolder ? downloadFolder.split(/[\\/]/).pop() : <span className="italic text-gray-400">Chưa chọn folder</span>}
          </span>
          <button
            onClick={handlePickFolder}
            className="text-xs px-2 py-1 rounded-md border border-gray-200 text-gray-500 hover:border-violet-300 hover:text-violet-600 transition-colors"
          >
            {downloadFolder ? "Đổi" : "Chọn"}
          </button>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left controls */}
        <div className="w-72 shrink-0 flex flex-col border-r border-gray-100 bg-white overflow-y-auto">
          {/* Mode tabs */}
          <div className="flex border-b border-gray-100">
            {(["text_to_image", "image_editing"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 py-2 text-xs font-medium transition-colors ${
                  mode === m
                    ? "text-violet-600 border-b-2 border-violet-500"
                    : "text-gray-400 hover:text-gray-600"
                }`}
              >
                {m === "text_to_image" ? "Text → Image" : "Image Editing"}
              </button>
            ))}
          </div>

          {/* Prompt */}
          <div className="p-3 border-b border-gray-50">
            <label className="block text-xs font-medium text-gray-500 mb-1">Prompt</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter text to generate an image..."
              rows={3}
              maxLength={300}
              className="w-full text-sm border border-gray-200 rounded-md px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-violet-400"
            />
            <div className={`text-right text-xs mt-0.5 ${prompt.length >= 280 ? "text-red-400" : "text-gray-300"}`}>
              {prompt.length}/300
            </div>
          </div>

          {/* Aspect Ratio + Dimensions + Gens — compact 1 block */}
          <div className="px-3 py-2 border-b border-gray-50 flex flex-col gap-2">
            {/* Row 1: AR + Gens per model */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 shrink-0 w-6">AR</span>
              <div className="flex flex-wrap gap-1 flex-1">
                {AR_LABELS.map((ar) => {
                  const short = ar.replace(/ \(.*\)/, "");
                  return (
                    <button
                      key={ar}
                      onClick={() => { setAspectRatio(ar); setDimension(ASPECT_RATIO_DIMENSIONS[ar][0]); }}
                      className={`px-1.5 py-0.5 text-xs rounded border transition-colors ${
                        aspectRatio === ar
                          ? "bg-violet-50 border-violet-300 text-violet-700"
                          : "border-gray-200 text-gray-500 hover:border-gray-300"
                      }`}
                    >
                      {short}
                    </button>
                  );
                })}
              </div>
              <span className="text-xs text-gray-400 shrink-0">×</span>
              <div className="flex gap-1 shrink-0">
                {[1, 2, 3, 4].map((n) => (
                  <button
                    key={n}
                    onClick={() => setGensPerModel(n)}
                    className={`w-6 h-5 text-xs rounded border transition-colors ${
                      gensPerModel === n
                        ? "bg-violet-50 border-violet-300 text-violet-700"
                        : "border-gray-200 text-gray-500 hover:border-gray-300"
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>
            {/* Row 2: Dimensions */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 shrink-0 w-6">px</span>
              <div className="flex flex-wrap gap-1">
                {ASPECT_RATIO_DIMENSIONS[aspectRatio].map((d) => (
                  <button
                    key={d.label}
                    onClick={() => setDimension(d)}
                    className={`px-1.5 py-0.5 text-xs rounded border transition-colors ${
                      dimension.label === d.label
                        ? "bg-violet-50 border-violet-300 text-violet-700"
                        : "border-gray-200 text-gray-500 hover:border-gray-300"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Models list */}
          <div className="p-3 flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-medium text-gray-500">
                Models{" "}
                <span className="text-violet-500">({selectedIds.size} selected)</span>
              </label>
              <div className="flex gap-1">
                <button
                  onClick={() => selectTop(5)}
                  className="text-xs text-violet-500 hover:text-violet-700"
                >
                  Top 5
                </button>
                <span className="text-gray-300">·</span>
                <button
                  onClick={() => selectTop(10)}
                  className="text-xs text-violet-500 hover:text-violet-700"
                >
                  Top 10
                </button>
                <span className="text-gray-300">·</span>
                <button
                  onClick={() => setSelectedIds(new Set())}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  Clear
                </button>
              </div>
            </div>
            <input
              value={modelSearch}
              onChange={(e) => setModelSearch(e.target.value)}
              placeholder="Search models..."
              className="text-xs border border-gray-200 rounded-md px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-violet-400"
            />
            <div className="flex-1 overflow-y-auto space-y-0.5 min-h-0">
              {filteredModels.map((m) => {
                const price =
                  mode === "text_to_image"
                    ? m.ttiPricePerGeneration
                    : m.itiPricePerGeneration;
                const elo = mode === "text_to_image" ? m.ttiElo : m.itiElo;
                const available =
                  mode === "text_to_image" ? m.hasTtiEndpoint : m.hasItiEndpoint;
                return (
                  <label
                    key={m.id}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-colors ${
                      selectedIds.has(m.id)
                        ? "bg-violet-50"
                        : available
                          ? "hover:bg-gray-50"
                          : "opacity-40 cursor-not-allowed"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(m.id)}
                      disabled={!available}
                      onChange={() => available && toggleModel(m.id)}
                      className="accent-violet-600"
                    />
                    <span className="flex-1 min-w-0">
                      <span className="block text-xs font-medium text-gray-700 truncate">
                        {m.name}
                      </span>
                      <span className="block text-xs text-gray-400">{m.creator}</span>
                    </span>
                    <span className="shrink-0 text-right">
                      {elo != null && (
                        <span className="block text-xs text-gray-400">{elo.toFixed(0)}</span>
                      )}
                      {price != null && (
                        <span className="block text-xs font-mono text-gray-500">
                          ${price.toFixed(3)}
                        </span>
                      )}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Generate button */}
          <div className="p-3 border-t border-gray-100 shrink-0">
            {generateError && (
              <div className="text-xs text-red-500 mb-2 line-clamp-2">{generateError}</div>
            )}
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-400">
                {selectedIds.size} models · {gensPerModel}x · est. ~${estCost.toFixed(3)}
              </span>
            </div>
            <button
              onClick={handleGenerate}
              disabled={!selectedEmail || selectedIds.size === 0 || !prompt.trim()}
              className="w-full flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {generating ? (
                <span className="w-4 h-4 border border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
              )}
              Start Generation
              {selectedIds.size > 0 && ` (${selectedIds.size * gensPerModel} imgs)`}
            </button>
          </div>
        </div>

        {/* Right: history */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-700">Generation History</h2>
            <button
              onClick={() => loadHistory(true)}
              disabled={historyLoading}
              className="text-xs text-violet-500 hover:text-violet-700 disabled:opacity-50"
            >
              {historyLoading ? "Loading..." : "Refresh"}
            </button>
          </div>

          {history.length === 0 && !historyLoading && (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400">
              <svg
                className="w-10 h-10 mb-2 opacity-30"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <p className="text-sm">No generations yet</p>
              <p className="text-xs mt-1">Select models and enter a prompt to get started</p>
            </div>
          )}

          <div className="space-y-6">
            {history.map((gen) => (
              <GenerationCard
                key={gen.id}
                gen={gen}
                email={selectedEmail}
                downloadFolder={downloadFolder}
              />
            ))}
          </div>

          {hasMore && (
            <div className="mt-4 text-center">
              <button
                onClick={() => loadHistory(false)}
                disabled={historyLoading}
                className="text-xs text-violet-500 hover:text-violet-700 disabled:opacity-50"
              >
                {historyLoading ? "Loading..." : "Load more"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
