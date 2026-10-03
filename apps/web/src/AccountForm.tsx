import { type FormEvent, useId, useState } from 'react';
import { auth } from './client';

export const AccountForm = () => {
    const id = useId();
    const [signup, setSignup] = useState(true);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const submit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        const values = new FormData(event.currentTarget);
        setBusy(true);
        setError('');
        try {
            const input = { email: String(values.get('email')), password: String(values.get('password')) };
            const result = signup
                ? await auth.signUp.email({ ...input, name: String(values.get('name')) })
                : await auth.signIn.email(input);
            if (result.error) {
                throw new Error(result.error.message ?? 'Authentication failed.');
            }
        } catch (error) {
            setError(String(error));
        } finally {
            setBusy(false);
        }
    };
    return (
        <section className="account">
            <p className="eyebrow">YOUR DOCUMENT WORKBENCH</p>
            <h1>
                Find the structure.
                <br />
                Keep the detail.
            </h1>
            <p>
                Extract lines and rectangles from your PDFs. Inspect each page as it finishes, then take the JSON into
                your own tools.
            </p>
            <form onSubmit={(event) => void submit(event)}>
                <h2>{signup ? 'Create your account' : 'Welcome back'}</h2>
                {signup && (
                    <label htmlFor={`${id}-name`}>
                        Name
                        <input id={`${id}-name`} name="name" autoComplete="name" required maxLength={100} />
                    </label>
                )}
                <label htmlFor={`${id}-email`}>
                    Email
                    <input id={`${id}-email`} name="email" type="email" autoComplete="email" required maxLength={254} />
                </label>
                <label htmlFor={`${id}-password`}>
                    Password
                    <input
                        id={`${id}-password`}
                        name="password"
                        type="password"
                        minLength={12}
                        maxLength={128}
                        autoComplete={signup ? 'new-password' : 'current-password'}
                        required
                    />
                </label>
                <small>At least 12 characters. Your email is your sign-in identifier.</small>
                {error && <p role="alert">{error}</p>}
                <button type="submit" disabled={busy}>
                    {busy ? 'Please wait…' : signup ? 'Create account' : 'Sign in'}
                </button>
                <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                        setSignup(!signup);
                        setError('');
                    }}
                >
                    {signup ? 'Already have an account? Sign in' : 'Create a new account'}
                </button>
            </form>
        </section>
    );
};
