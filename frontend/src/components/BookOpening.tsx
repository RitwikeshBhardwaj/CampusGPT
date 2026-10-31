/** A book that opens and turns its pages, played once when a chat is created. */
export function BookOpening({ onDone }: { onDone: () => void }) {
  return (
    <div className="book-stage" onAnimationEnd={(e) => { if (e.target === e.currentTarget) onDone() }}>
      <div className="book" aria-hidden="true">
        <div className="cover"><span>CampusGPT</span></div>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="page" style={{ ["--i" as string]: i }} />
        ))}
      </div>
    </div>
  )
}
