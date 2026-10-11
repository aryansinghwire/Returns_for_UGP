import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApp } from "../context/AppContext";
import { useAuth } from "../context/AuthContext";
import { api, type RequestContext } from "./client";
import type {
  ActionOutcomeUpdate,
  ActionRequest,
  AlertOut,
  EscalationOut,
  AuditLogEntry,
  CohortType,
  DashboardOut,
  Granularity,
  HistoryEntry,
  MetaOut,
  OrderDetail,
  OrderFilters,
  OverrideRequest,
  PaginatedAuditLog,
  PaginatedOrders,
  ReportingResponse,
  ScoreHistogram,
  RuleCreate,
  RuleEvaluateResult,
  RuleOut,
  RuleUpdate,
  Tenant,
  TenantCreate,
} from "./types";

function useCtx(): RequestContext {
  const { tenant } = useApp();
  return { tenant };
}

/**
 * Whether it's OK to ask the server for data yet.
 *
 * Its main job is to stop every request the moment a login expires. Without
 * it, each one would retry with the expired login, fail, and trigger the
 * "you've been logged out" handling again and again.
 */
function useScopeReady(): boolean {
  return useAuth().status === "authenticated";
}

// --- meta / tenants / roles ---

export function useMeta() {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["meta"],
    queryFn: () => api.get<MetaOut>("/meta", ctx),
  });
}

export function useTenants() {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["tenants"],
    queryFn: () => api.get<Tenant[]>("/tenants", ctx, undefined, true),
  });
}

export function useCreateTenant() {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TenantCreate) => api.post<Tenant>("/tenants", ctx, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenants"] }),
  });
}

// --- orders / queue ---

export function useOrders(filters: OrderFilters) {
  const ctx = useCtx();
  const ready = useScopeReady();
  return useQuery({
    queryKey: ["orders", ctx.tenant, filters],
    queryFn: () => api.get<PaginatedOrders>("/orders", ctx, filters as Record<string, unknown>),
    enabled: ready,
    placeholderData: (prev) => prev,
  });
}

/**
 * How risk is spread across the order list, for the chart above it.
 *
 * Uses every filter except the score range, on purpose. The score range is
 * what the user picks on this chart, so including it would shrink the chart
 * to just the selection. It also means dragging the range doesn't reload the
 * chart.
 */
export function useScoreHistogram(filters: OrderFilters) {
  const ctx = useCtx();
  const ready = useScopeReady();
  const params = {
    status: filters.status,
    country: filters.country,
    product_type: filters.product_type,
    cold_start: filters.cold_start,
    last_n_days: filters.last_n_days,
  };
  return useQuery({
    queryKey: ["score-histogram", ctx.tenant, params],
    queryFn: () =>
      api.get<ScoreHistogram>("/orders/score-histogram", ctx, params as Record<string, unknown>),
    enabled: ready,
    placeholderData: (prev) => prev,
  });
}

// --- dashboard ---

/**
 * The numbers on the dashboard's front page.
 *
 * Both sections come in one request, so they always describe the same
 * moment. The date filter only applies to the orders section - the actions
 * section covers all time, because the order dates are made up and end in
 * 2021 while actions have real dates.
 */
export function useDashboard(params: { last_n_days?: number }) {
  const ctx = useCtx();
  const ready = useScopeReady();
  return useQuery({
    queryKey: ["dashboard", ctx.tenant, params],
    queryFn: () => api.get<DashboardOut>("/dashboard", ctx, params),
    enabled: ready,
    // Changing the date filter can't change the actions section, so it mustn't
    // flicker back to "loading" (or to "nothing here") when only the orders
    // section is updating.
    placeholderData: (prev) => prev,
  });
}

export function useOrder(orderId: string | undefined) {
  const ctx = useCtx();
  const ready = useScopeReady();
  return useQuery({
    queryKey: ["order", ctx.tenant, orderId],
    queryFn: () => api.get<OrderDetail>(`/orders/${orderId}`, ctx),
    enabled: ready && !!orderId,
  });
}

export function useOrderHistory(orderId: string | undefined) {
  const ctx = useCtx();
  const ready = useScopeReady();
  return useQuery({
    queryKey: ["order-history", ctx.tenant, orderId],
    queryFn: () => api.get<HistoryEntry[]>(`/orders/${orderId}/history`, ctx),
    enabled: ready && !!orderId,
  });
}

