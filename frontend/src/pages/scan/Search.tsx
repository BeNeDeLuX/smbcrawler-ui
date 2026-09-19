import { useState } from "react";
import { Alert, Card, Code, Grid, Group, ScrollArea, Stack, Text, TextInput } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { api, SearchHit } from "../../api";
import { PreviewPane } from "../../components/PreviewPane";

export function Search({ scanId }: { scanId: string }) {
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<SearchHit | null>(null);

  const res = useQuery({
    queryKey: ["scan", scanId, "search", q],
    enabled: q.length > 0,
    queryFn: () =>
      api.get<{ total: number; items: SearchHit[]; indexed: boolean; error?: string }>(
        `/api/scans/${scanId}/search?q=${encodeURIComponent(q)}`
      ),
  });

  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 6 }}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setQ(input.trim());
          }}
        >
          <TextInput
            placeholder="full-text query (FTS5 syntax) — e.g.  password OR cpassword"
            value={input}
            onChange={(e) => setInput(e.currentTarget.value)}
          />
        </form>

        {res.data && !res.data.indexed && <Alert mt="sm" color="yellow">No search index yet for this scan.</Alert>}
        {res.data?.error && <Alert mt="sm" color="red">{res.data.error}</Alert>}
        {res.data && <Text mt="xs" size="sm" c="dimmed">{res.data.total} matches</Text>}

        <ScrollArea h="calc(100vh - 320px)" mt="xs">
          <Stack gap="xs">
            {(res.data?.items ?? []).map((h, i) => (
              <Card
                key={i}
                withBorder
                p="xs"
                onClick={() => setSel(h)}
                style={{ cursor: "pointer", borderColor: sel === h ? "var(--mantine-color-blue-6)" : undefined }}
              >
                <Text size="xs" c="dimmed" style={{ wordBreak: "break-all" }}>
                  {`\\\\${h.target}\\${h.share}\\${h.path}`}
                </Text>
                <Code block style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>
                  {h.snippet}
                </Code>
              </Card>
            ))}
          </Stack>
        </ScrollArea>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <PreviewPane
          scanId={scanId}
          target={sel ? { path: `\\\\${sel.target}\\${sel.share}\\${sel.path}`, content_hash: sel.content_hash } : null}
        />
      </Grid.Col>
    </Grid>
  );
}
