import { useRef } from "react"

type DropZoneProps = {
  onFile: (file: File) => Promise<void>
  disabled: boolean
}

export const DropZone = ({ onFile, disabled }: DropZoneProps) => {
  const inputRef = useRef<HTMLInputElement | null>(null)

  const onChange = async (event: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
    const file = event.target.files?.[0]
    if (file) {
      await onFile(file)
    }
  }

  return (
    <div className="panel" data-testid="drop-zone">
      <h2 style={{ marginTop: 0, marginBottom: "0.5rem", fontSize: "1.25rem", fontWeight: 600, color: "#1e293b" }}>Upload a PDF or image</h2>
      <p style={{ marginTop: 0, marginBottom: "1rem", color: "#64748b", fontSize: "0.9375rem" }}>Accepted formats: PDF, PNG, JPG, JPEG, BMP, TIFF, WEBP</p>
      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <button className="button" type="button" onClick={() => inputRef.current?.click()} disabled={disabled}>
          Choose File
        </button>
        <input ref={inputRef} type="file" onChange={(event) => void onChange(event)} disabled={disabled} hidden />
      </div>
    </div>
  )
}
