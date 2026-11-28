"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, type UserRecord } from "@/lib/types";
import { deleteResource, patchJson } from "@/lib/client-api";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

import { UserForm } from "@/components/users/user-form";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { FormError } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";

export function UsersView({
  users,
  currentUserId,
}: {
  users: readonly UserRecord[];
  currentUserId: number;
}) {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [deactivating, setDeactivating] = useState<UserRecord | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const activeAdmins = users.filter((user) => user.role === "admin" && user.isActive).length;
  const activeCount = users.filter((user) => user.isActive).length;

  async function toggleRole(user: UserRecord) {
    setActionError(null);
    setBusyId(user.id);
    try {
      await patchJson(`/users/${user.id}`, {
        role: user.role === "admin" ? "user" : "admin",
      });
      router.refresh();
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.detail : "Could not change the role.",
      );
    } finally {
      setBusyId(null);
    }
  }

  async function activate(user: UserRecord) {
    setActionError(null);
    setBusyId(user.id);
    try {
      await patchJson(`/users/${user.id}`, { isActive: true });
      router.refresh();
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.detail : "Could not activate the user.",
      );
    } finally {
      setBusyId(null);
    }
  }

  async function confirmDeactivate() {
    if (!deactivating) return;
    setBusyId(deactivating.id);
    setDeleteError(null);
    try {
      await deleteResource(`/users/${deactivating.id}`);
      setDeactivating(null);
      router.refresh();
    } catch (caught) {
      setDeleteError(
        caught instanceof ApiError ? caught.detail : "Could not deactivate the user.",
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {users.length} account{users.length === 1 ? "" : "s"}, {activeCount} active,{" "}
            {activeAdmins} active administrator{activeAdmins === 1 ? "" : "s"}. Each user sees only
            their own portfolio.
          </p>
        </div>
        <Button variant="primary" onClick={() => setCreating(true)}>
          Add user
        </Button>
      </header>

      <FormError message={actionError} />

      <SectionCard title="Accounts" description="Deactivation keeps the portfolio history">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Login</TableHeaderCell>
              <TableHeaderCell>Role</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Currency</TableHeaderCell>
              <TableHeaderCell>Last login</TableHeaderCell>
              <TableHeaderCell className="text-right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map((user) => {
              const isSelf = user.id === currentUserId;
              const busy = busyId === user.id;
              return (
                <TableRow key={user.id}>
                  <TableCell>
                    <span className="font-medium">{user.login}</span>
                    {isSelf ? (
                      <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        you
                      </span>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-semibold uppercase",
                        user.role === "admin"
                          ? "bg-primary/15 text-primary"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
                      {user.role}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "text-xs font-medium",
                        user.isActive ? "text-positive" : "text-negative",
                      )}
                    >
                      {user.isActive ? "active" : "deactivated"}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{user.baseCurrency}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {user.lastLoginAt ? formatDate(user.lastLoginAt.slice(0, 10)) : "never"}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap justify-end gap-1">
                      <Button
                        size="sm"
                        onClick={() => toggleRole(user)}
                        disabled={busy}
                        title={
                          user.role === "admin"
                            ? "Downgrade to user"
                            : "Grant administrator rights"
                        }
                      >
                        {user.role === "admin" ? "Make user" : "Make admin"}
                      </Button>
                      {user.isActive ? (
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => {
                            setDeleteError(null);
                            setDeactivating(user);
                          }}
                          disabled={busy || isSelf}
                          title={
                            isSelf
                              ? "You cannot deactivate yourself"
                              : "Block sign-in, keep the portfolio"
                          }
                        >
                          Deactivate
                        </Button>
                      ) : (
                        <Button size="sm" onClick={() => activate(user)} disabled={busy}>
                          Activate
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </SectionCard>

      {activeAdmins <= 1 ? (
        <Alert tone="warning" title="Only one active administrator">
          The service always keeps at least one active admin: changing the role or deactivating the
          last one is refused.
        </Alert>
      ) : null}

      <Modal
        open={creating}
        title="New user"
        description="Register the login before the CA issues a certificate for it."
        onClose={() => setCreating(false)}
        className="max-w-xl"
      >
        <UserForm
          onCancel={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            router.refresh();
          }}
        />
      </Modal>

      <Modal
        open={deactivating !== null}
        title={deactivating ? `Deactivate ${deactivating.login}?` : "Deactivate user"}
        description="Sign-in is blocked; the portfolio, trades and history are kept."
        onClose={() => setDeactivating(null)}
        className="max-w-md"
      >
        <div className="space-y-4">
          <FormError message={deleteError} />
          <div className="flex justify-end gap-2">
            <Button onClick={() => setDeactivating(null)} disabled={busyId !== null}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDeactivate} disabled={busyId !== null}>
              {busyId !== null ? "Deactivating…" : "Deactivate user"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
