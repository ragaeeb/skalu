import { drizzleAdapter } from '@better-auth/drizzle-adapter';
import { betterAuth } from 'better-auth';
import { drizzle } from 'drizzle-orm/d1';
import { account, rateLimit, session, user, verification } from './auth-schema';

export const getAuth = (env: Env) =>
    betterAuth({
        advanced: {
            ipAddress: { ipAddressHeaders: ['cf-connecting-ip'] },
            useSecureCookies: env.APP_ORIGIN.startsWith('https:'),
        },
        baseURL: env.APP_ORIGIN,
        database: drizzleAdapter(drizzle(env.DB), {
            provider: 'sqlite',
            schema: { account, rateLimit, session, user, verification },
        }),
        emailAndPassword: { enabled: true, maxPasswordLength: 128, minPasswordLength: 12 },
        rateLimit: { enabled: true, max: 20, storage: 'database', window: 60 },
        secret: env.BETTER_AUTH_SECRET,
        trustedOrigins: [env.APP_ORIGIN],
    });

export const hashKey = async (key: string) => {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(key));
    return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
};

export const requireUser = async (request: Request, env: Env, sessionOnly = false): Promise<string> => {
    const header = request.headers.get('authorization');
    if (header && !sessionOnly) {
        if (!/^Bearer sk_[a-f0-9]{64}$/.test(header)) {
            throw new Response('Invalid API key', { status: 401 });
        }
        const key = await env.DB.prepare('SELECT user_id FROM api_key WHERE hash = ?')
            .bind(await hashKey(header.slice(7)))
            .first<{ user_id: string }>();
        if (!key) {
            throw new Response('Invalid API key', { status: 401 });
        }
        return key.user_id;
    }
    const session = await getAuth(env).api.getSession({ headers: request.headers });
    if (!session) {
        throw new Response('Sign in required', { status: 401 });
    }
    if (!['GET', 'HEAD'].includes(request.method) && request.headers.get('origin') !== env.APP_ORIGIN) {
        throw new Response('Invalid request origin', { status: 403 });
    }
    return session.user.id;
};
