import { describe, expect, it } from "vitest";
import { getHistoryOffset, getTotalPages, parseRecommendationNumbers } from "../shared/lottoDataUtils";

describe("六合彩資料整形與分頁規則", () => {
  it("解析合法的六碼推薦 JSON", () => {
    expect(parseRecommendationNumbers("[3, 14, 21, 29, 37, 45]")).toEqual([3, 14, 21, 29, 37, 45]);
  });

  it("拒絕無效 JSON、非六碼、重複號碼與範圍外號碼", () => {
    expect(() => parseRecommendationNumbers("not-json")).toThrow("有效 JSON");
    expect(() => parseRecommendationNumbers("[1,2,3]")).toThrow("六個整數");
    expect(() => parseRecommendationNumbers("[1,1,3,4,5,6]")).toThrow("重複");
    expect(() => parseRecommendationNumbers("[1,2,3,4,5,50]")).toThrow("範圍外");
  });

  it("依頁碼與排序資料量計算正確分頁邊界", () => {
    expect(getHistoryOffset(1, 25)).toBe(0);
    expect(getHistoryOffset(4, 25)).toBe(75);
    expect(getTotalPages(1000, 25)).toBe(40);
    expect(getTotalPages(0, 25)).toBe(1);
    expect(() => getHistoryOffset(0, 25)).toThrow("正整數");
  });
});
