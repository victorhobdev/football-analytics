\set ON_ERROR_STOP on

begin;

delete from raw.wc_match_events;
delete from raw.wc_bookings;
delete from raw.wc_substitutions;
delete from raw.wc_goals;
delete from raw.wc_squads;
delete from raw.wc_player_identity_map;
delete from raw.wc_team_identity_map;
delete from raw.standings_snapshots where competition_key = 'fifa_world_cup_mens';
delete from raw.fixtures where competition_key = 'fifa_world_cup_mens';
delete from raw.competition_seasons where competition_key = 'fifa_world_cup_mens';
delete from control.wc_entity_match_review_queue;
delete from control.wc_source_snapshots;

\copy raw.competition_seasons from '/tmp/wc_delta/raw_competition_seasons.csv' with (format csv, header true)
\copy raw.fixtures from '/tmp/wc_delta/raw_fixtures.csv' with (format csv, header true)
\copy raw.standings_snapshots from '/tmp/wc_delta/raw_standings_snapshots.csv' with (format csv, header true)
\copy raw.wc_player_identity_map from '/tmp/wc_delta/raw_wc_player_identity_map.csv' with (format csv, header true)
\copy raw.wc_team_identity_map from '/tmp/wc_delta/raw_wc_team_identity_map.csv' with (format csv, header true)
\copy raw.wc_squads from '/tmp/wc_delta/raw_wc_squads.csv' with (format csv, header true)
\copy raw.wc_goals from '/tmp/wc_delta/raw_wc_goals.csv' with (format csv, header true)
\copy raw.wc_match_events from '/tmp/wc_delta/raw_wc_match_events.csv' with (format csv, header true)
\copy raw.wc_bookings from '/tmp/wc_delta/raw_wc_bookings.csv' with (format csv, header true)
\copy raw.wc_substitutions from '/tmp/wc_delta/raw_wc_substitutions.csv' with (format csv, header true)
\copy control.wc_entity_match_review_queue from '/tmp/wc_delta/control_wc_entity_match_review_queue.csv' with (format csv, header true)
\copy control.wc_source_snapshots from '/tmp/wc_delta/control_wc_source_snapshots.csv' with (format csv, header true)

analyze raw.competition_seasons;
analyze raw.fixtures;
analyze raw.standings_snapshots;
analyze raw.wc_player_identity_map;
analyze raw.wc_team_identity_map;
analyze raw.wc_squads;
analyze raw.wc_goals;
analyze raw.wc_match_events;
analyze raw.wc_bookings;
analyze raw.wc_substitutions;

commit;
