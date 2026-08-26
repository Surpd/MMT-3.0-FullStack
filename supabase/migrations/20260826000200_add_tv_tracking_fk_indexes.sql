-- Cover composite foreign keys used by TV progress and notification lookups.
create index if not exists user_episode_progress_episode_idx
  on public.user_episode_progress (tv_id, season_number, episode_number);
create index if not exists tv_notification_deliveries_tv_idx
  on public.tv_notification_deliveries (tv_id);
