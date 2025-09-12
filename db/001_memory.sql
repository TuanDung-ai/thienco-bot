-- 001_memory_384.sql — RAG memory schema for 384d (FastEmbed / BGE-small)

create extension if not exists vector;

create table if not exists memory_facts (
  id bigserial primary key,
  user_id bigint not null,
  content text not null,
  meta jsonb,
  created_at timestamptz default now()
);

create table if not exists memory_vectors (
  id bigserial primary key,
  user_id bigint not null,
  ref_type text not null,      -- 'fact' | 'summary' | ...
  ref_id bigint not null,
  content text not null,
  embedding vector(384) not null
);

create index if not exists idx_memory_vectors_user on memory_vectors(user_id);
create index if not exists idx_memory_vectors_embedding on memory_vectors
  using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- Cosine: distance nhỏ hơn = giống hơn; similarity = 1 - distance
create or replace function memory_search(
  u bigint,
  q vector(384),
  k int default 8
) returns table(ref_type text, ref_id bigint, content text, distance double precision, similarity double precision)
language sql stable as $$
  select ref_type, ref_id, content,
         embedding <=> q as distance,
         1 - (embedding <=> q) as similarity
  from memory_vectors
  where user_id = u
  order by embedding <=> q
  limit k
$$;

-- Gợi ý: sau khi tạo/đổi schema
notify pgrst, 'reload schema';
analyze memory_vectors;
