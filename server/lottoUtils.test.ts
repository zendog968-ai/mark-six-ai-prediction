import { describe, expect, it } from "vitest";
import {
  countConsecutivePairs,
  formatLottoNumber,
  hasExtremeParity,
  makeOddEvenLabel,
} from "../shared/lottoUtils";

describe("六合彩組合規則", () => {
  it("辨識六碼全單或全雙的極端組合", () => {
    expect(hasExtremeParity([1, 3, 5, 7, 9, 11])).toBe(true);
    expect(hasExtremeParity([2, 4, 6, 8, 10, 12])).toBe(true);
    expect(hasExtremeParity([1, 2, 7, 10, 15, 18])).toBe(false);
  });

  it("計算排序前後皆正確的連號對數與奇偶比", () => {
    expect(countConsecutivePairs([27, 16, 15, 31, 32, 7])).toBe(2);
    expect(makeOddEvenLabel([27, 16, 15, 31, 32, 7])).toBe("4 單 / 2 雙");
  });

  it("一律以兩位數格式呈現號碼", () => {
    expect(formatLottoNumber(4)).toBe("04");
    expect(formatLottoNumber(49)).toBe("49");
  });
});
