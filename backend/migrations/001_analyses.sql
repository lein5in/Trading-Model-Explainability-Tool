create extension if not exists pgcrypto;

create table if not exists public.analyses (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    status text not null default 'queued' check (status in ('queued', 'running', 'completed', 'partial', 'failed')),
    stage text,
    params jsonb,
    model_meta jsonb,
    result jsonb,
    report jsonb,
    error text,
    client_ip_hash text
);

create index if not exists analyses_created_at_idx on public.analyses (created_at);
create index if not exists analyses_status_idx on public.analyses (status);

create table if not exists public.ohlcv_cache (
    key text primary key,
    payload jsonb,
    fetched_at timestamptz
);

alter table public.analyses enable row level security;
alter table public.ohlcv_cache enable row level security;
