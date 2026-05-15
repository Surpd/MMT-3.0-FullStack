// Minimal Telegram WebApp helpers — zero backend, only window.Telegram bridge.
declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready?: () => void;
        expand?: () => void;
        requestFullscreen?: () => void;
        disableVerticalSwipes?: () => void;
        enableClosingConfirmation?: () => void;
        isClosingConfirmationEnabled?: boolean;
        close?: () => void;
        openTelegramLink?: (url: string) => void;
        initDataUnsafe?: {
          user?: {
            id: number;
            first_name?: string;
            last_name?: string;
            username?: string;
            photo_url?: string;
          };
        };
        sendData?: (data: string) => void;
        HapticFeedback?: {
          impactOccurred?: (style: "light" | "medium" | "heavy") => void;
          notificationOccurred?: (type: "error" | "success" | "warning") => void;
        };
        themeParams?: Record<string, string>;
      };
    };
  }
}

export function getTelegramUser() {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp?.initDataUnsafe?.user ?? null;
}

export function tgSendData(payload: Record<string, unknown>) {
  try {
    const json = JSON.stringify(payload);
    window.Telegram?.WebApp?.sendData?.(json);
    if (typeof window !== "undefined") {
      // eslint-disable-next-line no-console
      console.log("[tg.sendData]", payload);
    }
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn("tgSendData failed", e);
  }
}

export function tgHaptic(style: "light" | "medium" | "heavy" = "light") {
  try {
    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.(style);
  } catch {
    /* no-op */
  }
}

export function tgNotify(type: "success" | "error" | "warning") {
  try {
    window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.(type);
  } catch {
    /* no-op */
  }
}

export function tgClose() {
  try {
    window.Telegram?.WebApp?.close?.();
  } catch {
    /* no-op */
  }
}

export function tgOpenTelegramLink(url: string) {
  try {
    const wa = window.Telegram?.WebApp;
    if (wa?.openTelegramLink) {
      wa.openTelegramLink(url);
    } else if (typeof window !== "undefined") {
      window.open(url, "_blank");
    }
  } catch {
    /* no-op */
  }
}

export function tgInit() {
  if (typeof window === "undefined") return;
  const wa = window.Telegram?.WebApp;
  if (!wa) return;
  try {
    wa.ready?.();
    wa.expand?.();
    wa.enableClosingConfirmation?.();
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (wa as any).isClosingConfirmationEnabled = true;
    } catch {
      /* no-op */
    }
  } catch {
    /* no-op */
  }
}
