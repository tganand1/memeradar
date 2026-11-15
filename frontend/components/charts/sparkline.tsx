export function Sparkline({
  values,
  width = 96,
  height = 28,
  positive,
  strokeWidth = 1.5,
}: {
  values: number[];
  width?: number;
  height?: number;
  positive?: boolean;
  strokeWidth?: number;
}) {
  if (!values || values.length < 2) {
    return <div style={{ width, height }} className="rounded bg-white/[0.03]" />;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);
  const points = values.map((value, index) => {
    const x = index * stepX;
    const y = height - ((value - min) / range) * (height - 4) - 2;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  const isPositive = positive ?? values[values.length - 1] >= values[0];
  const color = isPositive ? "hsl(157, 90%, 60%)" : "hsl(355, 85%, 62%)";
  const gradientId = `spark-${Math.round(values[0] * 1e6)}-${values.length}-${width}`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.22} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={`0,${height} ${points.join(" ")} ${width},${height}`} fill={`url(#${gradientId})`} />
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
