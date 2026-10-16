import type { Citation } from "../api"
import { CitationChip } from "./CitationChip"

interface MessageProps {
  message: {
    id: number
    conversation_id: number
    role: "user" | "assistant"
    content: string
    citations_json: string | null
    refused: boolean
    created_at: string
  }
}

export function Message({ message }: MessageProps) {
  const isRefusal = message.refused

  let citations: Citation[] = []
  try {
    citations = message.citations_json ? JSON.parse(message.citations_json) : []
  } catch {
    citations = []
  }

  return (
    <div style={{
      padding: 8,
      borderRadius: 6,
      background: isRefusal ? "#fff8e1" : undefined,
      border: isRefusal ? "1px solid #ffcc02" : undefined,
      marginBottom: 8,
    }}>
      <p style={{ whiteSpace: "pre-wrap" }}>{message.content}</p>
      {citations.length > 0 && (
        <div style={{ marginTop: 4 }}>
          {citations.map((c) => (
            <CitationChip key={c.number} citation={c} />
          ))}
        </div>
      )}
      {isRefusal && message.citations_json && (
        <div style={{ marginTop: 6, fontSize: 13, color: "#555" }}>
          Closest source:{" "}
          <CitationChip citation={citations[0]} />
        </div>
      )}
    </div>
  )
}
