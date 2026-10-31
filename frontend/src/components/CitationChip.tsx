import { useState } from "react"
import type { Citation } from "../api"

export function CitationChip({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false)

  return (
    <span>
      <button className="chip" onClick={() => setOpen(!open)} aria-expanded={open}>
        [{citation.number}]
      </button>
      {open && (
        <div className="passage">
          <strong>{citation.doc_name}</strong>, p.{citation.page}
          <p>
            {citation.passage.slice(0, 200)}
            {citation.passage.length > 200 && "…"}
          </p>
        </div>
      )}
    </span>
  )
}
