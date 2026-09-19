import { useState } from "react";
import {
  Badge,
  Checkbox,
  Grid,
  Group,
  Pagination,
  ScrollArea,
  Stack,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { api, PathRow } from "../../api";
import { PreviewPane, PreviewTarget } from "../../components/PreviewPane";
import { AnnotationControls } from "../../components/AnnotationControls";
import { FetchButton } from "../../components/FetchButton";

const PAGE = 100;

export function Files({ scanId }: { scanId: string }) {
  const [q, setQ] = useState("");
  const [hv, setHv] = useState(false);
  const [dl, setDl] = useState(true);
  const [page, setPage] = useState(1);
  const [sel, setSel] = useState<PathRow | null>(null);

  const params = new URLSearchParams({
    limit: String(PAGE),
    offset: String((page - 1) * PAGE),
  });
  if (q) params.set("q", q);
  if (hv) params.set("high_value", "true");
  if (dl) params.set("downloaded_only", "true");

  const listKey = ["scan", scanId, "paths", params.toString()];
  const list = useQuery({
    queryKey: listKey,
    queryFn: () => api.get<{ total: number; items: PathRow[] }>(`/api/scans/${scanId}/paths?${params}`),
  });

  const total = list.data?.total ?? 0;

  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 6 }}>
        <Stack gap="xs">
          <Group>
            <TextInput
              placeholder="path contains…"
              value={q}
              onChange={(e) => {
                setPage(1);
                setQ(e.currentTarget.value);
              }}
              style={{ flex: 1 }}
            />
          </Group>
          <Group>
            <Checkbox label="high-value only" checked={hv} onChange={(e) => { setPage(1); setHv(e.currentTarget.checked); }} />
            <Checkbox label="downloaded only" checked={dl} onChange={(e) => { setPage(1); setDl(e.currentTarget.checked); }} />
          </Group>
          <ScrollArea h="calc(100vh - 300px)">
            <Table highlightOnHover stickyHeader>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Path</Table.Th>
                  <Table.Th>Size</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {(list.data?.items ?? []).map((r) => (
                  <Table.Tr
                    key={r.id}
                    onClick={() => setSel(r)}
                    style={{ cursor: "pointer", background: sel?.id === r.id ? "var(--mantine-color-blue-light)" : undefined }}
                  >
                    <Table.Td>
                      <Text size="sm" style={{ wordBreak: "break-all" }}>
                        {r.high_value ? <Badge size="xs" color="grape" mr={4}>HV</Badge> : null}
                        {r.annotation?.status === "false_positive" ? <Badge size="xs" color="gray" mr={4}>FP</Badge> : null}
                        {r.annotation?.status === "important" ? <Badge size="xs" color="red" mr={4}>!</Badge> : null}
                        {`\\\\${r.target}\\${r.share}\\${r.path}`}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed">{r.content_hash ? r.size : "—"}</Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">{total} paths</Text>
            <Pagination value={page} onChange={setPage} total={Math.max(1, Math.ceil(total / PAGE))} size="sm" />
          </Group>
        </Stack>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <Stack gap="xs">
          <PreviewPane
            scanId={scanId}
            target={
              sel
                ? ({ path: `\\\\${sel.target}\\${sel.share}\\${sel.path}`, content_hash: sel.content_hash, size: sel.size } as PreviewTarget)
                : null
            }
          />
          {sel && !sel.content_hash && (
            <FetchButton
              scanId={scanId}
              pathId={sel.id}
              pathLabel={`\\\\${sel.target}\\${sel.share}\\${sel.path}`}
              invalidateKeys={[listKey]}
              onFetched={(h) => setSel({ ...sel, content_hash: h })}
            />
          )}
          {sel && (
            <AnnotationControls
              scanId={scanId}
              kind={sel.content_hash ? "file" : "path"}
              refId={sel.content_hash ?? String(sel.id)}
              current={sel.annotation}
              invalidateKeys={[listKey]}
            />
          )}
        </Stack>
      </Grid.Col>
    </Grid>
  );
}
