import { BookOpen, FileAudio, FileText, FileVideo, Languages, Link as LinkIcon, NotebookPen, type LucideIcon } from "lucide-react";

export const RESOURCE_TYPES = ["Ebook", "Glossary", "Worksheet", "Audio", "Video", "Article", "Link"] as const;
export type ResourceType = (typeof RESOURCE_TYPES)[number];

export const TYPE_LABEL: Record<ResourceType, string> = {
  Ebook: "Ebooks", Glossary: "Glossaries", Worksheet: "Worksheets", Audio: "Audio", Video: "Video", Article: "Articles", Link: "Links",
};

export const TYPE_ICON: Record<ResourceType, LucideIcon> = {
  Ebook: BookOpen, Glossary: Languages, Worksheet: NotebookPen, Audio: FileAudio, Video: FileVideo, Article: FileText, Link: LinkIcon,
};

export type ResourceItem = {
  id: string; title: string; description: string; type: ResourceType; topic: string | null; is_free: boolean;
  language: string | null; language_name: string | null; has_file: boolean; file_name: string; file_size: number;
  content_type: string; has_link: boolean; locked?: boolean;
};

export type ResourceDetail = ResourceItem & { html_content: string; external_url: string; file_url: string | null };

export function fileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
