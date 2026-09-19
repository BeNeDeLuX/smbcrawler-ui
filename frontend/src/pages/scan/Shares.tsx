import { Badge, Checkbox, Group, Table, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, Share } from "../../api";

function Perm({ v }: { v: number | null }) {
  if (v == null) return <Text span c="dimmed">?</Text>;
  return v ? <Badge color="green" variant="light">yes</Badge> : <Text span c="dimmed">no</Text>;
}

export function Shares({ scanId }: { scanId: string }) {
  const [filters, setFilters] = useState({ high_value: false, readable: false, writable: false, guest: false });
  const qs = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v).map(([k]) => [k, "true"])
  ).toString();

  const q = useQuery({
    queryKey: ["scan", scanId, "shares", qs],
    queryFn: () => api.get<Share[]>(`/api/scans/${scanId}/shares${qs ? "?" + qs : ""}`),
  });

  return (
    <>
      <Group mb="sm">
        {(["high_value", "readable", "writable", "guest"] as const).map((k) => (
          <Checkbox
            key={k}
            label={k.replace("_", " ")}
            checked={filters[k]}
            onChange={(e) => setFilters({ ...filters, [k]: e.currentTarget.checked })}
          />
        ))}
      </Group>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Target</Table.Th>
            <Table.Th>Share</Table.Th>
            <Table.Th>Remark</Table.Th>
            <Table.Th>Auth</Table.Th>
            <Table.Th>Guest</Table.Th>
            <Table.Th>Write</Table.Th>
            <Table.Th>Read level</Table.Th>
            <Table.Th>HV</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(q.data ?? []).map((s, i) => (
            <Table.Tr key={i}>
              <Table.Td>{s.target}</Table.Td>
              <Table.Td fw={600}>{s.name}</Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">{s.remark}</Text>
              </Table.Td>
              <Table.Td><Perm v={s.auth_access} /></Table.Td>
              <Table.Td><Perm v={s.guest_access} /></Table.Td>
              <Table.Td><Perm v={s.write_access} /></Table.Td>
              <Table.Td>
                {s.read_level ?? "?"}
                {s.maxed_out ? " (maxed)" : ""}
              </Table.Td>
              <Table.Td>{s.high_value ? <Badge color="grape">HV</Badge> : ""}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </>
  );
}
