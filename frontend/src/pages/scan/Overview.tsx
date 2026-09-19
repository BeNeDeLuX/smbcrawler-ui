import { useEffect, useState } from "react";
import { Card, Code, Grid, Group, Progress, ScrollArea, SimpleGrid, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Scan } from "../../api";

function Stat({
  label,
  value,
  to,
}: {
  label: string;
  value: any;
  to?: string;
}) {
  return (
    <Card
      withBorder
      padding="sm"
      component={to ? Link : "div"}
      to={to}
      style={to ? { cursor: "pointer" } : undefined}
    >
      <Text size="xs" c="dimmed" tt="uppercase">
        {label}
      </Text>
      <Text fw={700} size="xl">
        {value ?? 0}
      </Text>
    </Card>
  );
}

export function Overview({ scanId, scan }: { scanId: string; scan?: Scan }) {
  const summary = useQuery({
    queryKey: ["scan", scanId, "summary"],
    queryFn: () => api.get<any>(`/api/scans/${scanId}/summary`),
    refetchInterval: scan && ["queued", "running"].includes(scan.status) ? 4000 : false,
  });

  const [log, setLog] = useState("");
  const running = scan && ["queued", "running"].includes(scan.status);

  useEffect(() => {
    if (!running) return;
    let stop = false;
    const tick = async () => {
      try {
        const r = await fetch(`/api/scans/${scanId}/log?tail=8000`, { credentials: "include" });
        if (!stop) setLog(await r.text());
      } catch {
        /* ignore */
      }
    };
    tick();
    const iv = setInterval(tick, 3000);
    return () => {
      stop = true;
      clearInterval(iv);
    };
  }, [scanId, running]);

  const sum = summary.data?.summary ?? {};
  const p = scan?.progress ?? {};

  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 8 }}>
        {running && (
          <Card withBorder mb="md">
            <Group justify="space-between" mb={4}>
              <Text fw={600}>
                {p.phase ?? "running"} — {p.targets_done ?? 0}/{p.targets_total ?? "?"} targets
              </Text>
              <Text size="sm" c="dimmed">
                {p.counts?.secret ?? 0} secrets · {p.counts?.downloaded ?? 0} files
              </Text>
            </Group>
            <Progress value={p.percent ?? 0} size="lg" striped animated />
          </Card>
        )}

        <SimpleGrid cols={{ base: 2, sm: 3 }}>
          <Stat label="Targets" value={sum.number_targets} to={`/scans/${scanId}/targets`} />
          <Stat label="Shares" value={sum.number_shares} to={`/scans/${scanId}/shares`} />
          <Stat label="Readable shares" value={sum.number_shares_listable_root} to={`/scans/${scanId}/shares`} />
          <Stat label="Writable shares" value={sum.number_shares_writable} to={`/scans/${scanId}/shares`} />
          <Stat label="Paths" value={sum.number_paths} to={`/scans/${scanId}/files`} />
          <Stat label="High-value files" value={sum.number_high_value_files} to={`/scans/${scanId}/files`} />
          <Stat label="Secrets" value={sum.number_secrets} to={`/scans/${scanId}/secrets`} />
          <Stat label="Unique secrets" value={sum.number_unique_secrets} to={`/scans/${scanId}/secrets`} />
          <Stat label="High-value shares" value={sum.number_high_value_shares} to={`/scans/${scanId}/shares`} />
        </SimpleGrid>

        {scan?.error && (
          <Card withBorder mt="md">
            <Title order={5} c="red">
              Error
            </Title>
            <Code block>{scan.error}</Code>
          </Card>
        )}
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 4 }}>
        <Card withBorder>
          <Title order={6} mb="xs">
            Run info
          </Title>
          <Text size="sm">
            smbcrawler {summary.data?.config?.smbcrawler_version ?? "—"}
          </Text>
          <Text size="sm" c="dimmed">
            {summary.data?.config?.created ?? ""}
          </Text>
          <Code block mt="xs" style={{ whiteSpace: "pre-wrap" }}>
            {scan?.params?.cmd ?? ""}
          </Code>
        </Card>

        {running && (
          <Card withBorder mt="md">
            <Title order={6} mb="xs">
              Live log
            </Title>
            <ScrollArea h={280}>
              <Code block style={{ whiteSpace: "pre-wrap", fontSize: 11 }}>
                {log || "…"}
              </Code>
            </ScrollArea>
          </Card>
        )}
      </Grid.Col>
    </Grid>
  );
}
