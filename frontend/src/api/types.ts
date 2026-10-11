// The shapes of the data the server sends and accepts. Must match
// backend/app/schemas.py and backend/app/constants.py exactly.

export type Role = "ops_analyst" | "tenant_admin" | "admin";

/** Every role, least powerful first - the order the audit log's filter
 *  lists them in. Kept here so no other file has to list them again. */
export const ALL_ROLES: Role[] = ["ops_analyst", "tenant_admin", "admin"];

/** Roles allowed on the admin pages - /escalations and /admin.
 *
 *  Both the menu and the pages themselves read this list, so they always
 *  agree. If they didn't, a new role could see a menu link to a page that
 *  then refused to open. */
export const ADMIN_AREA_ROLES: Role[] = ["tenant_admin", "admin"];

/** The display name for each role. Must match the labels in
 *  backend/app/constants.py ROLES. Kept here, rather than asked for from the
 *  server, so showing a role name doesn't need a request. */
export const ROLE_LABELS: Record<Role, string> = {
  ops_analyst: "Ops Analyst",
  tenant_admin: "Tenant Admin",
  admin: "Platform Admin (Support)",
};

/** Roles people can choose when signing up. Must match config.SIGNUP_ROLES.
 *  "admin" is left out on purpose - and the server refuses it anyway,
 *  whatever this list says. */
export const SIGNUP_ROLES: Role[] = ["ops_analyst", "tenant_admin"];

export interface Tenant {
  id: number;
  name: string;
  slug: string;
}

export interface TenantCreate {
  name: string;
}

export const ACTION_TYPES = [
  "call_customer",
  "send_confirmation_sms",
  "send_reminder_email",
  "flag_for_manual_review",
  "convert_cod_to_prepaid",
  "proceed_with_delivery",
  "escalate",
] as const;
export type ActionType = (typeof ACTION_TYPES)[number];

/** The display name for each action. Every page uses this one list, so an
 *  action is always called the same thing. */
export const ACTION_LABELS: Record<ActionType, string> = {
  call_customer: "Call customer",
  send_confirmation_sms: "Send confirmation SMS",
  send_reminder_email: "Send reminder email",
  flag_for_manual_review: "Flag for manual review",
  convert_cod_to_prepaid: "Convert COD to prepaid",
  proceed_with_delivery: "Proceed with delivery",
  escalate: "Escalate to Tenant Admin",
};

/** What an automatic rule may do - every action except escalating. A rule
 *  could escalate thousands of orders at once, more than an admin could
 *  handle, so escalating is done one order at a time.
 *  Must match backend/app/constants.py RULE_ACTION_TYPES. */
export const RULE_ACTION_TYPES: ActionType[] = ACTION_TYPES.filter(
  (a) => a !== "escalate",
);

export const OUTCOMES = ["pending", "resolved_kept", "resolved_prevented", "no_response"] as const;
export type Outcome = (typeof OUTCOMES)[number];

export const ORDER_STATUSES = ["pending", "overridden", "actioned", "closed"] as const;
export type OrderStatusValue = (typeof ORDER_STATUSES)[number];

/** The server sends values like "resolved_kept". These are the readable
 *  versions people should see instead. */
export const ORDER_STATUS_LABELS: Record<OrderStatusValue, string> = {
  pending: "Pending",
  overridden: "Overridden",
  actioned: "Actioned",
  closed: "Closed",
};

export const OUTCOME_LABELS: Record<Outcome, string> = {
  pending: "Pending",
  resolved_kept: "Resolved \u2014 order kept",
  resolved_prevented: "Resolved \u2014 return prevented",
  no_response: "No response",
};

export const SEVERITY_LABELS: Record<"high" | "medium", string> = {
  high: "High",
  medium: "Medium",
};

export interface OrderListItem {
  order_id: string;
  tenant: string;
  order_date: string;
  customer_ref: string;
  product_ref: string;
  current_score: number;
  model_risk_score: number;
  status: OrderStatusValue;
  reasons: string[];
  customer_no_history: boolean;
  product_no_history: boolean;
  country_bucket: string;
  product_brand_bucket: string;
  product_type_bucket: string;
}

export interface OrderDetail extends OrderListItem {
  customer_return_rate: number;
  product_return_rate: number;
  avg_discount_value: number;
  avg_gbp_price: number;
  override_score: number | null;
  override_reason: string | null;
  overridden_by: string | null;
  overridden_at: string | null;
  raw_features: Record<string, unknown>;
}

export interface PaginatedOrders {
  items: OrderListItem[];
  page: number;
  page_size: number;
  total: number;
  /** The dashboard's "today": the newest order this user can see. The dates
   *  are made up and end in November 2021, so the date filter counts back from
   *  this rather than from the real date. */
  reference_date: string | null;
  /** The first day included in the date filter, or null if there's no filter. */
  since_date: string | null;
}

export interface ScoreHistogramBucket {
  lower: number;
  upper: number;
  count: number;
}

export interface ScoreHistogram {
  buckets: ScoreHistogramBucket[];
  total: number;
  reference_date: string | null;
  since_date: string | null;
}

