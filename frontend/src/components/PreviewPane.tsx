import { Alert, Badge, Button, Card, Code, Group, ScrollArea, Text } from "@mantine/core";
import { IconDownload } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export interface PreviewTarget {
  path: string;
  content_hash: string | null;
  size?: number;
  highlightLine?: number;
}

export function PreviewPane({
  scanId,
  target,
}: {
  scanId: string;
  target: PreviewTarget | null;
}) {
  const hash = target?.content_hash ?? null;
  const q = useQuery({
    queryKey: ["scan", scanId, "preview", hash],
    enabled: !!hash,
    queryFn: async () => {
      const res = await fetch(`/api/scans/${scanId}/files/${hash}/preview`, {
        credentials: "include",
      });
      if (res.status === 415) return { text: null, binary: true };
      if (!res.ok) throw new Error(await res.text());
      return { text: await res.text(), binary: false };
    },
  });

  if (!target) {
    return (
      <Card withBorder h="100%">
        <Text c="dimmed">Select a file to preview.</Text>
      </Card>
    );
  }

  const lines = (q.data?.text ?? "").split("\n");

  return (
    <Card withBorder h="100%" p="sm">
      <Group justify="space-between" mb="xs" wrap="nowrap">
        <Text fw={600} style={{ wordBreak: "break-all" }}>
          {target.path}
        </Text>
        {hash && (
          <Button
            size="xs"
            variant="light"
            leftSection={<IconDownload size={14} />}
            component="a"
            href={`/api/scans/${scanId}/files/${hash}`}
          >
            Raw
          </Button>
        )}
      </Group>
      <Group gap="xs" mb="xs">
        {target.size != null && <Badge variant="default">{target.size} B</Badge>}
        {hash && <Badge variant="default">sha256 {hash.slice(0, 12)}…</Badge>}
      </Group>

      {!hash && <Alert color="gray">This file was not downloaded — no preview available.</Alert>}
      {q.isError && <Alert color="red">{String((q.error as Error).message)}</Alert>}
      {q.data?.binary && <Alert color="yellow">Binary file — download the raw bytes.</Alert>}

      {q.data?.text != null && (
        <ScrollArea h="calc(100vh - 320px)">
          <Code block style={{ fontSize: 12, whiteSpace: "pre" }}>
            {lines.map((l, i) => (
              <div
                key={i}
                style={{
                  background:
                    target.highlightLine === i + 1 ? "var(--mantine-color-yellow-light)" : undefined,
                }}
              >
                <span style={{ opacity: 0.4, userSelect: "none" }}>
                  {String(i + 1).padStart(4, " ")}{"  "}
                </span>
                {l}
              </div>
            ))}
          </Code>
        </ScrollArea>
      )}
    </Card>
  );
}
