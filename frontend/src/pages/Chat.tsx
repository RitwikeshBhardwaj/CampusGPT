import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../auth"
import * as api from "../api"
import { Message } from "../components/Message"
import { BookOpening } from "../components/BookOpening"

const UNTITLED = "Untitled"

export function Chat() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<api.Conversation[]>([])
  const [messages, setMessages] = useState<api.Message[]>([])
  const [selectedConvId, setSelectedConvId] = useState<number | null>(null)
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [openingBook, setOpeningBook] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [draftTitle, setDraftTitle] = useState("")
  const bottomRef = useRef<HTMLDivElement>(null)
  const nextId = useRef(1)

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
      setOpeningBook(true)
    } catch {
      // ignore
    } finally {
      setCreating(false)
    }
  }

  function startRename(c: api.Conversation) {
    setEditingId(c.id)
    setDraftTitle(c.title ?? "")
  }

  async function commitRename(id: number) {
    const title = draftTitle.trim()
    setEditingId(null)
    if (!title) return
    const previous = conversations
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)))
    try {
      await api.renameConversation(id, title)
    } catch {
      setConversations(previous)
    }
  }

  async function send() {
    const question = input.trim()
    if (!question) return
    setInput("")
    setLoading(true)

    const convId = selectedConvId ?? conversations[0]?.id ?? null

    const userId = nextId.current++
    const assistantId = nextId.current++

    setMessages((prev) => [
      ...prev,
      {
        id: userId, conversation_id: convId ?? 0, role: "user", content: question,
        citations_json: null, refused: false, created_at: new Date().toISOString(),
      },
      {
        id: assistantId, conversation_id: convId ?? 0, role: "assistant",
        content: "", citations_json: null, refused: false,
        created_at: new Date().toISOString(),
      },
    ])

    try {
      await api.streamChat(question, convId, {
        onToken: (text) =>
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + text } : m))
          ),
        onFinal: (resp) =>
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: resp.answer,
                    citations_json: JSON.stringify(resp.citations),
                    refused: resp.refused,
                  }
                : m
            )
          ),
      })
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
    <div className="shell">
      <aside className="sidebar glass">
        <div className="wordmark">CampusGPT</div>
        <button className="primary" onClick={newChat} disabled={creating}>
          {creating ? "Opening…" : "New chat"}
        </button>
        <div className="conv-list">
          {conversations.map((c) =>
            editingId === c.id ? (
              <input
                key={c.id}
                className="rename-input"
                value={draftTitle}
                placeholder={UNTITLED}
                autoFocus
                aria-label="Chat name"
                onChange={(e) => setDraftTitle(e.target.value)}
                onBlur={() => commitRename(c.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") e.currentTarget.blur()
                  if (e.key === "Escape") setEditingId(null)
                }}
              />
            ) : (
              <button
                key={c.id}
                className={
                  "conv" +
                  (c.id === selectedConvId ? " active" : "") +
                  (c.title ? "" : " untitled")
                }
                onClick={() => selectConversation(c.id)}
                onDoubleClick={() => startRename(c)}
                title="Double-click to rename"
              >
                {c.title ?? UNTITLED}
              </button>
            )
          )}
        </div>
        <div className="sidebar-footer">
          {user?.role === "admin" && (
            <button className="quiet" onClick={() => navigate("/admin")}>Admin panel</button>
          )}
          <button className="quiet" onClick={logout}>Log out</button>
        </div>
      </aside>

      <main className="stage">
        {openingBook && <BookOpening onDone={() => setOpeningBook(false)} />}
        <div className="transcript">
          {messages.length === 0 && !openingBook && (
            <p className="empty-hint">Ask something about the university.</p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={"row " + m.role}>
              <Message message={m} />
            </div>
          ))}
          <div ref={bottomRef} />
          {loading && <p className="thinking">Thinking…</p>}
        </div>
        <div className="composer glass">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask a question…"
            aria-label="Question"
          />
          <button className="primary" onClick={send} disabled={loading}>Send</button>
        </div>
      </main>
    </div>
  )
}
