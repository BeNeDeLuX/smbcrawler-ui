import { useState } from "react";
import {
  Button,
  Group,
  Modal,
  NumberInput,
  PasswordInput,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { IconCloudDownload } from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

// smbcrawler enumerates every file but only auto-downloads the ones a profile
// matches. This pulls one un-downloaded file over SMB after the fact.
export function FetchButton({
  scanId,
  pathId,
  pathLabel,
  onFetched,
  invalidateKeys = [],
}: {
  scanId: string;
  pathId: number;
  pathLabel: string;
  onFetched?: (contentHash: string) => void;
  invalidateKeys?: unknown[][];
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [domain, setDomain] = useState("");
  const [password, setPassword] = useState("");
  const [nthash, setNthash] = useState("");
  const [maxMib, setMaxMib] = useState<number | string>(50);

  const m = useMutation({
    mutationFn: () =>
      api.post<{ content_hash: string; size: number; secrets_found?: number }>(
        `/api/scans/${scanId}/paths/${pathId}/fetch`,
        { username, domain, password, nthash, max_mib: Number(maxMib) }
      ),
    onSuccess: (r) => {
      notifications.show({
        color: "green",
        message: `Fetched ${r.size} B${
          r.secrets_found ? ` · ${r.secrets_found} new secret(s)` : ""
        }`,
      });
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["scan", scanId, "preview", r.content_hash] });
      invalidateKeys.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      onFetched?.(r.content_hash);
    },
    onError: (e: any) =>
      notifications.show({ color: "red", message: String(e.message) }),
  });

  return (
    <>
      <Button
        size="xs"
        variant="light"
        leftSection={<IconCloudDownload size={14} />}
        onClick={() => setOpen(true)}
      >
        Fetch from SMB
      </Button>

      <Modal opened={open} onClose={() => setOpen(false)} title="On-demand SMB fetch" centered>
        <Stack>
          <Text size="sm" c="dimmed" style={{ wordBreak: "break-all" }}>
            {pathLabel}
          </Text>
          <Text size="xs" c="dimmed">
            Scan credentials are deleted after a run — re-enter them to pull this file.
          </Text>
          <Group grow>
            <TextInput label="Username" placeholder="(null session)" value={username} onChange={(e) => setUsername(e.currentTarget.value)} />
            <TextInput label="Domain" value={domain} onChange={(e) => setDomain(e.currentTarget.value)} />
          </Group>
          <Group grow>
            <PasswordInput label="Password" value={password} onChange={(e) => setPassword(e.currentTarget.value)} />
            <TextInput label="NT hash" placeholder="(instead of password)" value={nthash} onChange={(e) => setNthash(e.currentTarget.value)} />
          </Group>
          <NumberInput label="Max size (MiB)" min={1} max={500} value={maxMib} onChange={setMaxMib} />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={() => m.mutate()} loading={m.isPending}>Fetch</Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
