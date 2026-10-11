-- FMV write-ups that the fmv-chat edge function reads. One row per ticker per date.
-- RLS is on with no policies, so only the service role (the edge function) can read it.
create table if not exists public.fmv_docs (
  ticker  text not null,
  as_of   date not null,
  content text not null,          -- the full fmv.md for that ticker/date
  primary key (ticker, as_of)
);
alter table public.fmv_docs enable row level security;

-- Upload example (psql or the SQL editor):
--   insert into public.fmv_docs (ticker, as_of, content)
--   values ('GOOGL', '2026-10-09', $md$ ...paste fmv.md... $md$)
--   on conflict (ticker, as_of) do update set content = excluded.content;
