import { BarChart, PieChart } from "@mantine/charts";
import {
  Card,
  Grid,
  Group,
  ScrollArea,
  SimpleGrid,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

const PALETTE = [
  "blue.6", "teal.6", "grape.6", "orange.6", "red.6",
  "cyan.6", "lime.6", "pink.6", "indigo.6", "yellow.6",
  "green.6", "violet.6",
];

function fmtBytes(n: number): string {
  if (!n) return "0 B";
  const u = ["B", "KiB", "MiB", "GiB", "TiB"];
  const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`;
}

interface Stats {
  totals: { files: number; size: number; downloaded: number; high_value: number; empty_dirs: number };
  by_extension: { ext: string; count: number; size: number }[];
  by_share: { target: string; share: string; count: number; size: number }[];
  by_target: { target: string; count: number; size: number }[];
  size_buckets: { label: string; count: number }[];
  largest: { target: string; share: string; path: string; size: number; content_hash: string | null }[];
  secrets: {
    total: number;
    unique: number;
    by_share: { target: string; share: string; count: number }[];
    by_rule: { rule: string; count: number; comment: string }[];
  };
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card withBorder padding="sm">
      <Text size="xs" c="dimmed" tt="uppercase">{label}</Text>
      <Text fw={700} size="xl">{value}</Text>
    </Card>
  );
}

export function Stats({ scanId }: { scanId: string }) {
  const q = useQuery({
    queryKey: ["scan", scanId, "stats"],
    queryFn: () => api.get<Stats>(`/api/scans/${scanId}/stats`),
  });

  if (q.isLoading) return <Text c="dimmed">Loading…</Text>;
  if (q.isError || !q.data) return <Text c="red">No file data for this scan.</Text>;
  const d = q.data;

  const TOP = 10;
  const extTop = d.by_extension.slice(0, TOP);
  const extRest = d.by_extension.slice(TOP).reduce((a, e) => a + e.count, 0);
  const pieByType = [
    ...extTop.map((e, i) => ({ name: e.ext, value: e.count, color: PALETTE[i % PALETTE.length] })),
    ...(extRest ? [{ name: "(other)", value: extRest, color: "gray.5" }] : []),
  ];
  const pieBySizeExt = extTop.map((e, i) => ({
    name: e.ext,
    value: e.size,
    color: PALETTE[i % PALETTE.length],
  }));

  const shareBars = d.by_share.slice(0, 15).map((s) => ({
    share: `${s.share}`,
    label: `\\\\${s.target}\\${s.share}`,
    files: s.count,
  }));

  const sec = d.secrets ?? { total: 0, unique: 0, by_share: [], by_rule: [] };
  const secShareBars = sec.by_share.slice(0, 15).map((s) => ({
    share: s.share,
    secrets: s.count,
  }));
  const secRuleBars = sec.by_rule.slice(0, 15).map((r) => ({
    rule: r.rule,
    secrets: r.count,
  }));

  return (
    <Grid>
      <Grid.Col span={12}>
        <SimpleGrid cols={{ base: 2, sm: 6 }}>
          <StatCard label="Files" value={d.totals.files} />
          <StatCard label="Total size" value={fmtBytes(d.totals.size)} />
          <StatCard label="Downloaded" value={d.totals.downloaded} />
          <StatCard label="High-value" value={d.totals.high_value} />
          <StatCard label="Secrets" value={sec.total} />
          <StatCard label="Unique secrets" value={sec.unique} />
        </SimpleGrid>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <Card withBorder>
          <Title order={6} mb="sm">Files by type</Title>
          {pieByType.length ? (
            <PieChart data={pieByType} h={260} withTooltip tooltipDataSource="segment" withLabels labelsType="value" />
          ) : <Text c="dimmed">—</Text>}
        </Card>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <Card withBorder>
          <Title order={6} mb="sm">Disk volume by type</Title>
          {pieBySizeExt.some((x) => x.value > 0) ? (
            <PieChart data={pieBySizeExt} h={260} withTooltip tooltipDataSource="segment" valueFormatter={fmtBytes} />
          ) : <Text c="dimmed">—</Text>}
        </Card>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <Card withBorder>
          <Title order={6} mb="sm">Files per share (top 15)</Title>
          {shareBars.length ? (
            <BarChart
              h={Math.max(200, shareBars.length * 26)}
              data={shareBars}
              dataKey="share"
              orientation="vertical"
              yAxisProps={{ width: 120 }}
              series={[{ name: "files", color: "blue.6" }]}
              withTooltip
            />
          ) : <Text c="dimmed">—</Text>}
        </Card>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <Card withBorder>
          <Title order={6} mb="sm">File size distribution</Title>
          <BarChart
            h={260}
            data={d.size_buckets}
            dataKey="label"
            series={[{ name: "count", color: "teal.6" }]}
            withTooltip
            xAxisProps={{ angle: -30, textAnchor: "end", height: 70 }}
          />
        </Card>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <Card withBorder>
          <Title order={6} mb="sm">Secrets per share</Title>
          {secShareBars.length ? (
            <BarChart
              h={Math.max(180, secShareBars.length * 26)}
              data={secShareBars}
              dataKey="share"
              orientation="vertical"
              yAxisProps={{ width: 120 }}
              series={[{ name: "secrets", color: "red.6" }]}
              withTooltip
            />
          ) : (
            <Text c="dimmed">No secrets.</Text>
          )}
        </Card>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <Card withBorder>
          <Title order={6} mb="sm">Secrets by rule</Title>
          {secRuleBars.length ? (
            <BarChart
              h={Math.max(180, secRuleBars.length * 26)}
              data={secRuleBars}
              dataKey="rule"
              orientation="vertical"
              yAxisProps={{ width: 160 }}
              series={[{ name: "secrets", color: "grape.6" }]}
              withTooltip
            />
          ) : (
            <Text c="dimmed">No secrets.</Text>
          )}
        </Card>
      </Grid.Col>

      {sec.by_rule.length > 0 && (
        <Grid.Col span={12}>
          <Card withBorder>
            <Title order={6} mb="sm">Secret rules</Title>
            <ScrollArea>
              <Table striped>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Rule</Table.Th>
                    <Table.Th>Hits</Table.Th>
                    <Table.Th>Description</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {sec.by_rule.map((r) => (
                    <Table.Tr key={r.rule}>
                      <Table.Td><Text ff="monospace" size="sm">{r.rule}</Text></Table.Td>
                      <Table.Td>{r.count}</Table.Td>
                      <Table.Td><Text size="sm" c="dimmed">{r.comment}</Text></Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          </Card>
        </Grid.Col>
      )}

      <Grid.Col span={12}>
        <Card withBorder>
          <Group justify="space-between" mb="sm">
            <Title order={6}>Largest files</Title>
            <Text size="xs" c="dimmed">top {d.largest.length}</Text>
          </Group>
          <ScrollArea>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Path</Table.Th>
                  <Table.Th>Size</Table.Th>
                  <Table.Th>Downloaded</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {d.largest.map((f, i) => (
                  <Table.Tr key={i}>
                    <Table.Td>
                      <Text size="sm" style={{ wordBreak: "break-all" }}>
                        {`\\\\${f.target}\\${f.share}\\${f.path}`}
                      </Text>
                    </Table.Td>
                    <Table.Td><Text size="sm">{fmtBytes(f.size)}</Text></Table.Td>
                    <Table.Td>{f.content_hash ? "yes" : "—"}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Card>
      </Grid.Col>

      <Grid.Col span={12}>
        <Card withBorder>
          <Title order={6} mb="sm">By file type</Title>
          <ScrollArea>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Extension</Table.Th>
                  <Table.Th>Files</Table.Th>
                  <Table.Th>Total size</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {d.by_extension.map((e) => (
                  <Table.Tr key={e.ext}>
                    <Table.Td><Text ff="monospace">{e.ext}</Text></Table.Td>
                    <Table.Td>{e.count}</Table.Td>
                    <Table.Td>{fmtBytes(e.size)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Card>
      </Grid.Col>
    </Grid>
  );
}
