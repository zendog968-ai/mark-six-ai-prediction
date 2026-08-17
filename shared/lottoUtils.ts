export function formatLottoNumber(number: number) {
  return String(number).padStart(2, "0");
}

export function hasExtremeParity(numbers: number[]) {
  const oddCount = numbers.filter(number => number % 2 !== 0).length;
  return oddCount === 0 || oddCount === numbers.length;
}

export function countConsecutivePairs(numbers: number[]) {
  const sorted = [...numbers].sort((left, right) => left - right);
  return sorted.slice(1).filter((number, index) => number === sorted[index] + 1).length;
}

export function makeOddEvenLabel(numbers: number[]) {
  const oddCount = numbers.filter(number => number % 2 !== 0).length;
  return `${oddCount} 單 / ${numbers.length - oddCount} 雙`;
}
