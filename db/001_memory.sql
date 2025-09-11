-- 001_memory.sql — RAG memory schema (pgvector, 1536 dims for openai/text-embedding-3-small)
-- Run this in Supabase SQL editor (or psql). Safe to re-run.

create extension if not exists vector;

create table if not exists memory_facts (
  id bigserial primary key,
  user_id bigint not null,
  content text not null,
  meta jsonb,
  created_at timestamptz default now()
);

-- Choose ONE dimension that matches your embedding model.
-- For openai/text-embedding-3-small: 1536
-- For openai/text-embedding-3-large: 3072
create table if not exists memory_vectors (
  id bigserial primary key,
  user_id bigint not null,
  ref_type text not null check (ref_type in ('fact','summary')),
  ref_id bigint,
  content text not null,
  embedding vector(1536) not null,
  created_at timestamptz default now()
);

create index if not exists idx_memory_vectors_user on memory_vectors(user_id);
-- Cosine distance index for fast ANN search
create index if not exists idx_memory_vectors_embedding on memory_vectors
  using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- Cosine-similarity search: returns highest score (0..1)
create or replace function memory_search(u bigint, q vector(1536), k int default 8)
returns table(ref_type text, ref_id bigint, content text, score float4)
language sql stable as $$
  select ref_type, ref_id, content, 1 - (embedding <=> q) as score
  from memory_vectors
  where user_id = u
  order by embedding <=> q
  limit k
$$;
