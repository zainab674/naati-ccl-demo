import { Download, FileSpreadsheet } from "lucide-react";

const btn = "inline-flex h-9 items-center gap-2 rounded-lg bg-white px-3 text-sm font-medium text-ink shadow-sm ring-1 ring-slate-200 hover:bg-slate-50";

/** Shown next to every CSV upload: the empty format (header row) and, when there is one, a filled-in example. */
export default function CsvFormatButtons({ formatUrl, exampleUrl }: { formatUrl: string; exampleUrl?: string }) {
  return (
    <div className="flex flex-wrap gap-2">
      <a href={formatUrl} download className={btn}><Download className="size-4" /> Download CSV format</a>
      {exampleUrl && <a href={exampleUrl} download className={btn}><FileSpreadsheet className="size-4" /> Download example</a>}
    </div>
  );
}