export function useOverrideOrder(orderId: string) {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OverrideRequest) => api.post<OrderDetail>(`/orders/${orderId}/override`, ctx, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["order-history", ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useCreateAction(orderId: string) {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ActionRequest) => api.post<HistoryEntry>(`/orders/${orderId}/actions`, ctx, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["order-history", ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUpdateActionOutcome(orderId: string) {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ logId, body }: { logId: number; body: ActionOutcomeUpdate }) =>
      api.patch<HistoryEntry>(`/orders/${orderId}/actions/${logId}`, ctx, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["order-history", ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

// --- reporting ---
// Only used by ReportingPage, which is switched off (see the note at the top
// of that file). The server side still works and is tested, so this stays.

export function useReporting(params: {
  granularity?: Granularity;
  cohort_type?: CohortType;
  cohort_key?: string;
}) {
  const ctx = useCtx();
  const ready = useScopeReady();
  return useQuery({
    queryKey: ["reporting", ctx.tenant, params],
    queryFn: () => api.get<ReportingResponse>("/reporting/baseline-vs-actual", ctx, params),
    enabled: ready,
  });
}

// --- alerts ---

export function useAlerts(params: { min_gap?: number; min_n?: number } = {}) {
  const ctx = useCtx();
  const ready = useScopeReady();
  return useQuery({
    queryKey: ["alerts", ctx.tenant, params],
    queryFn: () => api.get<AlertOut[]>("/alerts", ctx, params),
    enabled: ready,
    refetchInterval: 60_000,
  });
}

// --- escalations ---

/** The company admin's list of escalated orders. Only admins can see it, on
 *  the server and on the website - an analyst asking for it is refused, rather
 *  than shown an empty list. */
export function useEscalations(params: { include_resolved?: boolean } = {}) {
  const ctx = useCtx();
  const ready = useScopeReady();
  return useQuery({
    queryKey: ["escalations", ctx.tenant, params],
    queryFn: () => api.get<EscalationOut[]>("/escalations", ctx, params),
    enabled: ready,
  });
}

// --- rules ---

export function useRules() {
  const ctx = useCtx();
  const ready = useScopeReady();
  return useQuery({
    // Who's logged in isn't part of this key, because every saved result is
    // cleared on each login and logout - which keeps accounts' data apart
    // completely. The company is part of it, because a platform admin switches
    // companies without logging out.
    queryKey: ["rules", ctx.tenant],
    queryFn: () => api.get<RuleOut[]>("/rules", ctx),
    enabled: ready,
  });
}

export function useCreateRule() {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RuleCreate) => api.post<RuleOut>("/rules", ctx, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
}

export function useUpdateRule() {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, body }: { ruleId: number; body: RuleUpdate }) =>
      api.patch<RuleOut>(`/rules/${ruleId}`, ctx, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
}

/**
 * How many waiting orders each active rule would act on - so the confirmation
 * box can show real numbers, not just a vague warning.
 *
 * One number per rule, not one total. Rules' score ranges can overlap, and an
 * order in two ranges gets one action from each rule, so a single total would
 * be misleading. Uses the order list's existing filters - nothing new on the
 * server.
 */
export function useSweepPreview(rules: RuleOut[], enabled: boolean) {
  const ctx = useCtx();
  const ready = useScopeReady();
  return useQueries({
    queries: rules.map((rule) => ({
      queryKey: ["sweep-preview", ctx.tenant, rule.id, rule.score_min, rule.score_max],
      queryFn: () =>
        api.get<PaginatedOrders>("/orders", ctx, {
          status: "pending",
          min_score: rule.score_min,
          max_score: rule.score_max,
          page_size: 1,
        }),
      enabled: enabled && ready,
      staleTime: 0,
    })),
  });
}

export function useEvaluateRules() {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<RuleEvaluateResult>("/rules/evaluate", ctx),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["audit-log"] });
    },
  });
}

// --- audit log ---

export function useAuditLog(params: {
  actor_role?: string;
  event_type?: string;
  since?: string;
  until?: string;
  page?: number;
  page_size?: number;
}) {
  const ctx = useCtx();
  const ready = useScopeReady();
  return useQuery({
    queryKey: ["audit-log", ctx.tenant, params],
    queryFn: () => api.get<PaginatedAuditLog>("/audit-log", ctx, params),
    enabled: ready,
    placeholderData: (prev) => prev,
  });
}

export type { AuditLogEntry };
