import { useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  FileInput,
  Group,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconAlertTriangle, IconShieldLock } from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, TlsCertificate } from "../api";

export function Settings() {
  const qc = useQueryClient();
  const [cert, setCert] = useState<File | null>(null);
  const [key, setKey] = useState<File | null>(null);

  const q = useQuery({
    queryKey: ["tls-certificate"],
    queryFn: () => api.get<TlsCertificate>("/api/tls/certificate"),
  });

  const upload = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.append("cert", cert as File);
      fd.append("key", key as File);
      return api.postForm<TlsCertificate>("/api/tls/certificate", fd);
    },
    onSuccess: () => {
      notifications.show({ color: "green", message: "Certificate installed — the proxy reloads within a few seconds." });
      setCert(null);
      setKey(null);
      qc.invalidateQueries({ queryKey: ["tls-certificate"] });
    },
    onError: (e: any) => notifications.show({ color: "red", message: String(e.message) }),
  });

  const reset = useMutation({
    mutationFn: () => api.del<TlsCertificate>("/api/tls/certificate"),
    onSuccess: () => {
      notifications.show({ color: "green", message: "Reverted to the self-signed certificate." });
      qc.invalidateQueries({ queryKey: ["tls-certificate"] });
    },
    onError: (e: any) => notifications.show({ color: "red", message: String(e.message) }),
  });

  const c = q.data;

  return (
    <Stack maw={700}>
      <Title order={3}>Settings</Title>

      <Card withBorder>
        <Group mb="sm">
          <IconShieldLock size={18} />
          <Title order={5}>TLS certificate</Title>
        </Group>

        {!c?.present && (
          <Alert color="yellow" icon={<IconAlertTriangle size={16} />}>
            No certificate reported yet — the <code>proxy</code> container generates a
            self-signed one on first boot. If this persists, check that it's running.
          </Alert>
        )}

        {c?.present && (
          <>
            <Group mb="sm">
              <Badge color={c.source === "custom" ? "grape" : "blue"} variant="light">
                {c.source}
              </Badge>
            </Group>
            <Table>
              <Table.Tbody>
                <Table.Tr>
                  <Table.Th w={140}>Subject</Table.Th>
                  <Table.Td style={{ wordBreak: "break-all" }}>{c.subject}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Th>Issuer</Table.Th>
                  <Table.Td style={{ wordBreak: "break-all" }}>{c.issuer}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Th>Valid</Table.Th>
                  <Table.Td>
                    {c.not_before?.slice(0, 10)} – {c.not_after?.slice(0, 10)}
                  </Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Th>SHA-256</Table.Th>
                  <Table.Td>
                    <Text ff="monospace" size="xs" style={{ wordBreak: "break-all" }}>
                      {c.fingerprint_sha256}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              </Table.Tbody>
            </Table>
          </>
        )}

        <Title order={6} mt="lg" mb="xs">
          Upload a custom certificate
        </Title>
        <Text size="sm" c="dimmed" mb="sm">
          PEM certificate (leaf, optionally with the chain appended) + an unencrypted PEM
          private key. Applied live within a few seconds — no restart.
        </Text>
        <Group grow mb="sm">
          <FileInput label="Certificate (.crt/.pem)" placeholder="cert.pem" value={cert} onChange={setCert} accept=".pem,.crt,.cer" />
          <FileInput label="Private key (.key/.pem)" placeholder="key.pem" value={key} onChange={setKey} accept=".pem,.key" />
        </Group>
        <Group justify="space-between">
          <Button
            variant="default"
            color="red"
            onClick={() => reset.mutate()}
            loading={reset.isPending}
            disabled={c?.source !== "custom"}
          >
            Reset to self-signed
          </Button>
          <Button onClick={() => upload.mutate()} loading={upload.isPending} disabled={!cert || !key}>
            Upload
          </Button>
        </Group>
      </Card>
    </Stack>
  );
}
