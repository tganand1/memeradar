"use client";

import {
  AlertTriangle,
  Check,
  Database,
  Gauge,
  Loader2,
  RotateCcw,
  Save,
  Shield,
  SlidersHorizontal,
  Sparkles,
  Wallet,
  Waves,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Shell } from "@/components/shell/shell";
import { useToast } from "@/components/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { api, API_BASE } from "@/lib/api";
import { fmtUsd } from "@/lib/format";
import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { AppConfig } from "@/lib/types";

const PRESETS = [
  { id: "conservative", name: "Conservative", desc: "Higher bar, tight stop, small size, 8% breaker.", icon: Shield },
  { id: "balanced", name: "Balanced", desc: "MemeRadar defaults — 74+ score, 25% stop.", icon: Gauge },
  { id: "degen", name: "Degen", desc: "Lower bar, bigger size, wider stops, 25% breaker.", icon: Sparkles },
];

const TABS = [
  { id: "strategy", label: "Strategy", icon: SlidersHorizontal },
  { id: "risk", label: "Risk & exits", icon: Shield },
  { id: "sizing", label: "Sizing", icon: Wallet },
  { id: "execution", label: "Execution", icon: Waves },
  { id: "feeds", label: "Feeds & alerts", icon: Database },
  { id: "general", label: "General", icon: AlertTriangle },
] as const;

type TabId = (typeof TABS)[number]["id"];

function FieldRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-white/[0.04] py-2.5 last:border-0">
      <div className="min-w-0">
        <p className="text-[12px] text-fg">{label}</p>
        {hint ? <p className="mt-0.5 text-[10px] leading-relaxed text-muted">{hint}</p> : null}
      </div>
      <div className="w-[132px] shrink-0">{children}</div>
    </div>
  );
}

function NumberBox({
  value,
  onChange,
  step = 1,
  min,
  max,
  suffix,
}: {
  value: number;
  onChange: (value: number) => void;
  step?: number;
  min?: number;
  max?: number;
  suffix?: string;
}) {
  return (
    <div className="flex items-center gap-1 rounded-lg border border-white/[0.08] bg-black/30 px-2 focus-within:border-accent/30">
      <input
        type="number"
        value={Number.isFinite(value) ? value : 0}
        step={step}
        min={min}
        max={max}
        onChange={(event) => {
          const next = Number(event.target.value);
          if (Number.isFinite(next)) onChange(next);
        }}
        className="w-full bg-transparent py-1.5 text-right font-mono text-xs text-fg outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
      />
      {suffix ? <span className="font-mono text-[9px] text-muted">{suffix}</span> : null}
    </div>
  );
}

function PctBox({
  value,
  onChange,
  step = 0.5,
}: {
  value: number;
  onChange: (value: number) => void;
  step?: number;
}) {
  return (
    <NumberBox
      value={Number((value * 100).toFixed(3))}
      step={step}
      suffix="%"
      onChange={(next) => onChange(next / 100)}
    />
  );
}

function ToggleRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-white/[0.04] py-2.5 last:border-0">
      <div className="min-w-0">
        <p className="text-[12px] text-fg">{label}</p>
        {hint ? <p className="mt-0.5 text-[10px] leading-relaxed text-muted">{hint}</p> : null}
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div>
          <CardTitle>{title}</CardTitle>
          {description ? <p className="mt-0.5 text-xs text-muted">{description}</p> : null}
        </div>
      </CardHeader>
      <div className="px-5 pb-4">{children}</div>
    </Card>
  );
}

function CorsField({ value, onChange }: { value: string[]; onChange: (next: string[]) => void }) {
  const [text, setText] = useState(value.join(", "));
  useEffect(() => {
    setText(value.join(", "));
  }, [value]);
  return (
    <input
      value={text}
      onChange={(event) => {
        setText(event.target.value);
        onChange(
          event.target.value
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
        );
      }}
      className="w-full rounded-lg border border-white/[0.08] bg-black/30 px-2.5 py-2 font-mono text-[11px] text-fg outline-none focus:border-accent/30"
    />
  );
}

