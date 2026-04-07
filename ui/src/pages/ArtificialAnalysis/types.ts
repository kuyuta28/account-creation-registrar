export const ASPECT_RATIO_DIMENSIONS = {
  "1:1 (Square)": [
    { label: "512×512", w: 512, h: 512 },
    { label: "768×768", w: 768, h: 768 },
    { label: "1024×1024", w: 1024, h: 1024 },
    { label: "1536×1536", w: 1536, h: 1536 },
  ],
  "16:9 (Landscape)": [
    { label: "1024×576", w: 1024, h: 576 },
    { label: "1280×720 (HD)", w: 1280, h: 720 },
    { label: "1920×1080 (Full HD)", w: 1920, h: 1080 },
  ],
  "9:16 (Portrait)": [
    { label: "576×1024", w: 576, h: 1024 },
    { label: "720×1280 (HD)", w: 720, h: 1280 },
    { label: "1080×1920 (Full HD)", w: 1080, h: 1920 },
  ],
  "4:3": [
    { label: "768×576", w: 768, h: 576 },
    { label: "1024×768", w: 1024, h: 768 },
    { label: "1600×1200", w: 1600, h: 1200 },
  ],
  "3:4": [
    { label: "576×768", w: 576, h: 768 },
    { label: "768×1024", w: 768, h: 1024 },
    { label: "1200×1600", w: 1200, h: 1600 },
  ],
} as const;

export type AspectRatioKey = keyof typeof ASPECT_RATIO_DIMENSIONS;
export type DimensionOption = { label: string; w: number; h: number };
export const AR_LABELS = Object.keys(ASPECT_RATIO_DIMENSIONS) as AspectRatioKey[];

export type { AAImage, AAGeneration, AAModel, Account } from "../../api/client";
