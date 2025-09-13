-- Enable extension (idempotent)
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";
create extension if not exists "vector";

-- ===== Tables =====

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
  window_start_at timestamptz not null,
  window_end_at   timestamptz not null,
  summary         text not null,
  created_at      timestamptz default now()
);

create table if not exists public.memory_vectors (
  id         bigserial primary key,
  user_id    text not null,
  ref_type   text not null,              -- 'fact' | 'summary' | ...
  ref_id     uuid not null,              -- trỏ tới memory_facts.id hoặc conv_summaries.id
  content    text not null,
  embedding  vector(384) not null,
  created_at timestamptz default now()
);

-- ===== Indexes =====

-- tra cứu theo user
create index if not exists idx_memory_vectors_user on public.memory_vectors(user_id);

-- lookup theo ref (nếu cần delete/update theo nguồn)
create index if not exists idx_memory_vectors_ref on public.memory_vectors(ref_type, ref_id);

-- ANN index cho cosine (chọn IVFFlat hoặc HNSW; giữ 1 loại để đỡ nặng)
-- IVFFlat (cần ANALYZE trước khi dùng)
create index if not exists memory_vectors_embedding_cosine_idx
  on public.memory_vectors using ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ===== Function search =====

drop function if exists public.memory_search(bigint, vector, integer);
drop function if exists public.memory_search(text,   vector, integer);

create or replace function public.memory_search(
  u text,
  q vector(384),
  k integer default 8
)
returns table (
  ref_type text,
  ref_id   uuid,
  content  text,
  score    double precision
)
language sql stable as $$
  select ref_type, ref_id, content,
         1 - (embedding <=> q) as score
  from public.memory_vectors
  where user_id = u
  order by embedding <=> q
  limit k
$$;

-- refresh PostgREST cache + tối ưu
notify pgrst, 'reload schema';
analyze public.memory_vectors;
