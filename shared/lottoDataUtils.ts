export function parseRecommendationNumbers(serialized: string) {
  let parsed: unknown;
  try {
    parsed = JSON.parse(serialized);
  } catch {
    throw new Error("推薦組合格式不是有效 JSON。");
  }
  if (!Array.isArray(parsed) || parsed.length !== 6 || !parsed.every(value => Number.isInteger(value))) {
    throw new Error("推薦組合必須包含六個整數號碼。");
  }
  const numbers = parsed as number[];
  if (new Set(numbers).size !== 6 || numbers.some(number => number < 1 || number > 49)) {
    throw new Error("推薦組合含有重複或範圍外號碼。");
  }
  return numbers;
}

export function getHistoryOffset(page: number, pageSize: number) {
  if (!Number.isInteger(page) || !Number.isInteger(pageSize) || page < 1 || pageSize < 1) {
    throw new Error("分頁參數必須為正整數。");
  }
  return (page - 1) * pageSize;
}

export function getTotalPages(total: number, pageSize: number) {
  if (!Number.isInteger(total) || total < 0 || !Number.isInteger(pageSize) || pageSize < 1) {
    throw new Error("總筆數與每頁筆數必須為合法整數。");
  }
  return Math.max(1, Math.ceil(total / pageSize));
}
