import { describe, expect, it } from "vitest";
import { DISCLAIMER_STICKY_CLASS, DISCLAIMER_TEXT } from "../shared/disclaimer";

describe("全站免責聲明版型", () => {
  it("使用共用的正確免責聲明文字", () => {
    expect(DISCLAIMER_TEXT).toBe("系統僅供統計教育與實驗用途，無法可靠預測真實開獎結果。");
  });

  it("具備桌面與行動版捲動後可見所需的 sticky、top 與層級設定", () => {
    expect(DISCLAIMER_STICKY_CLASS).toContain("sticky");
    expect(DISCLAIMER_STICKY_CLASS).toContain("top-16");
    expect(DISCLAIMER_STICKY_CLASS).toContain("lg:top-5");
    expect(DISCLAIMER_STICKY_CLASS).toContain("z-20");
  });
});
