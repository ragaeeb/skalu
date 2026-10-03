import { useEffect, useState } from 'react';
import { api, post } from './client';

export const ApiKey = () => {
    const [prefix, setPrefix] = useState<string | null>(null);
    const [key, setKey] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    useEffect(() => {
        void api<{ prefix: string } | null>('/api/key')
            .then((value) => setPrefix(value?.prefix ?? null))
            .catch((error) => setError(String(error)));
    }, []);
    const issue = async () => {
        setBusy(true);
        setError('');
        try {
            const result = await post<{ key: string; prefix: string }>(prefix ? '/api/key/rotate' : '/api/key');
            setKey(result.key);
            setPrefix(result.prefix);
        } catch (error) {
            setError(String(error));
        } finally {
            setBusy(false);
        }
    };
    return (
        <details className="key-panel">
            <summary>Your API key {prefix && <code>{prefix}…</code>}</summary>
            <p>Use a bearer key to create jobs from your scripts. Rotating immediately revokes the previous key.</p>
            <button type="button" disabled={busy} onClick={() => void issue()}>
                {prefix ? 'Rotate API key' : 'Create API key'}
            </button>
            {key && (
                <label>
                    API key — copy now; shown only once
                    <input readOnly value={key} onFocus={(event) => event.target.select()} />
                </label>
            )}
            {error && <p role="alert">{error}</p>}
            <a href="https://github.com/ragaeeb/skalu#api">API documentation ↗</a>
        </details>
    );
};
