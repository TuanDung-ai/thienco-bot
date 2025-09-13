-- supabase_memory_schema.sql — Unified schema (users/messages + memory + RPC 384d)

-- ========== 0) Extensions ==========
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";
create extension if not exists "vector";

-- ========== 1) Users / Messages ==========
create table if not exists public.users (
  user_id     bigint primary key,
  first_seen_at timestamptz default now(),
  meta        jsonb
);

create table if not exists public.messages (
  id          bigserial primary key,
  user_id     bigint not null,
  chat_id     bigint not null default 0,
  role        text not null check (role in ('user','assistant','system')),
  content     text not null,
  created_at  timestamptz default now()
);

create index if not exists idx_messages_user_id on public.messages(user_id);
create index if not exists idx_messages_chat_id on public.messages(chat_id);

-- ========== 2) Memory tables (vector 384 cho BGE-small) ==========
create table if not exists public.memory_facts (
  id         uuid primary key default gen_random_uuid(),
  user_id    text not null,
  content    text not null,
  meta       jsonb,
  created_at timestamptz default now()
);

create table if not exists public.conv_summaries (
  id              uuid primary key default gen_random_uuid(),
  user_id         text not null,
  window_start_at timestamptz,
  window_end_at   timestamptz,
  summary         text not null,
  created_at      timestamptz default now()
);

create table if not exists public.memory_vectors (
  id         uuid primary key default gen_random_uuid(),
  user_id    text not null,
  ref_type   text not null, -- 'fact' | 'summary' | ...
  ref_id     uuid not null references public.memory_facts(id) on delete cascade,
  content    text not null,
  embedding  vector(384) not null,
  created_at timestamptz default now()
);

-- Helpful indexes
create index if not exists idx_memory_vectors_user on public.memory_vectors(user_id);
create index if not exists idx_memory_vectors_ivf on public.memory_vectors using ivfflat (embedding vector_cosine_ops) with (lists=100);

-- ========== 3) RPC: memory_search(u text, q vector(384), k int) ==========
drop function if exists public.memory_search(text, vector(384), int);
create or replace function public.memory_search(u text, q vector(384), k int)
returns table (
  ref_type text,
  ref_id   uuid,
  content  text,
  score    double precision
) language sql stable as $$
  select ref_type, ref_id, content,
         1 - (embedding <=> q) as score
  from public.memory_vectors
  where user_id = u
  order by embedding <=> q
  limit k
$$;

-- ========== 4) Refresh & analyze ==========
notify pgrst, 'reload schema';
analyze public.memory_vectors;
