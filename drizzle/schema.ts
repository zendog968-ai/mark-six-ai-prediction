import { int, mysqlEnum, mysqlTable, text, timestamp, varchar } from "drizzle-orm/mysql-core";

/**
 * Core user table backing auth flow.
 * Extend this file with additional tables as your product grows.
 * Columns use camelCase to match both database fields and generated types.
 */
export const users = mysqlTable("users", {
  /**
   * Surrogate primary key. Auto-incremented numeric value managed by the database.
   * Use this for relations between tables.
   */
  id: int("id").autoincrement().primaryKey(),
  /** Manus OAuth identifier (openId) returned from the OAuth callback. Unique per user. */
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

/** 一期模擬或匯入的六合彩開獎資料；六個正選及特別號均獨立儲存以利查詢。 */
export const lottoDraws = mysqlTable("lotto_draws", {
  id: int("id").autoincrement().primaryKey(),
  drawNo: int("drawNo").notNull().unique(),
  drawDate: timestamp("drawDate").notNull(),
  main1: int("main1").notNull(),
  main2: int("main2").notNull(),
  main3: int("main3").notNull(),
  main4: int("main4").notNull(),
  main5: int("main5").notNull(),
  main6: int("main6").notNull(),
  special: int("special").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
});

/** 以最近 50 期資料與模型評分產生的單一號碼統計快照。 */
export const lottoNumberStats = mysqlTable("lotto_number_stats", {
  id: int("id").autoincrement().primaryKey(),
  number: int("number").notNull().unique(),
  frequency50: int("frequency50").notNull(),
  gap: int("gap").notNull(),
  temperature: varchar("temperature", { length: 16 }).notNull(),
  modelWeight: int("modelWeight").notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

/** 由機率權重抽樣、去重與條件過濾後得到的組合快照。 */
export const lottoRecommendations = mysqlTable("lotto_recommendations", {
  id: int("id").autoincrement().primaryKey(),
  setIndex: int("setIndex").notNull().unique(),
  numbers: text("numbers").notNull(),
  oddEven: varchar("oddEven", { length: 24 }).notNull(),
  numberSum: int("numberSum").notNull(),
  consecutivePairs: int("consecutivePairs").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
});

export type LottoDraw = typeof lottoDraws.$inferSelect;
export type LottoNumberStat = typeof lottoNumberStats.$inferSelect;
export type LottoRecommendation = typeof lottoRecommendations.$inferSelect;
