import { COOKIE_NAME } from "@shared/const";
import { z } from "zod";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, router } from "./_core/trpc";
import { getLottoHistory, getLottoOverview, getLottoRecommendations } from "./lotto";

export const appRouter = router({
    // if you need to use socket.io, read and register route in server/_core/index.ts, all api should start with '/api/' so that the gateway can route correctly
  system: systemRouter,
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return {
        success: true,
      } as const;
    }),
  }),
  lotto: router({
    overview: publicProcedure.query(() => getLottoOverview()),
    recommendations: publicProcedure.query(() => getLottoRecommendations()),
    history: publicProcedure
      .input(
        z.object({
          page: z.number().int().min(1).max(100),
          pageSize: z.number().int().min(10).max(100),
          direction: z.enum(["asc", "desc"]),
        }),
      )
      .query(({ input }) => getLottoHistory(input.page, input.pageSize, input.direction)),
  }),
});

export type AppRouter = typeof appRouter;
