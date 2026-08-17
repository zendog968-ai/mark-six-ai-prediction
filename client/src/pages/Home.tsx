import LottoBall from "@/components/LottoBall";
import { ErrorState, LoadingState } from "@/components/PageState";
import { Badge } from "@/components/ui/badge";
import { trpc } from "@/lib/trpc";
import { ArrowDownRight, ArrowUpRight, CalendarDays, ChartNoAxesColumnIncreasing, Clock3, Crown, Sparkles } from "lucide-react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const temperatureClass = (temperature: string) => {
  if (temperature === "熱門") return "bg-[#e7f0e8] text-[#37604a] border-[#c3d8c8]";
  if (temperature === "冷門") return "bg-[#f5e9e4] text-[#985846] border-[#e7c9bd]";
  return "bg-[#f3eee5] text-[#756852] border-[#e4dacb]";
};

export default function Home() {
  const overview = trpc.lotto.overview.useQuery();
  if (overview.isLoading) return <LoadingState />;
  if (overview.isError || !overview.data) return <ErrorState />;

  const { stats, recentDraws, totalDraws } = overview.data;
  const hot = [...stats].sort((left, right) => right.frequency50 - left.frequency50).slice(0, 6);
  const gaps = [...stats].sort((left, right) => right.gap - left.gap).slice(0, 6);
  const distribution = [...stats]
    .sort((left, right) => left.number - right.number)
    .map(item => ({ ...item, label: String(item.number).padStart(2, "0") }));
  const hotCount = stats.filter(item => item.temperature === "熱門").length;
  const coldCount = stats.filter(item => item.temperature === "冷門").length;

  return (
    <div className="lotto-page">
      <header className="mb-8 flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
        <div>
          <div className="eyebrow"><Sparkles className="h-3.5 w-3.5" /> 模擬資料洞察</div>
          <h1 className="mt-3 font-serif text-3xl font-semibold tracking-tight text-[#183a32] sm:text-4xl">數據儀表板</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-[#6a766d]">以最近 50 期主號資料整理頻率與遺漏期，作為資料視覺化與機率權重實驗的觀察視窗。</p>
        </div>
        <div className="flex items-center gap-3 rounded-2xl border border-[#dcd2c3] bg-[#faf8f3] px-4 py-3 text-sm shadow-[0_8px_20px_rgba(50,45,35,.04)]">
          <CalendarDays className="h-4 w-4 text-[#b88a42]" />
          <span className="text-[#768078]">資料覆蓋</span><strong className="font-semibold text-[#26483d]">{totalDraws.toLocaleString()} 期</strong>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="metric-card bg-[#173a32] text-[#f8f0df]">
          <div className="flex items-start justify-between"><span className="metric-label text-[#b9c9be]">分析樣本</span><ChartNoAxesColumnIncreasing className="h-5 w-5 text-[#d6ad67]" /></div>
          <div className="mt-8 font-serif text-4xl font-semibold">{totalDraws.toLocaleString()}</div>
          <p className="mt-2 text-xs leading-5 text-[#bdcdc3]">每期 6 個正選號碼與 1 個特別號，均為可重現模擬資料。</p>
        </div>
        <div className="metric-card bg-[#fffdf8]">
          <div className="flex items-start justify-between"><span className="metric-label">近期熱門</span><ArrowUpRight className="h-5 w-5 text-[#4d7c60]" /></div>
          <div className="mt-8 flex items-end gap-3"><span className="font-serif text-4xl font-semibold text-[#23473a]">{hotCount}</span><span className="mb-1.5 text-sm text-[#718077]">個號碼</span></div>
          <p className="mt-2 text-xs leading-5 text-[#798278]">近 50 期主號出現 8 次或以上的描述性標籤。</p>
        </div>
        <div className="metric-card bg-[#fffdf8]">
          <div className="flex items-start justify-between"><span className="metric-label">近期冷門</span><ArrowDownRight className="h-5 w-5 text-[#b76e50]" /></div>
          <div className="mt-8 flex items-end gap-3"><span className="font-serif text-4xl font-semibold text-[#23473a]">{coldCount}</span><span className="mb-1.5 text-sm text-[#718077]">個號碼</span></div>
          <p className="mt-2 text-xs leading-5 text-[#798278]">近 50 期主號出現 4 次或以下的描述性標籤。</p>
        </div>
      </section>

      <section className="mt-6 grid gap-6 2xl:grid-cols-[minmax(0,1.75fr)_minmax(330px,.75fr)]">
        <div className="panel overflow-hidden p-0">
          <div className="flex flex-col justify-between gap-3 border-b border-[#ebe4d8] px-5 py-5 sm:flex-row sm:items-center sm:px-7">
            <div><p className="eyebrow">01 / Frequency</p><h2 className="mt-2 font-serif text-xl font-semibold text-[#21463a]">各號碼近 50 期主號出現分佈</h2></div>
            <span className="rounded-full bg-[#edf2ed] px-3 py-1.5 text-xs font-semibold text-[#4f6f59]">49 個觀察值</span>
          </div>
          <div className="h-[310px] px-2 pb-3 pt-5 sm:px-5">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distribution} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                <XAxis dataKey="label" tick={{ fill: "#819087", fontSize: 10 }} tickLine={false} axisLine={false} interval={3} />
                <YAxis tick={{ fill: "#819087", fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip cursor={{ fill: "#eff2ec" }} contentStyle={{ borderRadius: 14, border: "1px solid #e2dbcf", boxShadow: "0 12px 30px rgba(47, 57, 44, .12)" }} labelFormatter={value => `號碼 ${String(value).padStart(2, "0")}`} formatter={(value: number) => [value, "近 50 期次數"]} />
                <Bar dataKey="frequency50" radius={[5, 5, 0, 0]} maxBarSize={17}>{distribution.map(item => <Cell key={item.number} fill={item.temperature === "熱門" ? "#3d7155" : item.temperature === "冷門" ? "#c78465" : "#b8a77f"} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <aside className="panel p-5 sm:p-6">
          <div className="flex items-start justify-between"><div><p className="eyebrow">02 / Gap</p><h2 className="mt-2 font-serif text-xl font-semibold text-[#21463a]">遺漏期數排行</h2></div><Clock3 className="h-5 w-5 text-[#b88a42]" /></div>
          <div className="mt-5 divide-y divide-[#eee7db]">
            {gaps.map((item, index) => <div key={item.number} className="flex items-center justify-between py-3 first:pt-0"><div className="flex items-center gap-3"><span className="w-4 text-xs font-semibold text-[#9b927f]">{String(index + 1).padStart(2, "0")}</span><LottoBall number={item.number} size="sm" /><span className="text-sm font-semibold text-[#365347]">號碼 {String(item.number).padStart(2, "0")}</span></div><div className="text-right"><strong className="text-sm text-[#6e5431]">{item.gap}</strong><span className="ml-1 text-xs text-[#859087]">期</span></div></div>)}
          </div>
        </aside>
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-2">
        <div className="panel p-5 sm:p-7"><div className="flex items-center justify-between"><div><p className="eyebrow">03 / Hot & Cold</p><h2 className="mt-2 font-serif text-xl font-semibold text-[#21463a]">熱門號碼觀察</h2></div><Crown className="h-5 w-5 text-[#b88a42]" /></div><div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">{hot.map(item => <div key={item.number} className="rounded-2xl border border-[#dbe6dc] bg-[#f6faf6] p-3"><div className="flex items-center justify-between"><LottoBall number={item.number} size="sm" /><Badge className={`border text-[10px] shadow-none ${temperatureClass(item.temperature)}`}>{item.temperature}</Badge></div><p className="mt-4 text-xs text-[#77847b]">50 期頻率 <strong className="ml-1 text-[#315a42]">{item.frequency50}</strong></p></div>)}</div></div>
        <div className="panel overflow-hidden p-0"><div className="border-b border-[#ebe4d8] px-5 py-5 sm:px-7"><p className="eyebrow">04 / Recent draws</p><h2 className="mt-2 font-serif text-xl font-semibold text-[#21463a]">最近 20 期開獎紀錄</h2></div><div className="max-h-[350px] overflow-auto"><table className="w-full min-w-[640px] text-left"><thead className="sticky top-0 bg-[#fbfaf7] text-[11px] uppercase tracking-[.12em] text-[#8b8f83]"><tr><th className="px-5 py-3 font-semibold">期數</th><th className="px-4 py-3 font-semibold">日期</th><th className="px-4 py-3 font-semibold">正選號碼</th><th className="px-4 py-3 font-semibold">特別號</th></tr></thead><tbody>{recentDraws.map(draw => <tr key={draw.drawNo} className="border-t border-[#eee8dc] transition-colors hover:bg-[#faf8f1]"><td className="px-5 py-3 text-sm font-semibold text-[#335548]">#{String(draw.drawNo).padStart(4, "0")}</td><td className="px-4 py-3 text-xs text-[#7b867d]">{new Date(draw.drawDate).toLocaleDateString("zh-HK")}</td><td className="px-4 py-3"><div className="flex gap-1.5">{draw.mainNumbers.map(number => <LottoBall key={number} number={number} size="sm" />)}</div></td><td className="px-4 py-3"><LottoBall number={draw.special} special size="sm" /></td></tr>)}</tbody></table></div></div>
      </section>
    </div>
  );
}
