import { Badge, Code, SegmentedControl, Stack, Table, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api";

interface Ann {
  kind: string;
  ref: string;
  status: string;
  note: string;
  updated_at: string;
}

const COLOR: Record<string, string> = {
  open: "gray",
  reviewed: "blue",
  false_positive: "dark",
  important: "red",
};

export function Review({ scanId }: { scanId: string }) {
  const [status, setStatus] = useState("all");
  const q = useQuery({
    queryKey: ["scan", scanId, "annotations", status],
    queryFn: () =>
      api.get<Ann[]>(
        `/api/scans/${scanId}/annotations${status !== "all" ? `?status=${status}` : ""}`
      ),
  });

  return (
    <Stack>
      <SegmentedControl
        value={status}
        onChange={setStatus}
        data={["all", "important", "reviewed", "false_positive", "open"]}
      />
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Kind</Table.Th>
            <Table.Th>Ref</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Note</Table.Th>
            <Table.Th>Updated</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(q.data ?? []).map((a, i) => (
            <Table.Tr key={i}>
              <Table.Td>{a.kind}</Table.Td>
              <Table.Td>
                <Code style={{ wordBreak: "break-all" }}>{a.ref}</Code>
              </Table.Td>
              <Table.Td>
                <Badge color={COLOR[a.status] ?? "gray"}>{a.status}</Badge>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{a.note}</Text>
              </Table.Td>
              <Table.Td>
                <Text size="xs" c="dimmed">
                  {new Date(a.updated_at).toLocaleString()}
                </Text>
              </Table.Td>
            </Table.Tr>
          ))}
          {q.data?.length === 0 && (
            <Table.Tr>
              <Table.Td colSpan={5}>
                <Text ta="center" c="dimmed" py="lg">
                  Nothing here.
                </Text>
              </Table.Td>
            </Table.Tr>
          )}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
