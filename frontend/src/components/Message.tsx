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
    <div className={isRefusal ? "bubble refusal" : "bubble"}>
      <p>{message.content}</p>
      {citations.length > 0 && (
        <div className="citations">
          {citations.map((c) => (
            <CitationChip key={c.number} citation={c} />
          ))}
        </div>
      )}
      {isRefusal && citations[0] && (
        <div className="closest">
          Closest source: <CitationChip citation={citations[0]} />
        </div>
      )}
    </div>
  )
}