export default function SettingsPage() {
  const toast = useToast();
  const snapshot = useLiveStore((state) => state.snapshot);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [saved, setSaved] = useState<AppConfig | null>(null);
  const [tab, setTab] = useState<TabId>("strategy");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [presetPending, setPresetPending] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [accountConfirm, setAccountConfirm] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.config();
      setConfig(response.config);
      setSaved(response.config);
    } catch (error) {
      toast({
        title: "Could not load settings",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const setValue = (path: Array<string | number>, value: unknown) => {
    setConfig((prev) => {
      if (!prev) return prev;
      const next = JSON.parse(JSON.stringify(prev)) as any;
      let node = next;
      for (let index = 0; index < path.length - 1; index += 1) {
        node = node[path[index]];
      }
      node[path[path.length - 1]] = value;
      return next as AppConfig;
    });
  };

  const dirty = Boolean(config && saved && JSON.stringify(config) !== JSON.stringify(saved));

  const save = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const response = await api.saveConfig(config);
      setConfig(response.config);
      setSaved(response.config);
      toast({ title: "Configuration saved", description: "The bot is using the new strategy immediately.", variant: "success" });
    } catch (error) {
      toast({
        title: "Could not save settings",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  const resetConfig = async () => {
    setBusy("reset");
    try {
      const response = await api.resetConfig();
      setConfig(response.config);
      setSaved(response.config);
      setConfirmReset(false);
      toast({ title: "Configuration reset", description: "Restored config.yaml defaults.", variant: "info" });
    } catch (error) {
      toast({
        title: "Reset failed",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setBusy(null);
    }
  };

  const applyPreset = async (name: string) => {
    setPresetPending(name);
    try {
      const response = await api.applyPreset(name);
      setConfig(response.config);
      setSaved(response.config);
      toast({ title: `${name[0].toUpperCase()}${name.slice(1)} preset applied`, variant: "success" });
    } catch (error) {
      toast({
        title: "Preset failed",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setPresetPending(null);
    }
  };

  const resetAccount = async () => {
    setBusy("account");
    try {
      await api.resetAccount();
      setAccountConfirm(false);
    } catch (error) {
      toast({
        title: "Account reset failed",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setBusy(null);
    }
  };

  const seed = async () => {
    setBusy("seed");
    try {
      await api.seedDemo(true);
      toast({ title: "Demo dataset rebuilt", description: "Fresh tokens, trades and equity history loaded.", variant: "success" });
    } catch (error) {
      toast({
        title: "Seed failed",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setBusy(null);
    }
  };

  const spawn = async () => {
    setBusy("spawn");
    try {
      await api.spawnDemo(10);
      toast({ title: "Spawned 10 demo launches", variant: "info" });
    } catch (error) {
      toast({
        title: "Spawn failed",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setBusy(null);
    }
  };

  const runtimeMode = snapshot?.mode || "demo";
  const isDemo = runtimeMode === "demo";

  return (
    <Shell>
      <div className="space-y-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-muted">Control room</p>
            <h1 className="mt-1.5 text-2xl font-bold tracking-tight text-fg sm:text-[28px]">Settings</h1>
            <p className="mt-1 text-sm text-muted">
              Tune scoring, risk and execution. Changes apply to the running paper bot.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone={dirty ? "watch" : "buy"}>{dirty ? "unsaved" : "synced"}</Badge>
            <Button variant="outline" size="sm" onClick={() => setConfirmReset(true)}>
              <RotateCcw className="h-3.5 w-3.5" /> Reset
            </Button>
            <Button variant="primary" size="sm" onClick={save} disabled={!config || saving || !dirty}>
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Save changes
            </Button>
          </div>
        </div>

        {confirmReset ? (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-danger/25 bg-danger/[0.06] px-4 py-3">
            <AlertTriangle className="h-4 w-4 text-danger" />
            <p className="flex-1 text-xs text-muted">
              Reset every strategy value to <span className="font-mono text-fg">config.yaml</span> defaults? Stored trades and
              tokens are untouched.
            </p>
            <Button variant="outline" size="sm" onClick={() => setConfirmReset(false)}>
              Cancel
            </Button>
            <Button variant="danger" size="sm" onClick={resetConfig} disabled={busy === "reset"}>
              {busy === "reset" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null} Confirm reset
            </Button>
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {PRESETS.map((preset) => {
            const Icon = preset.icon;
            const pending = presetPending === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyPreset(preset.id)}
                disabled={Boolean(presetPending)}
                className="group relative overflow-hidden rounded-xl border border-white/[0.07] bg-panel/60 p-4 text-left transition-colors hover:border-accent/25 hover:bg-accent/[0.03] disabled:opacity-50"
              >
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-accent" />
                  <span className="text-sm font-semibold text-fg">{preset.name}</span>
                  {pending ? <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-accent" /> : <Check className="ml-auto h-3.5 w-3.5 text-muted/30 transition-colors group-hover:text-accent" />}
                </div>
                <p className="mt-1.5 text-[11px] leading-relaxed text-muted">{preset.desc}</p>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-1 overflow-x-auto rounded-xl border border-white/[0.06] bg-white/[0.02] p-1">
          {TABS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={cn(
                  "inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-medium transition-colors",
                  tab === item.id ? "bg-accent/10 text-accent" : "text-muted hover:text-fg",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {item.label}
              </button>
            );
          })}
        </div>

        {loading || !config ? (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-72 animate-shimmer rounded-2xl bg-white/[0.03]" />
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {tab === "strategy" ? (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <SectionCard title="Scoring thresholds" description="Verdicts are assigned from the weighted safety and momentum score.">
                  <FieldRow label="Minimum BUY score" hint="Entries require at least this final score.">
                    <NumberBox value={config.strategy.min_score_buy} min={0} max={100} onChange={(value) => setValue(["strategy", "min_score_buy"], value)} />
                  </FieldRow>
                  <FieldRow label="Minimum WATCH score" hint="Below this a token is an AVOID.">
                    <NumberBox value={config.strategy.min_score_watch} min={0} max={100} onChange={(value) => setValue(["strategy", "min_score_watch"], value)} />
                  </FieldRow>
                  <FieldRow label="Safety weight" hint="Share of the final score from security checks.">
                    <PctBox value={config.strategy.safety_weight} onChange={(value) => setValue(["strategy", "safety_weight"], value)} />
                  </FieldRow>
                  <FieldRow label="Momentum weight" hint="Share from liquidity, volume and buyer signals.">
                    <PctBox value={config.strategy.opportunity_weight} onChange={(value) => setValue(["strategy", "opportunity_weight"], value)} />
                  </FieldRow>
                  <p className="mt-2 text-[10px] text-muted">
                    Safety + momentum weights should total 100%.
                  </p>
                </SectionCard>

                <SectionCard title="Hard rejection gate" description="Any trigger blocks a trade regardless of score.">
                  <FieldRow label="Top 10 holders max" hint="Concentration limit for the top ten wallets.">
                    <PctBox value={config.strategy.hard_reject.top10_max_pct} onChange={(value) => setValue(["strategy", "hard_reject", "top10_max_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Top holder max" hint="Single wallet concentration limit.">
                    <PctBox value={config.strategy.hard_reject.top1_max_pct} onChange={(value) => setValue(["strategy", "hard_reject", "top1_max_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Min liquidity" hint="Pool depth required before entry.">
                    <NumberBox value={config.strategy.hard_reject.min_liquidity_usd} min={0} step={100} suffix="$" onChange={(value) => setValue(["strategy", "hard_reject", "min_liquidity_usd"], value)} />
                  </FieldRow>
                  <FieldRow label="Creator max rugs" hint="Reject creators with more previous rug pulls.">
                    <NumberBox value={config.strategy.hard_reject.creator_max_rugs} min={0} onChange={(value) => setValue(["strategy", "hard_reject", "creator_max_rugs"], value)} />
                  </FieldRow>
                  <FieldRow label="Min holders" hint="Minimum unique holders at scan time.">
                    <NumberBox value={config.strategy.hard_reject.min_holders} min={0} onChange={(value) => setValue(["strategy", "hard_reject", "min_holders"], value)} />
                  </FieldRow>
                </SectionCard>

                <div className="lg:col-span-2">
                  <SectionCard title="Scoring weights" description="Relative contribution of each safety and momentum check.">
                    <div className="grid grid-cols-1 gap-x-8 sm:grid-cols-2 lg:grid-cols-3">
                      {Object.entries(config.strategy.weights).map(([key, value]) => (
                        <FieldRow key={key} label={key.replace(/_/g, " ")}>
                          <NumberBox value={value} min={0} step={0.5} onChange={(next) => setValue(["strategy", "weights", key], next)} />
                        </FieldRow>
                      ))}
                      {Object.entries(config.strategy.opportunity_weights).map(([key, value]) => (
                        <FieldRow key={`opp-${key}`} label={`${key.replace(/_/g, " ")} (momentum)`}>
                          <NumberBox value={value} min={0} step={0.5} onChange={(next) => setValue(["strategy", "opportunity_weights", key], next)} />
                        </FieldRow>
                      ))}
                    </div>
                  </SectionCard>
                </div>
              </div>
            ) : null}

            {tab === "risk" ? (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <SectionCard title="Exit plan" description="Every position is monitored against these rules.">
                  <FieldRow label="Stop loss" hint="Hard exit from entry price.">
                    <PctBox value={config.strategy.exits.stop_loss_pct} step={1} onChange={(value) => setValue(["strategy", "exits", "stop_loss_pct"], -Math.abs(value))} />
                  </FieldRow>
                  <FieldRow label="Trailing stop" hint="Activated after the first take-profit.">
                    <PctBox value={config.strategy.exits.trailing_stop_pct} onChange={(value) => setValue(["strategy", "exits", "trailing_stop_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Time stop" hint="Exit flat positions after this hold time.">
                    <NumberBox value={config.strategy.exits.time_stop_minutes} min={1} suffix="min" onChange={(value) => setValue(["strategy", "exits", "time_stop_minutes"], value)} />
                  </FieldRow>
                  <FieldRow label="Time stop min gain" hint="Keep positions above this gain past the timer.">
                    <PctBox value={config.strategy.exits.time_stop_min_gain_pct} onChange={(value) => setValue(["strategy", "exits", "time_stop_min_gain_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Emergency liquidity drop" hint="Exit when pool depth collapses by this amount.">
                    <PctBox value={config.strategy.exits.emergency_liquidity_drop_pct} onChange={(value) => setValue(["strategy", "exits", "emergency_liquidity_drop_pct"], value)} />
                  </FieldRow>
                </SectionCard>

                <SectionCard title="Take profit ladder" description="Sell fractions at gain targets. Later targets inherit trailing stop.">
                  <div className="space-y-2">
                    {config.strategy.exits.take_profits.map((level, index) => (
                      <div key={index} className="flex items-end gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] p-2.5">
                        <div className="flex-1">
                          <p className="font-mono text-[9px] uppercase tracking-wider text-muted">Gain target</p>
                          <PctBox
                            value={level.gain_pct}
                            step={5}
                            onChange={(value) => setValue(["strategy", "exits", "take_profits", index, "gain_pct"], value)}
                          />
                        </div>
                        <div className="flex-1">
                          <p className="font-mono text-[9px] uppercase tracking-wider text-muted">Sell size</p>
                          <PctBox
                            value={level.sell_fraction}
                            step={5}
                            onChange={(value) => setValue(["strategy", "exits", "take_profits", index, "sell_fraction"], value)}
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            setValue(
                              ["strategy", "exits", "take_profits"],
                              config.strategy.exits.take_profits.filter((_, itemIndex) => itemIndex !== index),
                            )
                          }
                          className="mb-0.5 rounded-lg border border-white/[0.07] px-2 py-1.5 text-[10px] text-muted hover:border-danger/30 hover:text-danger"
                        >
                          remove
                        </button>
                      </div>
                    ))}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setValue(["strategy", "exits", "take_profits"], [
                          ...config.strategy.exits.take_profits,
                          { gain_pct: 2.0, sell_fraction: 0.3 },
                        ])
                      }
                    >
                      + Add take-profit level
                    </Button>
                    <p className="text-[10px] leading-relaxed text-muted">
                      Sell fractions are portions of the original position. Levels are executed top-down.
                    </p>
                  </div>
                </SectionCard>

                <SectionCard title="Circuit breaker" description="Daily loss protection across the whole account.">
                  <FieldRow label="Daily loss limit" hint="Trading halts after this drawdown from the UTC day start.">
                    <PctBox value={config.strategy.circuit_breaker.daily_loss_limit_pct} onChange={(value) => setValue(["strategy", "circuit_breaker", "daily_loss_limit_pct"], value)} />
                  </FieldRow>
                  <div className="mt-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[10px] text-muted">
                    Current day drawdown{" "}
                    <span className="font-mono text-fg">{Math.max(0, snapshot?.breaker?.drawdown_today_pct ?? 0).toFixed(2)}%</span>{" "}
                    vs limit <span className="font-mono text-fg">{((config.strategy.circuit_breaker.daily_loss_limit_pct ?? 0) * 100).toFixed(0)}%</span>.
                  </div>
                </SectionCard>
              </div>
            ) : null}

            {tab === "sizing" ? (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <SectionCard title="Portfolio limits" description="Caps that keep a single token from dominating the account.">
                  <FieldRow label="Max position" hint="Largest share of equity in one trade.">
                    <PctBox value={config.paper.max_position_pct} onChange={(value) => setValue(["paper", "max_position_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Max open exposure" hint="Total capital allowed across open positions.">
                    <PctBox value={config.paper.max_open_exposure_pct} onChange={(value) => setValue(["paper", "max_open_exposure_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Cash reserve" hint="Minimum cash kept available at all times.">
                    <PctBox value={config.paper.cash_reserve_pct} onChange={(value) => setValue(["paper", "cash_reserve_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Max pool share" hint="Limit relative to the token's liquidity pool.">
                    <PctBox value={config.paper.max_pool_share_pct} onChange={(value) => setValue(["paper", "max_pool_share_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Min trade size" hint="Skip entries smaller than this.">
                    <NumberBox value={config.paper.min_trade_usd} min={0} step={0.5} suffix="$" onChange={(value) => setValue(["paper", "min_trade_usd"], value)} />
                  </FieldRow>
                  <FieldRow label="Starting bankroll" hint="Applies to new resets.">
                    <NumberBox value={config.paper.starting_balance} min={1} step={10} suffix="$" onChange={(value) => setValue(["paper", "starting_balance"], value)} />
                  </FieldRow>
                </SectionCard>

                <SectionCard title="Conviction sizing" description="Score, confidence and streaks scale the base position.">
                  <FieldRow label="Base size of equity" hint="Starting point before conviction multipliers.">
                    <PctBox value={config.strategy.sizing.base_pct_of_equity} step={0.5} onChange={(value) => setValue(["strategy", "sizing", "base_pct_of_equity"], value)} />
                  </FieldRow>
                  <FieldRow label="Score scale" hint="How aggressively score increases size.">
                    <NumberBox value={config.strategy.sizing.score_scale} min={0} step={0.1} onChange={(value) => setValue(["strategy", "sizing", "score_scale"], value)} />
                  </FieldRow>
                  <FieldRow label="Confidence floor" hint="Lower bound of the confidence multiplier.">
                    <NumberBox value={config.strategy.sizing.confidence_floor} min={0} step={0.05} onChange={(value) => setValue(["strategy", "sizing", "confidence_floor"], value)} />
                  </FieldRow>
                  <FieldRow label="Confidence ceiling" hint="Upper bound of the confidence multiplier.">
                    <NumberBox value={config.strategy.sizing.confidence_ceiling} min={0} step={0.05} onChange={(value) => setValue(["strategy", "sizing", "confidence_ceiling"], value)} />
                  </FieldRow>
                  <FieldRow label="Kelly fraction" hint="Fractional Kelly scaling applied to edge.">
                    <NumberBox value={config.strategy.sizing.kelly_fraction} min={0} max={1} step={0.05} onChange={(value) => setValue(["strategy", "sizing", "kelly_fraction"], value)} />
                  </FieldRow>
                  <FieldRow label="Kelly payoff" hint="Assumed payoff ratio for Kelly.">
                    <NumberBox value={config.strategy.sizing.kelly_payoff} min={0.1} step={0.1} onChange={(value) => setValue(["strategy", "sizing", "kelly_payoff"], value)} />
                  </FieldRow>
                </SectionCard>

                <div className="lg:col-span-2">
                  <SectionCard title="Streak adjustments" description="Reduce after losses, expand carefully after wins.">
                    <div className="grid grid-cols-1 gap-x-8 sm:grid-cols-2 lg:grid-cols-4">
                      <FieldRow label="Losing streak cut" hint="Multiplier per consecutive loss.">
                        <NumberBox value={config.strategy.sizing.losing_streak_cut} min={0} step={0.05} onChange={(value) => setValue(["strategy", "sizing", "losing_streak_cut"], value)} />
                      </FieldRow>
                      <FieldRow label="Winning streak boost" hint="Multiplier per consecutive win.">
                        <NumberBox value={config.strategy.sizing.winning_streak_boost} min={1} step={0.02} onChange={(value) => setValue(["strategy", "sizing", "winning_streak_boost"], value)} />
                      </FieldRow>
                      <FieldRow label="Max streak mult" hint="Upper streak multiplier cap.">
                        <NumberBox value={config.strategy.sizing.max_streak_mult} min={1} step={0.05} onChange={(value) => setValue(["strategy", "sizing", "max_streak_mult"], value)} />
                      </FieldRow>
                      <FieldRow label="Min streak mult" hint="Lower streak multiplier floor.">
                        <NumberBox value={config.strategy.sizing.min_streak_mult} min={0} step={0.05} onChange={(value) => setValue(["strategy", "sizing", "min_streak_mult"], value)} />
                      </FieldRow>
                    </div>
                  </SectionCard>
                </div>
              </div>
            ) : null}

            {tab === "execution" ? (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <SectionCard title="Costs & slippage" description="Pessimistic simulation of Solana execution.">
                  <FieldRow label="Taker fee" hint="Applied to buys and sells.">
                    <PctBox value={config.paper.taker_fee_pct} step={0.05} onChange={(value) => setValue(["paper", "taker_fee_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Priority fee" hint="Paid per transaction in SOL.">
                    <NumberBox value={config.paper.priority_fee_sol} min={0} step={0.0001} suffix="SOL" onChange={(value) => setValue(["paper", "priority_fee_sol"], value)} />
                  </FieldRow>
                  <FieldRow label="Jito tip" hint="Additional tip in SOL.">
                    <NumberBox value={config.paper.jito_tip_sol} min={0} step={0.0001} suffix="SOL" onChange={(value) => setValue(["paper", "jito_tip_sol"], value)} />
                  </FieldRow>
                  <FieldRow label="Random slippage min" hint="Extra floor on top of AMM impact.">
                    <PctBox value={config.paper.random_slippage_min_pct} step={0.1} onChange={(value) => setValue(["paper", "random_slippage_min_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Random slippage max" hint="Extra ceiling on top of AMM impact.">
                    <PctBox value={config.paper.random_slippage_max_pct} step={0.1} onChange={(value) => setValue(["paper", "random_slippage_max_pct"], value)} />
                  </FieldRow>
                  <FieldRow label="Mark haircut" hint="Conservative mark-to-market discount.">
                    <PctBox value={config.paper.mark_haircut_pct} step={0.1} onChange={(value) => setValue(["paper", "mark_haircut_pct"], value)} />
                  </FieldRow>
                </SectionCard>

                <SectionCard title="Latency & failures" description="Realistic delays and failed transactions.">
                  <FieldRow label="Delay min" hint="Random delay before execution.">
                    <NumberBox value={config.paper.execution_delay_min_ms} min={0} suffix="ms" onChange={(value) => setValue(["paper", "execution_delay_min_ms"], value)} />
                  </FieldRow>
                  <FieldRow label="Delay max" hint="Upper bound of execution delay.">
                    <NumberBox value={config.paper.execution_delay_max_ms} min={0} suffix="ms" onChange={(value) => setValue(["paper", "execution_delay_max_ms"], value)} />
                  </FieldRow>
                  <FieldRow label="Buy failure rate" hint="Simulated failed buy transactions.">
                    <PctBox value={config.paper.failed_tx_rate} step={1} onChange={(value) => setValue(["paper", "failed_tx_rate"], value)} />
                  </FieldRow>
                  <FieldRow label="Sell failure rate" hint="Failed exits are retried.">
                    <PctBox value={config.paper.sell_failed_tx_rate} step={1} onChange={(value) => setValue(["paper", "sell_failed_tx_rate"], value)} />
                  </FieldRow>
                  <FieldRow label="Equity snapshot" hint="Interval between stored equity points.">
                    <NumberBox value={config.paper.equity_snapshot_seconds} min={1} suffix="s" onChange={(value) => setValue(["paper", "equity_snapshot_seconds"], value)} />
                  </FieldRow>
                  <div className="mt-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 font-mono text-[10px] text-muted">
                    SOL price <span className="text-fg">{fmtUsd(config.app.sol_price_usd)}</span> · mode{" "}
                    <span className="text-accent">{runtimeMode.toUpperCase()}</span>
                  </div>
                </SectionCard>
              </div>
            ) : null}

            {tab === "feeds" ? (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <SectionCard title="Scanner cadence" description="How often new launches and prices are polled.">
                  <FieldRow label="Demo token interval" hint="Average seconds between demo launches.">
                    <NumberBox value={config.listener.demo_token_interval_seconds} min={1} suffix="s" onChange={(value) => setValue(["listener", "demo_token_interval_seconds"], value)} />
                  </FieldRow>
                  <FieldRow label="Demo token jitter" hint="Random variation around the interval.">
                    <NumberBox value={config.listener.demo_token_jitter_seconds} min={0} suffix="s" onChange={(value) => setValue(["listener", "demo_token_jitter_seconds"], value)} />
                  </FieldRow>
                  <FieldRow label="DexScreener poll" hint="New pair polling interval.">
                    <NumberBox value={config.listener.dexscreener_poll_seconds} min={1} suffix="s" onChange={(value) => setValue(["listener", "dexscreener_poll_seconds"], value)} />
                  </FieldRow>

                  <FieldRow label="Price poll" hint="Background token price refresh.">
                    <NumberBox value={config.listener.price_poll_seconds} min={1} suffix="s" onChange={(value) => setValue(["listener", "price_poll_seconds"], value)} />
                  </FieldRow>
                  <FieldRow label="Position price poll" hint="Faster refresh for open positions.">
                    <NumberBox value={config.listener.position_price_poll_seconds} min={1} suffix="s" onChange={(value) => setValue(["listener", "position_price_poll_seconds"], value)} />
                  </FieldRow>
                  <FieldRow label="Max tokens / minute" hint="Rate limit for the scanner.">
                    <NumberBox value={config.listener.max_tokens_per_minute} min={1} onChange={(value) => setValue(["listener", "max_tokens_per_minute"], value)} />
                  </FieldRow>
                </SectionCard>

                <SectionCard title="Notifications" description="Telegram alerts require bot token and chat id env vars.">
                  <ToggleRow
                    label="Enable notifications"
                    hint="Master switch for outbound alerts."
                    checked={config.notifier.enabled}
                    onChange={(value) => setValue(["notifier", "enabled"], value)}
                  />
                  <ToggleRow
                    label="Notify buys"
                    checked={config.notifier.notify_buys}
                    onChange={(value) => setValue(["notifier", "notify_buys"], value)}
                  />
                  <ToggleRow
                    label="Notify sells"
                    checked={config.notifier.notify_sells}
                    onChange={(value) => setValue(["notifier", "notify_sells"], value)}
                  />
                  <ToggleRow
                    label="Notify big wins"
                    checked={config.notifier.notify_big_wins}
                    onChange={(value) => setValue(["notifier", "notify_big_wins"], value)}
                  />
                  <FieldRow label="Big win threshold" hint="Minimum P&L to qualify.">
                    <NumberBox value={config.notifier.big_win_usd} min={0} suffix="$" onChange={(value) => setValue(["notifier", "big_win_usd"], value)} />
                  </FieldRow>
                  <ToggleRow
                    label="Notify errors"
                    checked={config.notifier.notify_errors}
                    onChange={(value) => setValue(["notifier", "notify_errors"], value)}
                  />
                </SectionCard>

                <div className="lg:col-span-2">
                  <SectionCard title="API access" description="Allowed browser origins for REST and WebSocket connections.">
                    <CorsField value={config.api.cors_origins} onChange={(value) => setValue(["api", "cors_origins"], value)} />
                    <p className="mt-2 font-mono text-[10px] text-muted">
                      REST {API_BASE} · WS {API_BASE.replace(/^http/, "ws")}/ws
                    </p>
                  </SectionCard>
                </div>
              </div>
            ) : null}

            {tab === "general" ? (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <SectionCard title="Runtime" description="Startup mode and logging. Mode changes restart the scanner.">
                  <FieldRow label="Mode" hint="Demo generates synthetic launches; live polls real feeds.">
                    <select
                      value={config.app.mode}
                      onChange={(event) => setValue(["app", "mode"], event.target.value)}
                      className="w-full rounded-lg border border-white/[0.08] bg-[#0a0f16] px-2 py-1.5 font-mono text-xs text-fg outline-none focus:border-accent/30"
                    >
                      <option value="demo">demo</option>
                      <option value="live">live</option>
                    </select>
                  </FieldRow>
                  <FieldRow label="Log level" hint="Backend logging verbosity.">
                    <select
                      value={config.app.log_level}
                      onChange={(event) => setValue(["app", "log_level"], event.target.value)}
                      className="w-full rounded-lg border border-white/[0.08] bg-[#0a0f16] px-2 py-1.5 font-mono text-xs text-fg outline-none focus:border-accent/30"
                    >
                      {["DEBUG", "INFO", "WARNING", "ERROR"].map((level) => (
                        <option key={level} value={level}>
                          {level}
                        </option>
                      ))}
                    </select>
                  </FieldRow>
                  <ToggleRow
                    label="Auto-seed demo data"
                    hint="Seed sample tokens when the database is empty."
                    checked={config.app.demo_seed}
                    onChange={(value) => setValue(["app", "demo_seed"], value)}
                  />
                  <FieldRow label="Fallback SOL price" hint="Used when the live price feed is unavailable.">
                    <NumberBox value={config.app.sol_price_usd} min={1} step={1} suffix="$" onChange={(value) => setValue(["app", "sol_price_usd"], value)} />
                  </FieldRow>
                  <div className="mt-3 rounded-lg border border-warn/20 bg-warn/[0.05] px-3 py-2 text-[10px] text-muted">
                    Live mode uses real market data but never signs transactions. Trading remains fully simulated.
                  </div>
                </SectionCard>

                <SectionCard title="Paper account" description="Local simulation state stored in SQLite.">
                  <div className="space-y-2 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-muted">Equity</span>
                      <span className="font-mono text-fg">{fmtUsd(snapshot?.wallet?.equity ?? 100)}</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-muted">Realized P&amp;L</span>
                      <span className={cn("font-mono", (snapshot?.wallet?.realized_pnl ?? 0) >= 0 ? "text-accent" : "text-danger")}>
                        {fmtUsd(snapshot?.wallet?.realized_pnl ?? 0)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-muted">Open positions</span>
                      <span className="font-mono text-fg">{snapshot?.wallet?.open_count ?? 0}</span>
                    </div>
                  </div>

                  <div className="mt-3 space-y-2">
                    {accountConfirm ? (
                      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-danger/25 bg-danger/[0.06] px-3 py-2">
                        <p className="flex-1 text-[10px] text-muted">
                          Wipe cash, positions, trades, equity history and logs, then restore the starting bankroll.
                        </p>
                        <Button variant="outline" size="sm" onClick={() => setAccountConfirm(false)}>
                          Cancel
                        </Button>
                        <Button variant="danger" size="sm" onClick={resetAccount} disabled={busy === "account"}>
                          {busy === "account" ? <Loader2 className="h-3 w-3 animate-spin" /> : null} Reset
                        </Button>
                      </div>
                    ) : (
                      <Button variant="danger" size="sm" onClick={() => setAccountConfirm(true)}>
                        <RotateCcw className="h-3.5 w-3.5" /> Reset paper account
                      </Button>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" size="sm" onClick={spawn} disabled={!isDemo || busy === "spawn"}>
                        {busy === "spawn" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                        Spawn 10 tokens
                      </Button>
                      <Button variant="outline" size="sm" onClick={seed} disabled={!isDemo || busy === "seed"}>
                        {busy === "seed" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
                        Rebuild demo dataset
                      </Button>
                    </div>
                    {!isDemo ? (
                      <p className="text-[10px] text-warn">Demo seeding and spawning are disabled while in live mode.</p>
                    ) : null}
                  </div>
                </SectionCard>

                <div className="lg:col-span-2">
                  <SectionCard title="About" description="MemeRadar is a local-first research terminal.">
                    <div className="grid grid-cols-1 gap-3 text-[11px] sm:grid-cols-3">
                      <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                        <p className="font-mono text-[9px] uppercase tracking-wider text-muted">Frontend</p>
                        <p className="mt-1 text-fg">Next.js · React 18 · Tailwind</p>
                      </div>
                      <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                        <p className="font-mono text-[9px] uppercase tracking-wider text-muted">Backend</p>
                        <p className="mt-1 text-fg">FastAPI · SQLite · WebSockets</p>
                      </div>
                      <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                        <p className="font-mono text-[9px] uppercase tracking-wider text-muted">Trading</p>
                        <p className="mt-1 text-fg">Paper only · no private keys</p>
                      </div>
                    </div>
                  </SectionCard>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </Shell>
  );
}
