import { useState } from "react";
import { Badge, Group, Switch, Table, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

interface TargetRow {
  name: string;
  netbios_name: string | null;
  port_open: number;
  listable_authenticated: number | null;
  listable_unauthenticated: number | null;
  share_count: number;
  first_seen: string | null;
  last_activity: string | null;
}

// smbcrawler stores naive timestamps ("2026-09-02 17:53:00.123456"); show
// seconds precision as-is rather than guessing a timezone.
const ts = (v: string | null) => (v ? v.split(".")[0] : "—");

function TriState({ v }: { v: number | null }) {
  if (v == null)
    return (
      <Text span c="dimmed">
        n/a
      </Text>
    );
  return v ? (
    <Badge color="green" variant="light">
      yes
    </Badge>
  ) : (
    <Badge color="red" variant="light">
      denied
    </Badge>
  );
}

export function Targets({ scanId }: { scanId: string }) {
  const [noAccess, setNoAccess] = useState(false);

  const q = useQuery({
    queryKey: ["scan", scanId, "targets", noAccess],
    queryFn: () =>
      api.get<TargetRow[]>(
        `/api/scans/${scanId}/targets${noAccess ? "?no_access=true" : ""}`
      ),
  });

  const rows = q.data ?? [];

  return (
    <>
      <Group justify="space-between" mb="sm">
        <Text size="sm" c="dimmed">
          {rows.length} target{rows.length === 1 ? "" : "s"}
        </Text>
        <Switch
          label="only reachable servers where share listing failed"
          checked={noAccess}
          onChange={(e) => setNoAccess(e.currentTarget.checked)}
        />
      </Group>

      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Target</Table.Th>
            <Table.Th>NetBIOS</Table.Th>
            <Table.Th>Port 445</Table.Th>
            <Table.Th>List as user</Table.Th>
            <Table.Th>List as guest</Table.Th>
            <Table.Th>Shares</Table.Th>
            <Table.Th>Connected</Table.Th>
            <Table.Th>Last activity</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((t) => {
            const reachableNoAccess =
              t.port_open &&
              !t.listable_authenticated &&
              !t.listable_unauthenticated;
            return (
              <Table.Tr key={t.name}>
                <Table.Td fw={600}>
                  {t.name}
                  {reachableNoAccess ? (
                    <Badge ml={6} size="xs" color="orange">
                      no access
                    </Badge>
                  ) : null}
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {t.netbios_name ?? "—"}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {t.port_open ? (
                    <Badge color="green" variant="light">
                      open
                    </Badge>
                  ) : (
                    <Text span c="dimmed">
                      closed
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <TriState v={t.listable_authenticated} />
                </Table.Td>
                <Table.Td>
                  <TriState v={t.listable_unauthenticated} />
                </Table.Td>
                <Table.Td>{t.share_count}</Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed" ff="monospace">
                    {ts(t.first_seen)}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed" ff="monospace">
                    {ts(t.last_activity)}
                  </Text>
                </Table.Td>
              </Table.Tr>
            );
          })}
          {rows.length === 0 && (
            <Table.Tr>
              <Table.Td colSpan={8}>
                <Text ta="center" c="dimmed" py="lg">
                  Nothing here.
                </Text>
              </Table.Td>
            </Table.Tr>
          )}
        </Table.Tbody>
      </Table>
    </>
  );
}
