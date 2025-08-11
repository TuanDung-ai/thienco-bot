
-- Basic tables for MVP

create table if not exists users (
  user_id bigint primary key,
  first_seen_at timestamp with time zone default now(),
  meta jsonb
);

create table if not exists messages (
  id bigserial primary key,
  user_id bigint not null,
  role text not null check (role in ('user','assistant','system')),
  content text not null,
  created_at timestamp with time zone default now()
);

create table if not exists memory_snapshots (
  user_id bigint primary key,
  summary_text text,
  tokens_est int,
  updated_at timestamp with time zone default now()
);

create table if not exists faq_entries (
  faq_id bigserial primary key,
  question text not null,
  answer text not null,
  embedding vector(1536),
  source text,
  created_at timestamp with time zone default now()
);

create table if not exists feedback (
  id bigserial primary key,
  user_id bigint not null,
  message_id bigint,
  vote int check (vote in (-1,0,1)),
  note text,
  created_at timestamp with time zone default now()
);

create table if not exists metrics (
  id bigserial primary key,
  name text not null,
  value numeric,
  meta jsonb,
  created_at timestamp with time zone default now()
);
