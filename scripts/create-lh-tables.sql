-- Karpathy Loop — Lighthouse Branch Scores Table
-- Run this ONCE in Supabase SQL editor: https://supabase.com/dashboard/project/vjlsmljcceseeywepjoo/sql/new

create table if not exists lh_branch_scores (
  id              uuid        primary key default gen_random_uuid(),
  created_at      timestamptz default now(),
  app_name        text        not null,
  branch          text        not null,
  pr_url          text,
  category        text        not null,   -- Performance | Accessibility | Best Practices | SEO
  score_before    int         not null,
  score_after     int,                    -- filled in by audit cron after PR merge
  delta           int,                    -- score_after - score_before (positive = improvement)
  model           text,                   -- OpenRouter model used
  fix_description text,                   -- one-line AI analysis
  status          text        default 'pending'
                              check (status in ('pending', 'improved', 'regressed', 'merged', 'skipped'))
);

-- Index for quick lookups by app
create index if not exists lh_branch_scores_app_name_idx on lh_branch_scores (app_name);
create index if not exists lh_branch_scores_status_idx   on lh_branch_scores (status);

-- Optional: view for the quality dashboard
create or replace view lh_improvement_summary as
select
  app_name,
  category,
  count(*)                                          as total_attempts,
  count(*) filter (where status = 'improved')       as wins,
  count(*) filter (where status = 'regressed')      as regressions,
  round(avg(delta) filter (where delta is not null), 1) as avg_delta,
  max(score_after)                                  as best_score
from lh_branch_scores
group by app_name, category
order by app_name, category;
