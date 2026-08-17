import LottoBall from "@/components/LottoBall";
import { ErrorState, LoadingState } from "@/components/PageState";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { trpc } from "@/lib/trpc";
import { ArrowDownAZ, ArrowUpAZ, ChevronLeft, ChevronRight, Database, ListFilter } from "lucide-react";
import { useMemo, useState } from "react";

export default function History() {
  const [page, setPage] = useState(1);
  const [direction, setDirection] = useState<"asc" | "desc">("desc");
  const input = useMemo(() => ({ page, pageSize: 25, direction }), [page, direction]);
  const history = trpc.lotto.history.useQuery(input);

  if (history.isLoading) return <LoadingState label="正在整理歷史開獎紀錄…" />;
  if (history.isError || !history.data) return <ErrorState />;

  const { draws, total, totalPages } = history.data;
  const firstRecord = (page - 1) * 25 + 1;
  const lastRecord = Math.min(page * 25, total);

  return (
    <div className="lotto-page">
      <header className="mb-8 flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
        <div>
          <div className="eyebrow"><Database className="h-3.5 w-3.5" /> simulated archive</div>
          <h1 className="mt-3 font-serif text-3xl font-semibold tracking-tight text-[#183a32] sm:text-4xl">歷史數據瀏覽</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-[#6a766d]">可依期數正序或倒序查看完整的 1,000 期模擬開獎資料集。</p>
        </div>
        <div className="flex items-center gap-3 rounded-2xl border border-[#dcd2c3] bg-[#faf8f3] px-4 py-3 text-sm">
          <ListFilter className="h-4 w-4 text-[#b88a42]" />
          <span className="text-[#768078]">資料筆數</span><strong className="font-semibold text-[#26483d]">{total.toLocaleString()}</strong>
        </div>
      </header>
      <section className="panel overflow-hidden p-0">
        <div className="flex flex-col justify-between gap-4 border-b border-[#ebe4d8] px-5 py-5 sm:flex-row sm:items-center sm:px-7">
          <div><p className="eyebrow">Draw history</p><h2 className="mt-2 font-serif text-xl font-semibold text-[#21463a]">模擬攪珠紀錄</h2></div>
          <Select value={direction} onValueChange={value => { setDirection(value as "asc" | "desc"); setPage(1); }}>
            <SelectTrigger className="w-full border-[#ddd4c7] bg-white text-sm text-[#4c5f55] sm:w-[185px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="desc"><span className="flex items-center gap-2"><ArrowDownAZ className="h-4 w-4" />期數：新至舊</span></SelectItem>
              <SelectItem value="asc"><span className="flex items-center gap-2"><ArrowUpAZ className="h-4 w-4" />期數：舊至新</span></SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left">
            <thead className="bg-[#fbfaf7] text-[11px] uppercase tracking-[.12em] text-[#8b8f83]"><tr><th className="px-6 py-4 font-semibold">期數</th><th className="px-5 py-4 font-semibold">日期</th><th className="px-5 py-4 font-semibold">6 個正選號碼</th><th className="px-5 py-4 font-semibold">特別號</th></tr></thead>
            <tbody>{draws.map(draw => <tr key={draw.drawNo} className="border-t border-[#eee8dc] transition-colors hover:bg-[#faf8f1]"><td className="px-6 py-4 font-semibold text-[#315548]">#{String(draw.drawNo).padStart(4, "0")}</td><td className="px-5 py-4 text-sm text-[#718076]">{new Date(draw.drawDate).toLocaleDateString("zh-HK")}</td><td className="px-5 py-3"><div className="flex gap-2">{draw.mainNumbers.map(number => <LottoBall key={number} number={number} size="sm" />)}</div></td><td className="px-5 py-3"><LottoBall number={draw.special} special size="sm" /></td></tr>)}</tbody>
          </table>
        </div>
        <div className="flex flex-col justify-between gap-4 border-t border-[#ebe4d8] bg-[#fbfaf7] px-5 py-4 sm:flex-row sm:items-center sm:px-7">
          <p className="text-xs text-[#7d887f]">顯示第 <strong className="font-semibold text-[#465e52]">{firstRecord}–{lastRecord}</strong> 筆，共 {total.toLocaleString()} 筆資料</p>
          <div className="flex items-center gap-2"><Button variant="outline" size="sm" onClick={() => setPage(current => Math.max(1, current - 1))} disabled={page === 1} className="border-[#d9d0c2] bg-white text-[#476055]"><ChevronLeft className="mr-1 h-4 w-4" />上一頁</Button><span className="min-w-20 text-center text-xs font-semibold text-[#556b5e]">{page} / {totalPages}</span><Button variant="outline" size="sm" onClick={() => setPage(current => Math.min(totalPages, current + 1))} disabled={page === totalPages} className="border-[#d9d0c2] bg-white text-[#476055]">下一頁<ChevronRight className="ml-1 h-4 w-4" /></Button></div>
        </div>
      </section>
    </div>
  );
}
