import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../auth"
import * as api from "../api"
import { Message } from "../components/Message"

export function Chat() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<api.Conversation[]>([])
  const [messages, setMessages] = useState<api.Message[]>([])
  const [selectedConvId, setSelectedConvId] = useState<number | null>(null)
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listConversations()
  }, [])

  async function listConversations() {
    try {
      const convs = await api.listConversations()
      setConversations(convs)
    } catch {
      // ignore
    }
  }

  async function selectConversation(id: number) {
    setSelectedConvId(id)
    try {
      const msgs = await api.getMessages(id)
      setMessages(msgs)
    } catch {
      // ignore
    }
  }

  async function newChat() {
    setCreating(true)
    try {
      const conv = await api.createConversation()
      setConversations((prev) => [...prev, conv])
      setSelectedConvId(conv.id)
      setMessages([])
    } catch {
      // ignore
    } finally {
      setCreating(false)
    }
  }

  async function send() {
    const question = input.trim()
    if (!question) return
    setInput("")
    setLoading(true)

    const convId = selectedConvId ?? conversations[0]?.id ?? null

    // Optimistically add user message
    setMessages((prev) => [...prev, {
      id: 0, conversation_id: convId ?? 0, role: "user", content: question,
      citations_json: null, refused: false, created_at: new Date().toISOString(),
    }])

    try {
      const resp = await api.sendChat(question, convId)
      setMessages((prev) => [
        ...prev,
        {
          id: prev.length + 1, conversation_id: convId ?? 0, role: "assistant",
          content: resp.answer, citations_json: JSON.stringify(resp.citations),
          refused: resp.refused, created_at: new Date().toISOString(),
        },
      ])
      if (!selectedConvId) {
        // New conversation created — update the list and select it
        await listConversations()
        // The new conv is the last one in the list
        setConversations((prev) => {
          const last = prev[prev.length - 1]
          if (last) setSelectedConvId(last.id)
          return prev
        })
      }
    } finally {
      setLoading(false)
      bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }
  }

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      {/* Sidebar */}
      <div style={{ width: 220, borderRight: "1px solid #ddd", padding: 8, overflowY: "auto" }}>
        <button onClick={newChat} disabled={creating} style={{ width: "100%", marginBottom: 8 }}>
          {creating ? "Creating…" : "New Chat"}
        </button>
        {conversations.map((c) => (
          <div
            key={c.id}
            onClick={() => selectConversation(c.id)}
            style={{ padding: 4, cursor: "pointer", borderBottom: "1px solid #eee" }}
          >
            {c.title ?? "Untitled"}
          </div>
        ))}
        <button onClick={logout} style={{ marginTop: 16, width: "100%" }}>
          Logout
        </button>
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
          {messages.map((m, i) => (
            <div key={i} style={{
              textAlign: m.role === "user" ? "right" : "left",
              padding: "0 8px",
            }}>
              <Message message={m} />
            </div>
          ))}
          <div ref={bottomRef} />
          {loading && <p>Thinking…</p>}
        </div>
        <div style={{ padding: 8, borderTop: "1px solid #ddd", display: "flex", gap: 8 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask a question…"
            style={{ flex: 1 }}
          />
          <button onClick={send} disabled={loading}>Send</button>
        </div>
      </div>
    </div>
  )
}
