# Authentication for automated agents

BIM Guard's API (`/api/*`) is protected by Supabase-issued JWTs. There is no
API-key scheme and no separate agent auth path — an agent authenticates the
same way the browser client does, then calls the API with a bearer token.

## Getting a token

Obtain a session via the Supabase Auth password grant against this project's
Supabase URL:

```
POST {SUPABASE_URL}/auth/v1/token?grant_type=password
apikey: {SUPABASE_ANON_KEY}
Content-Type: application/json

{"email": "you@example.com", "password": "..."}
```

The response's `access_token` is a JWT. Use it as a bearer token on every API
call:

```
GET /api/projects
Authorization: Bearer {access_token}
```

## Verification

The backend verifies the token's signature against Supabase's published JWKS
on every request (`app/auth.py`) — it does not trust the token's claims
blindly, and it accepts tokens regardless of how they were issued (password
grant, Google OAuth, etc.), so there is nothing agent-specific to configure.

## API reference

- OpenAPI schema: [`/api/openapi.json`](/api/openapi.json)
- Interactive docs: [`/api/docs`](/api/docs)
- API catalog: [`/.well-known/api-catalog`](/.well-known/api-catalog)

## Scope

Tokens are tied to a Supabase Auth user and carry that user's own
permissions — there is no elevated or service-role access available through
this flow. Do not use the shared local-dev test account
(`dev@bim-guard.local`, documented in `CLAUDE.md`) against a production
deployment.
