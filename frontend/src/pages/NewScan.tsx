import { useState } from "react";
import {
  Accordion,
  Button,
  Checkbox,
  Code,
  Group,
  NumberInput,
  Paper,
  ScrollArea,
  Stack,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, Scan } from "../api";

export function NewScan() {
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [targets, setTargets] = useState("");
  const [username, setUsername] = useState("");
  const [domain, setDomain] = useState("");
  const [password, setPassword] = useState("");
  const [nthash, setNthash] = useState("");
  const [threads, setThreads] = useState<number | string>(10);
  const [depth, setDepth] = useState<number | string>(1);
  const [timeout, setTimeoutV] = useState<number | string>(5);
  const [checkWrite, setCheckWrite] = useState(false);
  const [noDownload, setNoDownload] = useState(false);
  const [profileYaml, setProfileYaml] = useState("");
  const [dry, setDry] = useState<any>(null);

  const targetList = () =>
    targets
      .split(/[\s,]+/)
      .map((t) => t.trim())
      .filter(Boolean);

  const dryRun = useMutation({
    mutationFn: () =>
      api.post<any>("/api/scans/dry-run", {
        targets: targetList(),
        extra_profile_yaml: profileYaml || null,
      }),
    onSuccess: setDry,
    onError: (e: any) => notifications.show({ color: "red", message: String(e.message) }),
  });

  const create = useMutation({
    mutationFn: () =>
      api.post<Scan>("/api/scans", {
        name,
        targets: targetList(),
        credentials: {
          username: username || " ",
          domain: domain || ".",
          password,
          nthash,
        },
        options: {
          threads: Number(threads),
          depth: Number(depth),
          timeout: Number(timeout),
          check_write_access: checkWrite,
          disable_autodownload: noDownload,
        },
        extra_profile_yaml: profileYaml || null,
      }),
    onSuccess: (s) => nav(`/scans/${s.id}`),
    onError: (e: any) => notifications.show({ color: "red", message: String(e.message) }),
  });

  return (
    <Stack maw={780}>
      <Title order={3}>New scan</Title>

      <TextInput label="Scan name" value={name} onChange={(e) => setName(e.currentTarget.value)} required />
      <Textarea
        label="Targets"
        description="Hostnames, IPs or CIDR ranges — one per line, or comma/space separated. Optional :port."
        minRows={4}
        autosize
        value={targets}
        onChange={(e) => setTargets(e.currentTarget.value)}
      />

      <Group grow>
        <TextInput label="Username" placeholder="(guest)" value={username} onChange={(e) => setUsername(e.currentTarget.value)} />
        <TextInput label="Domain" placeholder="." value={domain} onChange={(e) => setDomain(e.currentTarget.value)} />
      </Group>
      <Group grow>
        <TextInput label="Password" type="password" value={password} onChange={(e) => setPassword(e.currentTarget.value)} />
        <TextInput label="NT hash" placeholder="(instead of password)" value={nthash} onChange={(e) => setNthash(e.currentTarget.value)} />
      </Group>

      <Group grow>
        <NumberInput label="Threads" min={1} max={64} value={threads} onChange={setThreads} />
        <NumberInput label="Depth" description="-1 = unlimited" min={-1} max={64} value={depth} onChange={setDepth} />
        <NumberInput label="Timeout (s)" min={1} max={120} value={timeout} onChange={setTimeoutV} />
      </Group>
      <Group>
        <Checkbox label="Check write access (creates a temp dir per share)" checked={checkWrite} onChange={(e) => setCheckWrite(e.currentTarget.checked)} />
        <Checkbox label="Disable auto-download" checked={noDownload} onChange={(e) => setNoDownload(e.currentTarget.checked)} />
      </Group>

      <Accordion variant="separated">
        <Accordion.Item value="profile">
          <Accordion.Control>Profile override (YAML, optional)</Accordion.Control>
          <Accordion.Panel>
            <Textarea
              minRows={6}
              autosize
              placeholder={"files:\n  my_rule:\n    regex: '.*\\.kdbx$'\n    high_value: true"}
              value={profileYaml}
              onChange={(e) => setProfileYaml(e.currentTarget.value)}
              styles={{ input: { fontFamily: "monospace" } }}
            />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      <Group>
        <Button variant="default" onClick={() => dryRun.mutate()} loading={dryRun.isPending}>
          Dry run
        </Button>
        <Button onClick={() => create.mutate()} loading={create.isPending} disabled={!name || targetList().length === 0}>
          Start scan
        </Button>
      </Group>

      {dry && (
        <Paper withBorder p="sm">
          <Title order={5} mb="xs">
            Effective targets ({dry.targets?.length ?? 0})
          </Title>
          <Code block>{(dry.targets ?? []).join("\n")}</Code>
          <Title order={5} mt="md" mb="xs">
            Effective profiles
          </Title>
          <ScrollArea.Autosize mah={320}>
            <Code block>{JSON.stringify(dry.profiles, null, 2)}</Code>
          </ScrollArea.Autosize>
        </Paper>
      )}
    </Stack>
  );
}
