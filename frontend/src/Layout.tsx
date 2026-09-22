import { AppShell, Button, Group, Title } from "@mantine/core";
import { IconApi, IconLogout, IconSettings } from "@tabler/icons-react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "./auth";

export function Layout() {
  const { logout } = useAuth();
  const nav = useNavigate();
  return (
    <AppShell header={{ height: 56 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Title order={4} component={Link} to="/" style={{ textDecoration: "none" }}>
              smbcrawler UI
            </Title>
          </Group>
          <Group gap="xs">
            <Button
              variant="subtle"
              size="xs"
              component={Link}
              to="/settings"
              leftSection={<IconSettings size={16} />}
            >
              Settings
            </Button>
            <Button
              variant="subtle"
              size="xs"
              component="a"
              href="/docs"
              target="_blank"
              leftSection={<IconApi size={16} />}
            >
              API
            </Button>
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconLogout size={16} />}
              onClick={async () => {
                await logout();
                nav("/login");
              }}
            >
              Logout
            </Button>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
