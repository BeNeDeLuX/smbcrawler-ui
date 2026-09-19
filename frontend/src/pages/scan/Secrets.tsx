import { useMemo, useState } from "react";
import { Badge, Code, Grid, Group, ScrollArea, Stack, Switch, Table, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { api, SecretRow } from "../../api";
import { PreviewPane } from "../../components/PreviewPane";
import { AnnotationControls } from "../../components/AnnotationControls";

export function Secrets({ scanId }: { scanId: string }) {
  const [hideFP, setHideFP] = useState(true);
  const [sel, setSel] = useState<SecretRow | null>(null);

  const key = ["scan", scanId, "secrets"];
  const q = useQuery({
    queryKey: key,
    queryFn: () => api.get<SecretRow[]>(`/api/scans/${scanId}/secrets`),
  });

  const rows = useMemo(
    () => (q.data ?? []).filter((r) => !(hideFP && r.annotation?.status === "false_positive")),
    [q.data, hideFP]
  );

  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 6 }}>
        <Group justify="space-between" mb="xs">
          <Text size="sm" c="dimmed">{rows.length} of {q.data?.length ?? 0}</Text>
          <Switch label="hide false positives" checked={hideFP} onChange={(e) => setHideFP(e.currentTarget.checked)} />
        </Group>
        <ScrollArea h="calc(100vh - 280px)">
          <Table highlightOnHover stickyHeader>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Secret</Table.Th>
                <Table.Th>Location</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((r, i) => (
                <Table.Tr
                  key={i}
                  onClick={() => setSel(r)}
                  style={{ cursor: "pointer", background: sel === r ? "var(--mantine-color-blue-light)" : undefined }}
                >
                  <Table.Td>
                    <Code>{r.secret}</Code>
                    {r.annotation?.status === "false_positive" && <Badge size="xs" color="gray" ml={4}>FP</Badge>}
                    {r.annotation?.status === "important" && <Badge size="xs" color="red" ml={4}>!</Badge>}
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed" style={{ wordBreak: "break-all" }}>
                      {`\\\\${r.target}\\${r.share}\\${r.path}`} : {r.line_number}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <Stack gap="xs">
          <PreviewPane
            scanId={scanId}
            target={
              sel
                ? { path: `\\\\${sel.target}\\${sel.share}\\${sel.path}`, content_hash: sel.content_hash, highlightLine: sel.line_number }
                : null
            }
          />
          {sel && (
            <AnnotationControls
              scanId={scanId}
              kind="secret"
              refId={sel.secret}
              current={sel.annotation}
              invalidateKeys={[key]}
            />
          )}
        </Stack>
      </Grid.Col>
    </Grid>
  );
}
