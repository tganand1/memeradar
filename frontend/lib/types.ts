export type Mode = "demo" | "live";
export type Verdict = "BUY" | "WATCH" | "AVOID";

export interface Wallet {
  starting_balance: number;
  cash: number;
  equity: number;
  open_value: number;
  realized_pnl: number;
  unrealized_pnl: number;
  today_pnl: number;
  today_pnl_pct: number;
  all_time_pnl: number;
  all_time_pnl_pct: number;
  total_fees: number;
  open_count: number;
}

export interface Breaker {
  active: boolean;
  reason: string | null;
  drawdown_today_pct: number;
  limit_pct: number;
  day_start_equity: number;
  resets_at: string;
}

export interface HealthSource {
  status: string;
  detail: string;
  updated_at: string;
}

export interface Health {
  status: string;
  mode: Mode;
  tokens_per_minute: number;
  last_token_at: string | null;
  uptime_seconds: number;
  reconnects: number;
  sources: Record<string, HealthSource>;
  ws_clients?: number;
}

export interface Metrics {
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  avg_pnl: number;
  avg_pnl_pct: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number;
  expectancy: number;
  max_drawdown: number;
  sharpe: number;
  best_trade: { symbol: string; pnl_usd: number; pnl_pct: number; id: number } | null;
  worst_trade: { symbol: string; pnl_usd: number; pnl_pct: number; id: number } | null;
  avg_hold_seconds: number;
  rug_count: number;
  avg_slippage_cost: number;
  total_fees: number;
  total_pnl: number;
  roi_pct: number;
  missed_opportunities?: number;
  bullets_dodged?: number;
}

export interface OpportunityMetric {
  id: string;
  name: string;
  score: number;
  value: string;
  detail: string;
  data: Record<string, unknown>;
}

export interface Check {
  id: string;
  name: string;
  score: number;
  passed: boolean;
  critical: boolean;
  value: string;
  detail: string;
  data: Record<string, any>;
}

export interface PricePoint {
  t: number;
  p: number;
}

export interface TokenSummary {
  id: number;
  mint: string;
  name: string;
  symbol: string;
  creator: string;
  source: string;
  created_at: string;
  detected_at: string;
  image_url: string | null;
  website: string | null;
  twitter: string | null;
  telegram: string | null;
  initial_price_usd: number;
  initial_market_cap_usd: number;
  initial_liquidity_usd: number;
  price_usd: number;
  market_cap_usd: number;
  liquidity_usd: number;
  peak_price_usd: number;
  peak_gain_pct: number;
  safety_score: number;
  opportunity_score: number;
  final_score: number;
  verdict: Verdict;
  hard_rejected: boolean;
  red_flags: string[];
  green_flags: string[];
  rejected_reasons: string[];
  opportunity_metrics: Record<string, OpportunityMetric>;
  decision: "BUY" | "SKIP" | null;
  decision_reason: string | null;
  trade_id: number | null;
  rugged: boolean;
  is_demo: boolean;
  last_updated_at: string;
}

export interface ScoreBreakdown {
  safety: number;
  opportunity: number;
  final: number;
  safety_weight: number;
  opportunity_weight: number;
  safety_contributions: Record<string, number>;
  opportunity_contributions: Record<string, number>;
  thresholds: { buy: number; watch: number };
}

export interface TokenDetail extends TokenSummary {
  checks: Record<string, Check>;
  score_breakdown: ScoreBreakdown;
  price_history: PricePoint[];
  trades: Trade[];
  links: Record<string, string>;
}

export interface TpLevel {
  index: number;
  gain_pct: number;
  sell_fraction: number;
  price: number;
  hit: boolean;
}

export interface Position {
  id: number;
  mint: string;
  name: string;
  symbol: string;
  image_url: string | null;
  entry_price: number;
  current_price: number;
  size_usd: number;
  value_usd: number;
  tokens_remaining: number;
  remaining_ratio: number;
  pnl_usd: number;
  pnl_pct: number;
  gain_pct: number;
  market_cap_at_entry: number;
  current_market_cap: number;
  peak_price: number;
  peak_gain_pct: number;
  stop_price: number;
  sl_progress: number;
  next_tp_price: number | null;
  next_tp_gain_pct: number | null;
  tp_progress: number;
  tp_levels: TpLevel[];
  trailing_active: boolean;
  trailing_stop_price: number;
  liquidity_usd: number | null;
  score: number;
  safety: number;
  opportunity: number;
  opened_at: string;
  hold_seconds: number;
  is_demo: boolean;
}

