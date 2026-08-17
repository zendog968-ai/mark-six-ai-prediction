import { AlertCircle, LoaderCircle } from "lucide-react";

export function LoadingState({ label = "正在整理模擬資料…" }: { label?: string }) {
  return <div className="panel flex min-h-72 items-center justify-center gap-3 text-sm text-[#62736b]"><LoaderCircle className="h-5 w-5 animate-spin text-[#b98a42]" />{label}</div>;
}

export function ErrorState({ label = "資料暫時無法載入，請稍後重新整理。" }: { label?: string }) {
  return <div className="panel flex min-h-48 items-center justify-center gap-3 text-sm text-[#9e4739]"><AlertCircle className="h-5 w-5" />{label}</div>;
}
