-- Migration: create_chat_persistence
-- Description: Persist Graph-RAG Copilot conversations and message turns to Supabase.
-- Enables persistent multi-turn chat with date-grouped history and pinned favorites.

create table if not exists public.chat_conversations (
    id text primary key default gen_random_uuid()::text,
    project_id bigint not null references public.projects (id) on delete cascade,
    user_id uuid references auth.users (id) on delete set null,
    title text not null default 'New Conversation',
    scope text not null default 'hybrid',
    document_id bigint references public.documents (id) on delete set null,
    element_class text,
    is_pinned boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_chat_conversations_project_updated 
    on public.chat_conversations (project_id, updated_at desc);
create index if not exists idx_chat_conversations_user 
    on public.chat_conversations (user_id);
create index if not exists idx_chat_conversations_pinned 
    on public.chat_conversations (project_id, is_pinned);

create table if not exists public.chat_messages (
    id text primary key,
    conversation_id text not null references public.chat_conversations (id) on delete cascade,
    role text not null check (role in ('user', 'assistant', 'system')),
    content text not null default '',
    citations jsonb not null default '[]'::jsonb,
    reasoning_steps jsonb not null default '[]'::jsonb,
    tool_calls jsonb not null default '[]'::jsonb,
    cypher_queries jsonb not null default '[]'::jsonb,
    timestamp text,
    created_at timestamptz not null default now()
);

create index if not exists idx_chat_messages_conversation 
    on public.chat_messages (conversation_id, created_at asc);

alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;

revoke all privileges on table public.chat_conversations from anon, authenticated;
revoke all privileges on table public.chat_messages from anon, authenticated;

grant select, insert, update, delete on table public.chat_conversations to service_role;
grant select, insert, update, delete on table public.chat_messages to service_role;
