"use client";

import { useState, type FormEvent } from "react";

import { ApiError, type UserRole } from "@/lib/types";
import { postJson } from "@/lib/client-api";

import { Button } from "@/components/ui/button";
import { Field, FormError, Input, Select } from "@/components/ui/field";

export function UserForm({
  onSaved,
  onCancel,
}: {
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [login, setLogin] = useState("");
  const [role, setRole] = useState<UserRole>("user");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const trimmed = login.trim();
    if (!trimmed) {
      setError("Login is required: it must match the Common Name of the client certificate.");
      return;
    }

    setSaving(true);
    try {
      await postJson("/users", { login: trimmed, role });
      onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Could not create the user.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormError message={error} />

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Login"
          htmlFor="user-login"
          hint="The Common Name of the client certificate issued by the CA."
        >
          <Input
            id="user-login"
            value={login}
            onChange={(event) => setLogin(event.target.value)}
            maxLength={128}
            placeholder="ivan.petrov"
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
          />
        </Field>
        <Field
          label="Role"
          htmlFor="user-role"
          hint="Admins manage users and still see only their own portfolio."
        >
          <Select
            id="user-role"
            value={role}
            onChange={(event) => setRole(event.target.value as UserRole)}
          >
            <option value="user">user</option>
            <option value="admin">admin</option>
          </Select>
        </Field>
      </div>

      <p className="text-xs text-muted-foreground">
        Eign does not create certificates: register the login first, then have the CA issue a
        certificate with that Common Name.
      </p>

      <div className="flex justify-end gap-2">
        <Button onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={saving}>
          {saving ? "Creating…" : "Create user"}
        </Button>
      </div>
    </form>
  );
}
