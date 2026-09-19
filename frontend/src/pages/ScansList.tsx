import { Button, Group, Progress, Table, Text, Title } from "@mantine/core";
import { IconPlus, IconUpload } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Scan } from "../api";
import { StatusBadge, pct } from "../status";

export function ScansList() {
  const q = useQuery({
    queryKey: ["scans"],
    queryFn: () => api.get<Scan[]>("/api/scans"),
    refetchInterval: 4000,
  });

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={3}>Scans</Title>
        <Group>
          <Button component={Link} to="/scans/import" variant="default" leftSection={<IconUpload size={16} />}>
            Import .crwl
          </Button>
          <Button component={Link} to="/scans/new" leftSection={<IconPlus size={16} />}>
            New scan
          </Button>
        </Group>
      </Group>

      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Shares</Table.Th>
            <Table.Th>Result</Table.Th>
            <Table.Th>Created</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(q.data ?? []).map((s) => {
            const p = pct(s.progress);
            return (
              <Table.Tr key={s.id}>
                <Table.Td>
                  <Text component={Link} to={`/scans/${s.id}`} fw={600}>
                    {s.name}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <StatusBadge status={s.status} />
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {s.progress?.counts?.share ?? "—"}
                  </Text>
                </Table.Td>
                <Table.Td w={220}>
                  {s.status === "running" && p != null ? (
                    <Progress value={p} size="lg" striped animated />
                  ) : (
                    <Text size="sm" c="dimmed">
                      {s.progress?.counts
                        ? `${s.progress.counts.secret ?? 0} secrets · ${s.progress.counts.downloaded ?? 0} files`
                        : "—"}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {new Date(s.created_at).toLocaleString()}
                  </Text>
                </Table.Td>
              </Table.Tr>
            );
          })}
          {q.data?.length === 0 && (
            <Table.Tr>
              <Table.Td colSpan={5}>
                <Text c="dimmed" ta="center" py="xl">
                  No scans yet.
                </Text>
              </Table.Td>
            </Table.Tr>
          )}
        </Table.Tbody>
      </Table>
    </>
  );
}
