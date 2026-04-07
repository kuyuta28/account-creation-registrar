/**
 * sentry.ts — Sentry SDK initialization for React UI.
 * No-op nếu DSN không được cấu hình (VITE_SENTRY_DSN rỗng).
 */
import * as Sentry from "@sentry/react";

const DSN = "https://02e1b958d2e9226ac579eb96a3be5b1a@o4511148563890176.ingest.us.sentry.io/4511148594954240";
const ENV = import.meta.env.VITE_SENTRY_ENV ?? "production";

export const initSentry = (): void => {
  if (!DSN) return;

  Sentry.init({
    dsn: DSN,
    environment: ENV,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0.0,
    replaysOnErrorSampleRate: 1.0,
  });
};

export { Sentry };
