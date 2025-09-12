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

create index if not exists idx_messages_user_id on messages(user_id);
