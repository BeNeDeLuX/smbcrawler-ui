import { Anchor, Button, Group, Menu, Tabs, Text, Title } from "@mantine/core";
import { IconDownload, IconTrash, IconX } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Navigate,
  Route,
  Routes,
  useNavigate,
  useParams,
  useLocation,
} from "react-router-dom";
import { api, Scan } from "../api";
import { StatusBadge } from "../status";
import { Overview } from "./scan/Overview";
import { Targets } from "./scan/Targets";
import { Shares } from "./scan/Shares";
import { Files } from "./scan/Files";
import { Stats } from "./scan/Stats";
import { Secrets } from "./scan/Secrets";
import { Search } from "./scan/Search";
import { Review } from "./scan/Review";
import { Log } from "./scan/Log";

const TABS = [
  "overview",
  "targets",
  "shares",
  "files",
  "stats",
  "secrets",
  "search",
  "review",
  "log",
] as const;

export function ScanDetail() {
  const { scanId = "" } = useParams();
  const nav = useNavigate();
  const loc = useLocation();
  const qc = useQueryClient();
  const active = TABS.find((t) => loc.pathname.endsWith(`/${t}`)) ?? "overview";

  const scan = useQuery({
    queryKey: ["scan", scanId],
    queryFn: () => api.get<Scan>(`/api/scans/${scanId}`),
    refetchInterval: (q) =>
      ["queued", "running"].includes(q.state.data?.status ?? "") ? 3000 : false,
  });

  const cancel = useMutation({
    mutationFn: () => api.post(`/api/scans/${scanId}/cancel`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scan", scanId] }),
  });
  const del = useMutation({
    mutationFn: () => api.del(`/api/scans/${scanId}`),
    onSuccess: () => nav("/"),
  });

  if (scan.isError) return <Text c="red">Scan not found.</Text>;
  const s = scan.data;
  const running = s && ["queued", "running"].includes(s.status);
  const hasResults =
    s && ["running", "done", "canceled", "failed", "imported"].includes(s.status);

  const report = (format: string, section: string) => {
    window.open(
      `/api/scans/${scanId}/report?format=${format}&section=${section}`,
      "_blank"
    );
  };

  return (
    <>
      <Group justify="space-between" mb="xs">
        <Group>
          <Anchor onClick={() => nav("/")}>← Scans</Anchor>
          <Title order={3}>{s?.name ?? "…"}</Title>
          {s && <StatusBadge status={s.status} />}
        </Group>
        <Group>
          {hasResults && (
            <Menu>
              <Menu.Target>
                <Button variant="default" leftSection={<IconDownload size={16} />}>
                  Export
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item onClick={() => report("html", "summary")}>
                  HTML report (self-contained)
                </Menu.Item>
                <Menu.Item onClick={() => report("json", "secrets")}>JSON — secrets</Menu.Item>
                <Menu.Item onClick={() => report("csv", "high_value_files")}>
                  CSV — high-value files
                </Menu.Item>
                <Menu.Item onClick={() => report("json", "summary")}>JSON — summary</Menu.Item>
              </Menu.Dropdown>
            </Menu>
          )}
          {running && (
            <Button
              color="orange"
              variant="light"
              leftSection={<IconX size={16} />}
              onClick={() => cancel.mutate()}
              loading={cancel.isPending}
            >
              Cancel
            </Button>
          )}
          <Button
            color="red"
            variant="subtle"
            leftSection={<IconTrash size={16} />}
            onClick={() => {
              if (confirm("Delete this scan and all its data?")) del.mutate();
            }}
          >
            Delete
          </Button>
        </Group>
      </Group>

      <Tabs value={active} onChange={(v) => v && nav(`/scans/${scanId}/${v}`)} mb="md">
        <Tabs.List>
          <Tabs.Tab value="overview">Overview</Tabs.Tab>
          <Tabs.Tab value="targets">Targets</Tabs.Tab>
          <Tabs.Tab value="shares">Shares</Tabs.Tab>
          <Tabs.Tab value="files">Files</Tabs.Tab>
          <Tabs.Tab value="stats">Stats</Tabs.Tab>
          <Tabs.Tab value="secrets">Secrets</Tabs.Tab>
          <Tabs.Tab value="search">Search</Tabs.Tab>
          <Tabs.Tab value="review">Review</Tabs.Tab>
          <Tabs.Tab value="log">Log</Tabs.Tab>
        </Tabs.List>
      </Tabs>

      <Routes>
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="overview" element={<Overview scanId={scanId} scan={s} />} />
        <Route path="targets" element={<Targets scanId={scanId} />} />
        <Route path="shares" element={<Shares scanId={scanId} />} />
        <Route path="files" element={<Files scanId={scanId} />} />
        <Route path="stats" element={<Stats scanId={scanId} />} />
        <Route path="secrets" element={<Secrets scanId={scanId} />} />
        <Route path="search" element={<Search scanId={scanId} />} />
        <Route path="review" element={<Review scanId={scanId} />} />
        <Route path="log" element={<Log scanId={scanId} scan={s} />} />
      </Routes>
    </>
  );
}
