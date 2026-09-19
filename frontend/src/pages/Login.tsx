import { useEffect, useState } from "react";
import { Button, Card, Center, PasswordInput, Stack, Title } from "@mantine/core";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { ApiError } from "../api";

export function LoginPage() {
  const { login, authed } = useAuth();
  const nav = useNavigate();
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (authed) nav("/", { replace: true });
  }, [authed, nav]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await login(pw);
      nav("/", { replace: true });
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Center h="100vh">
      <Card withBorder shadow="sm" w={360} p="lg">
        <form onSubmit={submit}>
          <Stack>
            <Title order={3}>smbcrawler UI</Title>
            <PasswordInput
              label="Password"
              value={pw}
              onChange={(e) => setPw(e.currentTarget.value)}
              error={err}
              autoFocus
            />
            <Button type="submit" loading={busy}>
              Sign in
            </Button>
          </Stack>
        </form>
      </Card>
    </Center>
  );
}
