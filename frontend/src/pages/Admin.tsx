import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../auth"
import * as api from "../api"

export function Admin() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState<"documents" | "users">("documents")
  const [docs, setDocs] = useState<api.DocumentMeta[]>([])
  const [users, setUsers] = useState<api.User[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const [newUser, setNewUser] = useState({ username: "", password: "", role: "student" as "student" | "admin" })

  useEffect(() => {
    refresh()
  }, [])

  async function refresh() {
    try {
      const d = await api.listDocuments()
      setDocs(d)
    } catch {
      // ignore
    }
    try {
      const u = await api.listUsers()
      setUsers(u)
    } catch {
      // ignore
    }
  }

  async function handleCreateUser() {
    try {
      await api.createUser(newUser.username, newUser.password, newUser.role)
      setNewUser({ username: "", password: "", role: "student" })
      await refresh()
    } catch {
      // ignore
    }
  }

  if (user?.role !== "admin") {
    return (
      <div className="denied">
        <p>Admin access required.</p>
        <button onClick={logout}>Log out</button>
      </div>
    )
  }

  return (
    <div className="admin">
      <div className="admin-bar">
        <h1 className="wordmark">Admin</h1>
        <span className="spacer" />
        <button className="quiet" onClick={() => navigate("/")}>Back to chat</button>
        <button className="quiet" onClick={logout}>Log out</button>
      </div>
      <div className="admin-bar">
        <button className={tab === "documents" ? "primary" : ""} onClick={() => setTab("documents")}>
          Documents
        </button>
        <button className={tab === "users" ? "primary" : ""} onClick={() => setTab("users")}>
          Users
        </button>
      </div>

      {tab === "documents" && (
        <section className="panel glass">
          <h2>Documents</h2>
          <div className="upload-row">
            <button
              className="upload-picker"
              type="button"
              disabled={uploading}
              onClick={() => fileInput.current?.click()}
            >
              {uploading ? "Uploading…" : "Choose file"}
            </button>
            <input
              ref={fileInput}
              className="upload-input"
              type="file"
              accept=".pdf,.docx,.txt"
              aria-label="Choose a document to upload"
              disabled={uploading}
              onChange={async (e) => {
                const input = e.currentTarget
                const file = input.files?.[0]
                if (!file) return

                setUploading(true)
                setUploadError(null)

                try {
                  await api.uploadDocument(file)
                  await refresh()
                } catch (error) {
                  const message = error instanceof Error ? error.message : "Upload failed"
                  setUploadError(message)
                } finally {
                  setUploading(false)
                  input.value = ""
                }
              }}
            />
          </div>
          {uploadError && <p className="form-error">{uploadError}</p>}
          <ul className="record-list">
            {docs.map((d) => (
              <li key={d.id}>
                <span>{d.filename} — {d.pages} pages, {d.chunks} chunks</span>
                <button className="quiet" onClick={async () => { await api.deleteDocument(d.id); await refresh() }}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "users" && (
        <section className="panel glass">
          <h2>Users</h2>
          <div className="create-row">
            <input placeholder="username" aria-label="New username" value={newUser.username}
              onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} />
            <input placeholder="password" aria-label="New password" type="password" value={newUser.password}
              onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} />
            <select value={newUser.role} aria-label="Role"
              onChange={(e) => setNewUser({ ...newUser, role: e.target.value as "student" | "admin" })}>
              <option value="student">student</option>
              <option value="admin">admin</option>
            </select>
            <button className="primary" onClick={handleCreateUser}>Create user</button>
          </div>
          <ul className="record-list">
            {users.map((u) => (
              <li key={u.id}>
                <span>{u.username} — {u.role}</span>
                <button className="quiet" onClick={async () => { await api.deleteUser(u.id); await refresh() }}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