export interface TradeFill {
  ts: string;
  kind: string;
  reason: string;
  tokens: number;
  price: number;
  slippage_pct: number;
  fee_usd: number;
  proceeds_usd: number;
  zeroed: boolean;
}

export interface Trade {
  id: number;
  mint: string;
  name: string;
  symbol: string;
  image_url: string | null;
  status: "open" | "closed";
  opened_at: string;
  closed_at: string | null;
  entry_price: number;
  exit_price: number;
  size_usd: number;
  token_amount: number;
  tokens_remaining: number;
  entry_market_cap_usd: number;
  proceeds_usd: number;
  realized_partial: number;
  liquidity_at_entry: number;
  peak_price: number;
  peak_gain_pct: number;
  score_at_entry: number;
  safety_at_entry: number;
  opportunity_at_entry: number;
  buy_reasons: string[];
  exit_reasons: string[];
  sizing: Record<string, any>;
  fills: TradeFill[];
  tp_taken: number[];
  trailing_active: boolean;
  stop_price: number;
  trailing_stop_price: number;
  slippage_buy_pct: number;
  slippage_sell_pct: number;
  fees_usd: number;
  pnl_usd: number;
  pnl_pct: number;
  hold_seconds: number;
  equity_after: number;
  is_demo: boolean;
}

export interface LogEntry {
  id: number;
  ts: string;
  level: "info" | "warning" | "error" | "trade" | string;
  category: string;
  message: string;
  meta: Record<string, any>;
}

export interface EquityPoint {
  t: string;
  equity: number;
  cash: number;
}

export interface LiveEvent {
  kind: string;
  action?: string;
  data?: any;
  symbol?: string;
  mint?: string;
  reason?: string;
  enabled?: boolean;
}

export interface Snapshot {
  ts: string;
  mode: Mode;
  bot_enabled: boolean;
  breaker: Breaker;
  health: Health;
  wallet: Wallet;
  metrics: Metrics;
  positions: Position[];
  tokens: TokenSummary[];
  trades: Trade[];
  logs: LogEntry[];
  equity: EquityPoint[];
  sol_price: number;
}

export interface TokenListResponse {
  items: TokenSummary[];
  count: number;
  limit: number;
  offset: number;
}

export interface TradeListResponse {
  items: Trade[];
  total: number;
  limit: number;
  offset: number;
}

export interface ScoreBucket {
  bucket: string;
  trades: number;
  wins: number;
  win_rate: number;
  pnl: number;
  avg_pnl_pct: number;
}

export interface HourRow {
  hour: number;
  trades: number;
  wins: number;
  pnl: number;
}

export interface WeekdayRow {
  weekday: number;
  trades: number;
  wins: number;
  pnl: number;
}

export interface HeatCell {
  weekday: number;
  hour: number;
  trades: number;
  pnl: number;
}

export interface FilterStat {
  id: string;
  name: string;
  passed_trades: number;
  passed_win_rate: number | null;
  passed_pnl: number;
  failed_trades: number;
  failed_win_rate: number | null;
  failed_pnl: number;
}

export interface ThresholdRow {
  threshold: number;
  trades: number;
  win_rate: number;
  pnl: number;
  avg_pnl_pct: number;
}

export interface MissedToken {
  mint: string;
  name: string;
  symbol: string;
  verdict: Verdict;
  final_score: number;
  safety_score: number;
  opportunity_score: number;
  peak_gain_pct: number;
  initial_market_cap_usd: number;
  image_url: string | null;
  created_at: string;
  reasons: string[];
}

export interface DodgedToken {
  mint: string;
  name: string;
  symbol: string;
  verdict: Verdict;
  final_score: number;
  peak_gain_pct: number;
  rugged: boolean;
  image_url: string | null;
  created_at: string;
  reasons: string[];
}

