export function ConfidenceMeter({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const tone = score < 0.6 ? "bad" : score < 0.85 ? "warn" : "good";
  const barClass = { bad: "bg-bad", warn: "bg-warn", good: "bg-good" }[tone];
  const textClass = { bad: "text-bad", warn: "text-warn", good: "text-good" }[tone];

  return (
    <div className="flex items-center justify-center gap-2">
      <span className="h-[5px] w-[46px] flex-none overflow-hidden rounded-full border border-border bg-surface-2">
        <span className={`block h-full rounded-full ${barClass}`} style={{ width: `${pct}%` }} />
      </span>
      <span className={`w-9 text-right font-mono text-[12.5px] tabular-nums ${textClass}`}>{pct} %</span>
    </div>
  );
}
