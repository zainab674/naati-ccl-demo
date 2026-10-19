import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/content";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["", "/self-study", "/coaching", "/pricing", "/terms", "/privacy", "/signup"].map((path) => ({
    url: `${SITE_URL}${path}`,
    changeFrequency: "weekly",
    priority: path === "" ? 1 : 0.6,
  }));
}