export interface Analytics {
  score_buckets: ScoreBucket[];
  by_hour: HourRow[];
  by_weekday: WeekdayRow[];
  heatmap: HeatCell[];
  filters: FilterStat[];
  what_if: ThresholdRow[];
  missed_opportunities: MissedToken[];
  bullets_dodged: DodgedToken[];
  counts: { missed: number; dodged: number; rejected: number; scanned: number };
  metrics: Metrics;
}

export interface AppSection {
  mode: Mode;
  log_level: string;
  demo_seed: boolean;
  sol_price_usd: number;
}

export interface PaperSection {
  starting_balance: number;
  min_trade_usd: number;
  max_position_pct: number;
  max_open_exposure_pct: number;
  cash_reserve_pct: number;
  max_pool_share_pct: number;
  taker_fee_pct: number;
  priority_fee_sol: number;
  jito_tip_sol: number;
  random_slippage_min_pct: number;
  random_slippage_max_pct: number;
  execution_delay_min_ms: number;
  execution_delay_max_ms: number;
  failed_tx_rate: number;
  sell_failed_tx_rate: number;
  mark_haircut_pct: number;
  equity_snapshot_seconds: number;
}

export interface HardRejectCfg {
  top10_max_pct: number;
  top1_max_pct: number;
  min_liquidity_usd: number;
  creator_max_rugs: number;
  min_holders: number;
}

export interface SizingCfg {
  base_pct_of_equity: number;
  score_scale: number;
  confidence_floor: number;
  confidence_ceiling: number;
  kelly_fraction: number;
  kelly_payoff: number;
  losing_streak_cut: number;
  winning_streak_boost: number;
  max_streak_mult: number;
  min_streak_mult: number;
}

export interface TakeProfitCfg {
  gain_pct: number;
  sell_fraction: number;
}

export interface ExitsCfg {
  stop_loss_pct: number;
  take_profits: TakeProfitCfg[];
  trailing_stop_pct: number;
  time_stop_minutes: number;
  time_stop_min_gain_pct: number;
  emergency_liquidity_drop_pct: number;
}

export interface CircuitBreakerCfg {
  daily_loss_limit_pct: number;
}

export interface StrategyCfg {
  min_score_buy: number;
  min_score_watch: number;
  safety_weight: number;
  opportunity_weight: number;
  hard_reject: HardRejectCfg;
  sizing: SizingCfg;
  exits: ExitsCfg;
  circuit_breaker: CircuitBreakerCfg;
  weights: Record<string, number>;
  opportunity_weights: Record<string, number>;
}

export interface ListenerCfg {
  demo_token_interval_seconds: number;
  demo_token_jitter_seconds: number;
  dexscreener_poll_seconds: number;
  price_poll_seconds: number;
  position_price_poll_seconds: number;
  max_tokens_per_minute: number;
}

export interface NotifierCfg {
  enabled: boolean;
  notify_buys: boolean;
  notify_sells: boolean;
  notify_big_wins: boolean;
  big_win_usd: number;
  notify_errors: boolean;
}

export interface ApiCfg {
  cors_origins: string[];
}

export interface AppConfig {
  app: AppSection;
  paper: PaperSection;
  strategy: StrategyCfg;
  listener: ListenerCfg;
  notifier: NotifierCfg;
  api: ApiCfg;
}

export interface ConfigResponse {
  config: AppConfig;
  runtime?: { mode: Mode; bot_enabled: boolean };
}

export interface BacktestTrade {
  mint: string;
  symbol: string;
  score: number;
  safety: number;
  opportunity: number;
  size_usd: number;
  entry_price: number;
  pnl_usd: number;
  pnl_pct: number;
  exit_reasons: string[];
  opened_at: string;
  closed_at: string | null;
}

export interface BacktestResult {
  trades: BacktestTrade[];
  equity_curve: { t: string; equity: number }[];
  scanned: number;
  bought: number;
  avoided: number;
  missed_opportunities: number;
  bullets_dodged: number;
  rugged_tokens: number;
  metrics: {
    starting_balance: number;
    final_equity: number;
    pnl: number;
    roi_pct: number;
    win_rate: number;
    profit_factor: number;
    max_drawdown: number;
    avg_trade_pct: number;
  };
  config: Record<string, number>;
}
