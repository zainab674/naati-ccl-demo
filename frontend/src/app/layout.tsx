import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin", "latin-ext"] });

export const metadata: Metadata = {
  title: { default: "Benchmark Education | NAATI CCL Practice", template: "%s | Benchmark Education" },
  description:
    "NAATI CCL practice dialogues and mock tests in English and Filipino, Hindi, Mandarin, Punjabi, Arabic, Nepali or Vietnamese, with detailed feedback on every deduction.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full font-sans">{children}</body>
    </html>
  );
}
