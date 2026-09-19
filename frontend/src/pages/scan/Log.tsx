import { useEffect, useRef, useState } from "react";
import { Button, Code, Group, ScrollArea, Switch, Text } from "@mantine/core";
import { IconDownload, IconRefresh } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { api, Scan } from "../../api";

export function Log({ scanId, scan }: { scanId: string; scan?: Scan }) {
  const running = scan && ["queued", "running"].includes(scan.status);
  const [follow, setFollow] = useState(true);
  const viewport = useRef<HTMLDivElement>(null);

  const q = useQuery({
    queryKey: ["scan", scanId, "log-full"],
    queryFn: () => api.getText(`/api/scans/${scanId}/log?tail=5000000`),
    refetchInterval: running && follow ? 3000 : false,
  });

  useEffect(() => {
    if (follow && viewport.current) {
      viewport.current.scrollTo({ top: viewport.current.scrollHeight });
    }
  }, [q.data, follow]);

  const text = q.data ?? "";

  return (
    <>
      <Group justify="space-between" mb="xs">
        <Text size="sm" c="dimmed">
          {text ? `${text.split("\n").length} lines` : "no log yet"}
        </Text>
        <Group gap="sm">
          {running && (
            <Switch
              size="xs"
              label="follow"
              checked={follow}
              onChange={(e) => setFollow(e.currentTarget.checked)}
            />
          )}
          <Button
            size="xs"
            variant="default"
            leftSection={<IconRefresh size={14} />}
            onClick={() => q.refetch()}
            loading={q.isFetching}
          >
            Refresh
          </Button>
          <Button
            size="xs"
            variant="light"
            leftSection={<IconDownload size={14} />}
            component="a"
            href={`/api/scans/${scanId}/log?tail=100000000`}
            target="_blank"
          >
            Download
          </Button>
        </Group>
      </Group>

      <ScrollArea h="calc(100vh - 220px)" viewportRef={viewport}>
        <Code block style={{ fontSize: 12, whiteSpace: "pre" }}>
          {text || "—"}
        </Code>
      </ScrollArea>
    </>
  );
}
