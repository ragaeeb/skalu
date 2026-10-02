export const engineFetch = (env: Env, jobId: string, path: string, init?: RequestInit) => {
    // Local development runs the identical native service without requiring Docker.
    if (env.ENGINE_LOCAL_URL) {
        const origin = new URL(env.ENGINE_LOCAL_URL);
        if (!['127.0.0.1', 'localhost'].includes(origin.hostname)) {
            throw new Error('Local engine must use loopback.');
        }
        return fetch(new URL(path, origin), init);
    }
    return env.ENGINE.getByName(jobId).fetch(new Request(`http://engine${path}`, init));
};

export const loadSource = async (env: Env, jobId: string) => {
    const source = await env.FILES.get(`jobs/${jobId}/source.pdf`);
    if (!source) {
        throw new Error('Uploaded PDF is missing.');
    }
    return engineFetch(env, jobId, `/jobs/${jobId}`, {
        body: source.body,
        headers: { 'content-length': String(source.size), 'content-type': 'application/pdf' },
        method: 'PUT',
    });
};

export const stopEngine = async (env: Env, jobId: string) => {
    if (env.ENGINE_LOCAL_URL) {
        const response = await engineFetch(env, jobId, `/jobs/${jobId}`, { method: 'DELETE' });
        await response.body?.cancel();
        if (!response.ok) {
            throw new Error('Native engine cancellation failed.');
        }
    } else {
        // destroy() awaits runtime teardown; stop() only sends a signal in the pinned SDK.
        await env.ENGINE.getByName(jobId).destroy();
    }
};
