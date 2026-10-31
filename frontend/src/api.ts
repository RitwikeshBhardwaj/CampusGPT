export interface User {
  id: number
  username: string
  role: 'student' | 'admin'
}

export interface Citation {
  number: number
  doc_name: string
  page: number
  passage: string
}

export interface AnswerResponse {
  answer: string
  citations: Citation[]
  refused: boolean
  warning: string | null
  closest_source: Citation | null
}

export interface Conversation {
  id: number
  title: string | null
  created_at: string
}

export interface Message {
  id: number
  conversation_id: number
  role: 'user' | 'assistant'
  content: string
  citations_json: string | null
  refused: boolean
  created_at: string
}

export interface DocumentMeta {
  id: number
  filename: string
  pages: number
  chunks: number
  uploaded_at: string
}

export interface UploadResponse {
  doc_id: number
  filename: string
  pages: number
  chunks: number
}

async function jsonOrThrow<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`${resp.status}: ${text || resp.statusText}`)
  }
  return resp.json() as Promise<T>
}

export async function fetchMe(): Promise<User | null> {
  const r = await fetch('/api/auth/me', { credentials: 'include' })
  if (r.status === 401) return null
  return jsonOrThrow<User>(r)
}

export async function login(username: string, password: string): Promise<User> {
  const r = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ username, password }),
  })
  return jsonOrThrow<User>(r)
}

export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
}

export interface StreamHandlers {
  onToken: (text: string) => void
  onFinal: (response: AnswerResponse) => void
}

export async function streamChat(
  question: string,
  conversation_id: number | null,
  handlers: StreamHandlers
): Promise<void> {
  const resp = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ question, conversation_id }),
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`${resp.status}: ${await resp.text()}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const line = frame.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      const event = JSON.parse(line.slice('data: '.length))
      if (event.type === 'token') handlers.onToken(event.text)
      if (event.type === 'final') handlers.onFinal(event)
    }
    if (done) break
  }
}

export async function sendChat(
  question: string,
  conversation_id: number | null
): Promise<AnswerResponse> {
  return jsonOrThrow<AnswerResponse>(
    await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ question, conversation_id }),
    })
  )
}

export async function listConversations(): Promise<Conversation[]> {
  return jsonOrThrow<Conversation[]>(
    await fetch('/api/conversations', { credentials: 'include' })
  )
}

export async function createConversation(title?: string): Promise<Conversation> {
  return jsonOrThrow<Conversation>(
    await fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ title }),
    })
  )
}

export async function renameConversation(id: number, title: string): Promise<Conversation> {
  return jsonOrThrow<Conversation>(
    await fetch(`/api/conversations/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ title }),
    })
  )
}

export async function deleteConversation(id: number): Promise<void> {
  await fetch(`/api/conversations/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  })
}

export async function getMessages(id: number): Promise<Message[]> {
  return jsonOrThrow<Message[]>(
    await fetch(`/api/conversations/${id}/messages`, {
      credentials: 'include',
    })
  )
}

export async function listDocuments(): Promise<DocumentMeta[]> {
  return jsonOrThrow<DocumentMeta[]>(
    await fetch('/api/documents', { credentials: 'include' })
  )
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const r = await fetch('/api/documents', {
    method: 'POST',
    credentials: 'include',
    body: form,
  })
  return jsonOrThrow<UploadResponse>(r)
}

export async function deleteDocument(id: number): Promise<void> {
  await fetch(`/api/documents/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  })
}

export async function listUsers(): Promise<User[]> {
  return jsonOrThrow<User[]>(
    await fetch('/api/admin/users', { credentials: 'include' })
  )
}

export async function createUser(
  username: string,
  password: string,
  role: 'student' | 'admin'
): Promise<User> {
  return jsonOrThrow<User>(
    await fetch('/api/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, password, role }),
    })
  )
}

export async function deleteUser(id: number): Promise<void> {
  await fetch(`/api/admin/users/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  })
}