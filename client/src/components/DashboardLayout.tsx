import {
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  Database,
  Menu,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useLocation } from "wouter";
import { DISCLAIMER_STICKY_CLASS, DISCLAIMER_TEXT } from "../../../shared/disclaimer";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "./ui/sidebar";

const menuItems = [
  { icon: BarChart3, label: "數據儀表板", caption: "統計總覽", path: "/" },
  { icon: BrainCircuit, label: "AI 推薦", caption: "權重組合", path: "/recommendations" },
  { icon: Database, label: "歷史數據", caption: "1,000 期模擬紀錄", path: "/history" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [location, setLocation] = useLocation();
  return (
    <SidebarProvider>
      <Sidebar collapsible="icon" className="border-r border-[#d9d2c4] bg-[#173a32] text-[#f7f0df]">
        <SidebarHeader className="h-auto p-4 group-data-[collapsible=icon]:p-2">
          <button
            onClick={() => setLocation("/")}
            className="flex w-full items-center gap-3 rounded-2xl px-2 py-2 text-left transition-colors hover:bg-white/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#d3aa62] group-data-[collapsible=icon]:justify-center"
            aria-label="回到數據儀表板"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#d3aa62] text-[#173a32] shadow-[0_7px_18px_rgba(0,0,0,.16)]">
              <Sparkles className="h-5 w-5" />
            </span>
            <span className="min-w-0 group-data-[collapsible=icon]:hidden">
              <span className="block font-serif text-lg font-semibold tracking-wide">Lotto Atelier</span>
              <span className="mt-0.5 block text-[10px] font-medium uppercase tracking-[0.22em] text-[#d3aa62]">Analytics Lab</span>
            </span>
          </button>
        </SidebarHeader>
        <SidebarContent className="px-3 py-4">
          <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#9eb4a9] group-data-[collapsible=icon]:hidden">
            分析工作台
          </p>
          <SidebarMenu>
            {menuItems.map(item => {
              const active = location === item.path;
              return (
                <SidebarMenuItem key={item.path}>
                  <SidebarMenuButton
                    isActive={active}
                    onClick={() => setLocation(item.path)}
                    tooltip={item.label}
                    className="h-auto rounded-xl px-3 py-3 text-[#dfe9df] transition-all hover:bg-white/8 hover:text-white data-[active=true]:bg-[#f6f0e3] data-[active=true]:text-[#173a32] data-[active=true]:shadow-sm"
                  >
                    <item.icon className="h-[18px] w-[18px]" />
                    <span className="group-data-[collapsible=icon]:hidden">
                      <span className="block text-sm font-semibold">{item.label}</span>
                      <span className={`mt-0.5 block text-[11px] ${active ? "text-[#5b6f63]" : "text-[#aebfb5]"}`}>{item.caption}</span>
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        </SidebarContent>
        <SidebarFooter className="p-4 group-data-[collapsible=icon]:p-2">
          <div className="rounded-2xl border border-white/10 bg-white/[.045] p-3 group-data-[collapsible=icon]:hidden">
            <div className="flex items-center gap-2 text-xs font-semibold text-[#f3e6cb]">
              <ShieldCheck className="h-4 w-4 text-[#d3aa62]" /> 模擬資料集
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-[#b5c5bc]">1,000 期可重現樣本，供統計演示與模型實驗。</p>
          </div>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset className="min-w-0 bg-[#f5f1e9]">
        <div className="sticky top-0 z-30 flex items-center border-b border-[#ded7ca] bg-[#f5f1e9]/90 px-4 py-3 backdrop-blur-xl lg:hidden">
          <SidebarTrigger className="mr-3 rounded-lg border border-[#d7cdbc] bg-white text-[#173a32]" />
          <span className="font-serif text-base font-semibold text-[#173a32]">Lotto Atelier</span>
        </div>
        <main className="min-h-screen px-4 pb-10 pt-5 sm:px-7 lg:px-10 lg:pt-8">
          <div className={DISCLAIMER_STICKY_CLASS}>
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#a27635]" />
            <p className="text-sm font-medium leading-6">{DISCLAIMER_TEXT}</p>
          </div>
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
