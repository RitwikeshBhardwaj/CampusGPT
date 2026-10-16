import { useState } from "react"
import type { Citation } from "../api"

export function CitationChip({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <span
        style={{ cursor: "pointer", textDecoration: "underline", color: "blue" }}
        onClick={() => setOpen(!open)}
      >
        [{citation.number}]
      </span>
      {open && (
        <div style={{
          border: "1px solid #ccc",
          borderRadius: 4,
          padding: 8,
          marginTop: 4,
          background: "#f9f9f9",
        }}>
          <strong>{citation.doc_name}</strong>, p.{citation.page}
          <p style={{ margin: "4px 0 0", fontStyle: "italic" }}>
            {citation.passage.slice(0, 200)}
            {citation.passage.length > 200 && "…"}
          </p>
        </div>
      )}
    </>
  )
}
