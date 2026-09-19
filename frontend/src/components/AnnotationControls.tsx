import { useEffect, useState } from "react";
import { Button, Group, SegmentedControl, Textarea } from "@mantine/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, Annotation, AnnotationStatus } from "../api";

const OPTIONS: { label: string; value: AnnotationStatus }[] = [
  { label: "Open", value: "open" },
  { label: "Reviewed", value: "reviewed" },
  { label: "False positive", value: "false_positive" },
  { label: "Important", value: "important" },
];

export function AnnotationControls({
  scanId,
  kind,
  refId,
  current,
  invalidateKeys = [],
}: {
  scanId: string;
  kind: "path" | "file" | "secret";
  refId: string;
  current?: Annotation | null;
  invalidateKeys?: unknown[][];
}) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<AnnotationStatus>(current?.status ?? "open");
  const [note, setNote] = useState(current?.note ?? "");

  useEffect(() => {
    setStatus(current?.status ?? "open");
    setNote(current?.note ?? "");
  }, [current, refId]);

  const save = useMutation({
    mutationFn: () =>
      api.put(`/api/scans/${scanId}/annotations`, { kind, ref: refId, status, note }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scan", scanId, "annotations"] });
      invalidateKeys.forEach((k) => qc.invalidateQueries({ queryKey: k }));
    },
  });

  return (
    <Group align="flex-end" gap="sm" wrap="nowrap">
      <SegmentedControl size="xs" data={OPTIONS} value={status} onChange={(v) => setStatus(v as AnnotationStatus)} />
      <Textarea
        placeholder="note…"
        size="xs"
        autosize
        minRows={1}
        style={{ flex: 1 }}
        value={note}
        onChange={(e) => setNote(e.currentTarget.value)}
      />
      <Button size="xs" onClick={() => save.mutate()} loading={save.isPending}>
        Save
      </Button>
    </Group>
  );
}
