"use client";

import { ColorType, CrosshairMode, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";

import { fmtPrice } from "@/lib/format";
import type { PricePoint } from "@/lib/types";

export function PriceChart({ points, height = 220 }: { points: PricePoint[]; height?: number }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "rgba(148,163,184,0.7)",
        fontFamily: "JetBrains Mono, monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.035)" },
        horzLines: { color: "rgba(255,255,255,0.035)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "rgba(255,255,255,0.2)", labelBackgroundColor: "#111827" },
        horzLine: { color: "rgba(255,255,255,0.2)", labelBackgroundColor: "#111827" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.06)" },
      timeScale: { borderColor: "rgba(255,255,255,0.06)", timeVisible: true, secondsVisible: true },
      localization: {
        priceFormatter: (price: number) => fmtPrice(price),
        timeFormatter: (time: number) =>
          new Date(time * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      },
      handleScroll: false,
      handleScale: false,
    });

    const series = chart.addAreaSeries({
      lineColor: "rgba(61, 245, 174, 1)",
      lineWidth: 2,
      topColor: "rgba(52,245,164,0.24)",
      bottomColor: "rgba(52,245,164,0.01)",
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerBorderColor: "#05080d",
      crosshairMarkerBackgroundColor: "rgba(61, 245, 174, 1)",
      priceFormat: { type: "price", precision: 8, minMove: 0.00000001 },
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) chart.applyOptions({ width: Math.floor(entry.contentRect.width) });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;
    const data = (points || [])
      .map((point) => ({
        time: Math.floor(Number(point.t) / 1000) as UTCTimestamp,
        value: Number(point.p),
      }))
      .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.value))
      .sort((a, b) => a.time - b.time);
    const unique = data.filter((point, index) => index === 0 || point.time !== data[index - 1].time);
    series.setData(unique);
    if (unique.length > 1) {
      chart.timeScale().fitContent();
    }
  }, [points]);

  return (
    <div className="relative w-full overflow-hidden rounded-xl border border-white/[0.06] bg-black/20">
      <div ref={containerRef} style={{ height }} className="w-full" />
      {(!points || points.length < 2) && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-muted">No price history yet</div>
      )}
    </div>
  );
}
