import type { CSSProperties } from "react"

interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description?: string
  disabled?: boolean
}

/** Accessible on/off switch: a labelled button with role="switch". */
export default function Switch({ checked, onChange, label, description, disabled }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      style={{ ...row, opacity: disabled ? 0.55 : 1, cursor: disabled ? "not-allowed" : "pointer" }}
    >
      <span style={text}>
        <span style={labelStyle}>{label}</span>
        {description && <span style={descriptionStyle}>{description}</span>}
      </span>
      <span style={{ ...track, background: checked ? "#1f6feb" : "#30363d" }} aria-hidden>
        <span style={{ ...thumb, transform: checked ? "translateX(14px)" : "translateX(0)" }} />
      </span>
    </button>
  )
}

const row: CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
  width: "100%", padding: "8px 10px", background: "#0d1117",
  border: "1px solid #21262d", borderRadius: 6, textAlign: "left",
  font: "inherit", color: "inherit",
}
const text: CSSProperties = { display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }
const labelStyle: CSSProperties = { fontSize: 12, fontWeight: 600, color: "#e6edf3" }
const descriptionStyle: CSSProperties = {
  fontSize: 10.5, color: "#8b949e", lineHeight: 1.4,
  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
}
const track: CSSProperties = {
  position: "relative", flexShrink: 0, width: 30, height: 16, borderRadius: 8,
  transition: "background 150ms ease",
}
const thumb: CSSProperties = {
  position: "absolute", top: 2, left: 2, width: 12, height: 12, borderRadius: "50%",
  background: "#ffffff", transition: "transform 150ms ease",
}
