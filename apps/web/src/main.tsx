import { createRoot } from 'react-dom/client';
import { version } from '../../../package.json';
import { AccountForm } from './AccountForm';
import { auth } from './client';
import { Workbench } from './Workbench';
import './styles.css';

const App = () => {
    const { data: session, isPending } = auth.useSession();
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
