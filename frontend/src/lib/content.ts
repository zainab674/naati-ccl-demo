/** Server-side reads of public content from the backend (rendered per request so admin edits show immediately). */
import { connection } from "next/server";

const API_URL = process.env.API_URL || "http://127.0.0.1:8000";

export type Feature = { title: string; body: string };
export type HomeContent = {
  seo_title: string; seo_description: string; hero_title: string; hero_subtitle: string; hero_cta: string;
  features: Feature[]; how_it_works: Feature[]; disclaimer: string;
};
export type Faq = { q: string; a: string }[];
export type Review = { name: string; text: string; rating?: number; placeholder?: boolean };
export type PlanContent = {
  seo_title: string; seo_description: string; title: string; tagline: string; description: string;
  included: string[]; cta: string; contact_email?: string;
};
export type LegalContent = { title: string; draft?: boolean; updated?: string; sections: { heading: string; body: string }[] };
export type PublicPlan = { key: string; name: string; description: string; features: string[]; price_display: string; contact_only: boolean };

async function getJson<T>(path: string): Promise<T | null> {
  await connection();
  try {
    const r = await fetch(`${API_URL}/api${path}`, { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null; // backend unreachable: pages render their empty states instead of failing
  }
}

export async function getContent<T>(key: string): Promise<T | null> {
  const r = await getJson<{ value: T }>(`/public/content/${key}`);
  return r?.value ?? null;
}

export async function getPlans(): Promise<PublicPlan[]> {
  return (await getJson<PublicPlan[]>("/public/plans")) ?? [];
}

export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
