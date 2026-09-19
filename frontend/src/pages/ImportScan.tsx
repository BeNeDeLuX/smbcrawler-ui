import { useState } from "react";
import { Button, FileInput, Stack, Text, TextInput, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, Scan } from "../api";

export function ImportScan() {
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [crawl, setCrawl] = useState<File | null>(null);
  const [content, setContent] = useState<File | null>(null);

  const m = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.append("name", name);
      fd.append("crawl", crawl as File);
      if (content) fd.append("content", content);
      return api.postForm<Scan>("/api/imports", fd);
    },
    onSuccess: (s) => nav(`/scans/${s.id}`),
    onError: (e: any) => notifications.show({ color: "red", message: String(e.message) }),
  });

  return (
    <Stack maw={560}>
      <Title order={3}>Import a .crwl database</Title>
      <TextInput label="Name" value={name} onChange={(e) => setName(e.currentTarget.value)} required />
      <FileInput
        label="output.crwl (SQLite database)"
        placeholder="Pick file"
        value={crawl}
        onChange={setCrawl}
        accept=".crwl,.sqlite,.db"
        required
      />
      <FileInput
        label="Content archive (optional)"
        description="A tar of the contents of <crawl>.d (so it contains content/ and tree/). Enables file preview & search."
        placeholder="Pick tar file"
        value={content}
        onChange={setContent}
        accept=".tar,.tar.gz,.tgz"
      />
      <Text size="sm" c="dimmed">
        Create it with: <code>tar -C output.crwl.d -cf content.tar .</code>
      </Text>
      <Button onClick={() => m.mutate()} loading={m.isPending} disabled={!name || !crawl}>
        Import
      </Button>
    </Stack>
  );
}
