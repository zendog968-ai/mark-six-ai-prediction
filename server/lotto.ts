import { asc, count, desc } from "drizzle-orm";
import { lottoDraws, lottoNumberStats, lottoRecommendations } from "../drizzle/schema";
import { getHistoryOffset, getTotalPages, parseRecommendationNumbers } from "../shared/lottoDataUtils";
import { getDb } from "./db";

function asDraw(row: typeof lottoDraws.$inferSelect) {
  return {
    drawNo: row.drawNo,
    drawDate: row.drawDate,
    mainNumbers: [row.main1, row.main2, row.main3, row.main4, row.main5, row.main6],
    special: row.special,
  };
}

async function requireDb() {
  const db = await getDb();
  if (!db) throw new Error("資料庫目前無法連線。");
  return db;
}

export async function getLottoOverview() {
  const db = await requireDb();
  const [stats, recentDraws, drawCount] = await Promise.all([
    db.select().from(lottoNumberStats).orderBy(desc(lottoNumberStats.frequency50)),
    db.select().from(lottoDraws).orderBy(desc(lottoDraws.drawNo)).limit(20),
    db.select({ value: count() }).from(lottoDraws),
  ]);
  return {
    totalDraws: Number(drawCount[0]?.value ?? 0),
    stats,
    recentDraws: recentDraws.map(asDraw),
  };
}

export async function getLottoRecommendations() {
  const db = await requireDb();
  const recommendations = await db
    .select()
    .from(lottoRecommendations)
    .orderBy(asc(lottoRecommendations.setIndex));
  return recommendations.map(recommendation => ({
    setIndex: recommendation.setIndex,
    numbers: parseRecommendationNumbers(recommendation.numbers),
    oddEven: recommendation.oddEven,
    numberSum: recommendation.numberSum,
    consecutivePairs: recommendation.consecutivePairs,
    createdAt: recommendation.createdAt,
  }));
}

export async function getLottoHistory(page: number, pageSize: number, direction: "asc" | "desc") {
  const db = await requireDb();
  const sortExpression = direction === "asc" ? asc(lottoDraws.drawNo) : desc(lottoDraws.drawNo);
  const [draws, drawCount] = await Promise.all([
    db.select().from(lottoDraws).orderBy(sortExpression).limit(pageSize).offset(getHistoryOffset(page, pageSize)),
    db.select({ value: count() }).from(lottoDraws),
  ]);
  const total = Number(drawCount[0]?.value ?? 0);
  return {
    page,
    pageSize,
    total,
    totalPages: getTotalPages(total, pageSize),
    draws: draws.map(asDraw),
  };
}
