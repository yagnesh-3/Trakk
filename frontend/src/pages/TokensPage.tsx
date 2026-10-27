import { useEffect, useState, type FormEvent } from "react";
import { api } from "../lib/api";
import { formatDate, formatDateTime } from "../lib/format";
import type { ApiToken, ApiTokenCreated } from "../lib/types";
import { CopyField } from "./UsersPage";

export default function TokensPage() {
  const [tokens, setTokens] = useState<ApiToken[] | null>(null);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<ApiTokenCreated | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.tokens().then(setTokens).catch((err: Error) => setError(err.message));
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const token = await api.createToken(name.trim());
      setCreated(token);
      setTokens((prev) => [...(prev ?? []), token]);
      setName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create token");
    }
  }

  async function revoke(token: ApiToken) {
    if (!window.confirm(`Revoke "${token.name}"? Anything using it will stop working immediately.`)) return;
    try {
      await api.deleteToken(token.id);
      setTokens((prev) => prev?.filter((t) => t.id !== token.id) ?? null);
      if (created?.id === token.id) setCreated(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not revoke token");
    }
  }

  const origin = (import.meta.env.VITE_API_URL as string | undefined) || window.location.origin;

  return (
    <main className="page narrow-page">
      <div className="page-header">
        <h1>API tokens</h1>
      </div>
      <p className="muted">
        Tokens let scripts and tools such as Claude use the tracker as you, with your project access. Treat them like
        passwords. A token can't create other tokens.
      </p>

      <form className="panel inline-form token-form" onSubmit={create}>
        <input
          placeholder="Token name, e.g. Claude on my laptop"
          value={name}
          maxLength={100}
          onChange={(e) => setName(e.target.value)}
          required
          aria-label="Token name"
        />
        <button className="btn btn-primary">Create token</button>
      </form>

      {created && (
        <div className="callout" role="status">
          <div>
            <strong>Copy your new token now</strong>
            <p className="muted">It won't be shown again; only a fingerprint is stored.</p>
            <CopyField value={created.token} />
            <p className="muted small">Example request:</p>
            <pre className="code-block">{`curl -H "Authorization: Bearer ${created.token}" \\\n  ${origin}/api/projects`}</pre>
          </div>
          <button className="icon-button" aria-label="Dismiss" onClick={() => setCreated(null)}>
            ✕
          </button>
        </div>
      )}
      {error && <div className="form-error">{error}</div>}

      {tokens === null ? (
        <p className="muted">Loading…</p>
      ) : tokens.length === 0 ? (
        <p className="muted">You have no tokens.</p>
      ) : (
        <div className="table-wrap panel flush">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Token</th>
                <th>Created</th>
                <th>Last used</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {tokens.map((t) => (
                <tr key={t.id}>
                  <td>{t.name}</td>
                  <td>
                    <code>{t.prefix}…</code>
                  </td>
                  <td className="muted nowrap">{formatDate(t.createdAt)}</td>
                  <td className="muted nowrap">{t.lastUsedAt ? formatDateTime(t.lastUsedAt) : "Never"}</td>
                  <td className="cell-actions">
                    <button className="btn btn-ghost btn-sm danger" onClick={() => void revoke(t)}>
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
