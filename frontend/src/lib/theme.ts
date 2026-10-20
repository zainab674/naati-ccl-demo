/** Theme data shared by the server (root layout) and the client (ThemeProvider). No "use client" here. */

export type Theme = {
  brand_color: string; name: string; tagline: string; logo_url: string | null; palette: Record<string, string>;
};

export const DEFAULT_THEME: Theme = { brand_color: "#1f6778", name: "Benchmark Education", tagline: "NAATI CCL PREP", logo_url: null, palette: {} };

/** CSS that overrides the default brand palette (globals.css) with the admin's chosen one. */
export function paletteCss(palette: Record<string, string>) {
  const vars = Object.entries(palette).filter(([k, v]) => /^\d+$/.test(k) && /^#[0-9a-f]{6}$/i.test(v))
    .map(([k, v]) => `--color-brand-${k}:${v};`).join("");
  return vars ? `:root:root{${vars}}` : "";
}
