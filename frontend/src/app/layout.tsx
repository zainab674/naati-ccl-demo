import type { Metadata } from "next";
import { Geist, Inter } from "next/font/google";

import { ThemeProvider } from "@/components/Theme";
import { getTheme } from "@/lib/content";
import { DEFAULT_THEME, paletteCss } from "@/lib/theme";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin", "latin-ext"] });
const geist = Geist({ variable: "--font-geist", subsets: ["latin", "latin-ext"] });

export async function generateMetadata(): Promise<Metadata> {
  const name = (await getTheme())?.name || DEFAULT_THEME.name;
  return {
    title: { default: `${name} | NAATI CCL Practice`, template: `%s | ${name}` },
    description:
      "NAATI CCL practice dialogues and mock tests in English and Filipino, Hindi, Mandarin, Punjabi, Arabic, Nepali or Vietnamese, with detailed feedback on every deduction.",
  };
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // The admin's theme (Settings > Theme) is read per request, so a change shows on the next page load.
  const theme = (await getTheme()) ?? DEFAULT_THEME;
  const css = paletteCss(theme.palette);
  return (
    <html lang="en" className={`${inter.variable} ${geist.variable} h-full antialiased`}>
      <head>{css && <style id="brand-theme">{css}</style>}</head>
      <body className="min-h-full font-sans"><ThemeProvider theme={theme}>{children}</ThemeProvider></body>
    </html>
  );
}
