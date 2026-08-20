type Props = {
  title: string;
  value: string;
  change: string;
  color?: string;
};

export default function KpiCard({
  title,
  value,
  change,
  color = "#14ACE8",
}: Props) {
  return (
    <div
      style={{
        background: "#121826",
        border: "1px solid #1f2937",
        borderRadius: 14,
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      <span
        style={{
          color: "#8FA3BF",
          fontSize: 14,
        }}
      >
        {title}
      </span>

      <span
        style={{
          fontSize: 32,
          fontWeight: 700,
        }}
      >
        {value}
      </span>

      <span
        style={{
          color,
          fontWeight: 600,
        }}
      >
        {change}
      </span>
    </div>
  );
}