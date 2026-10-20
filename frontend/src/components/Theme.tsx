"use client";

/** The admin-chosen theme (Settings > Theme): name, tagline and logo for the whole app. Colours are applied by the
 * root layout as CSS variables, so every `brand-*` Tailwind class follows the chosen colour. */
import { createContext, type ReactNode, useContext } from "react";

import { DEFAULT_THEME, type Theme } from "@/lib/theme";

const ThemeCtx = createContext<Theme>(DEFAULT_THEME);

export function ThemeProvider({ theme, children }: { theme: Theme; children: ReactNode }) {
  return <ThemeCtx.Provider value={theme}>{children}</ThemeCtx.Provider>;
}

export const useTheme = () => useContext(ThemeCtx);

/** The platform name as plain text (e.g. in a footer). */
export function BrandName() {
  return <>{useTheme().name}</>;
}