export interface OrderFilters {
  tenant?: string;
  status?: OrderStatusValue;
  min_score?: number;
  max_score?: number;
  country?: string;
  product_type?: string;
  cold_start?: boolean;
  /** How many days back to look, ending at reference_date. */
  last_n_days?: number;
  sort?: OrderSort;
  page?: number;
  page_size?: number;
}

export const ORDER_SORTS = ["-score", "score", "-date", "date"] as const;
export type OrderSort = (typeof ORDER_SORTS)[number];

export const ORDER_SORT_LABELS: Record<OrderSort, string> = {
  "-score": "Risk score (high to low)",
  score: "Risk score (low to high)",
  "-date": "Date (newest)",
  date: "Date (oldest)",
};

/** The choices in the order list's date filter. No days means all time. */
export const PERIOD_OPTIONS: { label: string; days: number | undefined }[] = [
  { label: "All time", days: undefined },
  { label: "Last 7 days", days: 7 },
  { label: "Last 14 days", days: 14 },
  { label: "Last 30 days", days: 30 },
  { label: "Last 60 days", days: 60 },
  { label: "Last 90 days", days: 90 },
];

export interface OverrideRequest {
  new_score: number;
  reason: string;
  // No "who did it" field: the server takes that from the login.
}

export interface ActionRequest {
  action_type: ActionType;
  trigger?: "manual" | "automated_threshold";
  note?: string;
  // No "who did it" field - see OverrideRequest.
}

export interface ActionOutcomeUpdate {
  outcome: Outcome;
  note?: string;
}

export interface HistoryEntry {
  id: number;
  event_type: "override" | "intervention_action";
  action_type: ActionType | null;
  trigger: "manual" | "automated_threshold";
  outcome: Outcome | null;
  old_score: number | null;
  new_score: number | null;
  note: string | null;
  actor_role: Role;
  actor_name: string | null;
  created_at: string;
}

export interface AuditLogEntry extends HistoryEntry {
  order_id: string;
  tenant: string;
}

export interface PaginatedAuditLog {
  items: AuditLogEntry[];
  page: number;
  page_size: number;
  total: number;
}

export interface ReportingBucket {
  bucket: string;
  baseline_return_rate: number;
  actual_return_rate: number;
  n_orders: number;
}

export type CohortType = "overall" | "product" | "country" | "product_type";
export type Granularity = "day" | "week";

export interface ReportingResponse {
  cohort_type: CohortType;
  cohort_key: string;
  granularity: Granularity;
  buckets: ReportingBucket[];
}

/** One escalated order, as shown in the company admin's list. Must match
 *  backend/app/schemas.py EscalationOut. */
export interface EscalationOut {
  /** The escalation's own ID, not the order's: an order can be escalated more
   *  than once, and each one is closed separately. */
  log_id: number;
  order_id: string;
  tenant: string;
  order_date: string;
  current_score: number;
  model_risk_score: number;
  order_status: OrderStatusValue;
  raised_by: string | null;
  raised_by_role: Role;
  raised_at: string;
  trigger: "manual" | "automated_threshold";
  note: string | null;
  outcome: Outcome | null;
}

export interface AlertOut {
  tenant: string;
  cohort_type: CohortType;
  cohort_key: string;
  baseline_rate: number;
  actual_rate: number;
  gap: number;
  n_orders: number;
  severity: "high" | "medium";
}

export interface RuleOut {
  id: number;
  tenant: string;
  tenant_slug: string;
  name: string;
  score_min: number;
  score_max: number;
  action_type: ActionType;
  is_active: boolean;
}

export interface RuleCreate {
  name: string;
  score_min: number;
  score_max: number;
  action_type: ActionType;
}

export interface RuleUpdate {
  is_active?: boolean;
  score_min?: number;
  score_max?: number;
  action_type?: ActionType;
}

export interface RuleEvaluateResult {
  rules_evaluated: number;
  actions_created: number;
  details: { rule: string; actions_created: number }[];
}

export interface MetaOut {
  generated_at: string;
  model: string;
  n_orders: number;
  achieved_overall_auc: number | null;
  achieved_cold_customer_auc: number | null;
  tenants: string[];
  notice: string;
}

// --- dashboard -------------------------------------------------------------
//
// Must match DashboardOut in backend/app/schemas.py.

export interface DashboardRiskMix {
  low: number;
  medium: number;
  high: number;
}

export interface DashboardOrders {
  total: number;
  risk_mix: DashboardRiskMix;
  cold_start: number;
  last_n_days: number | null;
  /** The dates this section covers - and only this section. null for a
   *  company with no orders yet, which is normal. */
  reference_date: string | null;
  since_date: string | null;
}

export interface DashboardOpenAction {
  action_type: ActionType;
  open_actions: number;
}

export interface DashboardActions {
  /** The first three count ORDERS; open_actions counts ACTIONS. One order can
   *  have several actions, so the two are never added together. */
  orders_cleared_for_delivery: number;
  orders_flagged_for_manual_review: number;
  orders_escalated_and_open: number;
  open_actions: number;
  /** Zero means nothing has ever been done, so the page says that in words
   *  rather than showing four zeros. The four boxes alone can't tell you this:
   *  a company that has only made phone calls would show zeros in all four. */
  total_actions_logged: number;
  open_by_action_type: DashboardOpenAction[];
}

export interface DashboardOut {
  orders: DashboardOrders;
  actions: DashboardActions;
}
