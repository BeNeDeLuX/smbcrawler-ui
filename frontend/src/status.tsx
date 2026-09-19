import { Badge } from "@mantine/core";
import type { ScanStatus } from "./api";

const COLORS: Record<ScanStatus, string> = {
  queued: "gray",
  running: "blue",
  done: "green",
  failed: "red",
  canceled: "orange",
  imported: "teal",
};

export function StatusBadge({ status }: { status: ScanStatus }) {
  return (
    <Badge color={COLORS[status] ?? "gray"} variant="light">
      {status}
    </Badge>
  );
}

export function pct(progress: Record<string, any>): number | null {
  if (typeof progress?.percent === "number") return progress.percent;
  return null;
}
