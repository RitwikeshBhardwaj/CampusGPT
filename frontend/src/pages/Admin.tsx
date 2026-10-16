import { useState, useEffect } from "react"
import { useAuth } from "../auth"
import * as api from "../api"

export function Admin() {
  const { user, logout } = useAuth()
  const [tab, setTab] = useState<"documents" | "users">("documents")
  const [docs, setDocs] = useState<api.DocumentMeta[]>([])
  const [users, setUsers] = useState<api.User[]>([])
  const [newUser, setNewUser] = useState({ username: "", password: "", role: "student" as const })

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
    return <div style={{ padding: 16 }}><p>Admin access required.</p><button onClick={logout}>Logout</button></div>
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>Admin</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button onClick={() => setTab("documents")}>Documents</button>
        <button onClick={() => setTab("users")}>Users</button>
        <button onClick={logout} style={{ marginLeft: "auto" }}>Logout</button>
      </div>

      {tab === "documents" && (
        <>
          <h2>Upload</h2>
          <input type="file" accept=".pdf" onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) return
            try {
              await api.uploadDocument(file)
              await refresh()
            } catch {
              alert("Upload failed")
            }
            e.target.value = ""
          }} />
          <h3>Documents</h3>
          <ul>
            {docs.map((d) => (
              <li key={d.id}>
                {d.filename} ({d.pages} pages, {d.chunks} chunks)
                <button onClick={async () => { await api.deleteDocument(d.id); await refresh() }}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {tab === "users" && (
        <>
          <h2>Create User</h2>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <input placeholder="username" value={newUser.username}
              onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} />
            <input placeholder="password" type="password" value={newUser.password}
              onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} />
            <select value={newUser.role}
              onChange={(e) => setNewUser({ ...newUser, role: e.target.value as "student" | "admin" })}>
              <option value="student">student</option>
              <option value="admin">admin</option>
            </select>
            <button onClick={handleCreateUser}>Create</button>
          </div>
          <h3>Users</h3>
          <ul>
            {users.map((u) => (
              <li key={u.id}>
                {u.username} ({u.role})
                <button onClick={async () => { await api.deleteUser(u.id); await refresh() }}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
