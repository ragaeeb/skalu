import { useRef } from 'react';

type DropZoneProps = { onFile: (file: File) => Promise<void>; disabled: boolean };

export const DropZone = ({ onFile, disabled }: DropZoneProps) => {
    const inputRef = useRef<HTMLInputElement | null>(null);

    const onChange = async (event: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
        const file = event.target.files?.[0];
        if (file) {
            await onFile(file);
        }
    };

    return (
        <div className="panel" data-testid="drop-zone">
            <h2
                style={{ color: '#1e293b', fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem', marginTop: 0 }}
            >
                Upload a PDF or image
            </h2>
            <p style={{ color: '#64748b', fontSize: '0.9375rem', marginBottom: '1rem', marginTop: 0 }}>
                Accepted formats: PDF, PNG, JPG, JPEG, BMP, TIFF, WEBP
            </p>
            <div style={{ alignItems: 'center', display: 'flex', gap: '0.75rem' }}>
                <button className="button" type="button" onClick={() => inputRef.current?.click()} disabled={disabled}>
                    Choose File
                </button>
                <input
                    ref={inputRef}
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.bmp,.tiff,.webp,image/png,image/jpeg,image/bmp,image/tiff,image/webp,application/pdf"
                    onChange={(event) => void onChange(event)}
                    disabled={disabled}
                    hidden
                />
            </div>
        </div>
    );
};
