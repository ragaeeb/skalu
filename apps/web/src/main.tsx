import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { AccountForm } from './AccountForm';
import { api, auth } from './client';
import { Workbench } from './Workbench';
import './styles.css';

const App = () => {
    const { data: session, isPending } = auth.useSession();
    const [version, setVersion] = useState('');
    useEffect(() => {
        void api<{ version: string }>('/version')
            .then((data) => setVersion(data.version))
            .catch(() => undefined);
    }, []);
    return (
        <>
            <header>
                <a className="brand" href="/">
                    skalu<span> / </span>
                    <small>document intelligence</small>
                </a>
                {session && (
                    <div>
                        <span>{session.user.name}</span>
                        <button
                            type="button"
                            className="secondary"
                            onClick={() =>
                                void auth.signOut().then(() => {
                                    location.href = '/';
                                })
                            }
                        >
                            Sign out
                        </button>
                    </div>
                )}
            </header>
            {isPending ? <p role="status">Loading your account…</p> : session ? <Workbench /> : <AccountForm />}
            <footer>
                <span>Structure, without the guesswork.</span>
                <span>Skalu {version}</span>
            </footer>
        </>
    );
};
const root = document.getElementById('root');
if (root) {
    createRoot(root).render(<App />);
}
