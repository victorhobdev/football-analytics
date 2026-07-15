{{ config(materialized='table', schema='control') }}

with source as (
    select *
    from (
        values
            ('copa_do_brasil', '2021', 'knockout', 'cdb_knockout_progressive_entry_v1', 'club', 'not_applicable', 'cdb_stage_governed_tie_rules_v1', 'validated_pilot'),
            ('copa_do_brasil', '2022', 'knockout', 'cdb_knockout_progressive_entry_v1', 'club', 'not_applicable', 'cdb_stage_governed_tie_rules_v1', 'validated_pilot'),
            ('copa_do_brasil', '2023', 'knockout', 'cdb_knockout_progressive_entry_v1', 'club', 'not_applicable', 'cdb_stage_governed_tie_rules_v1', 'validated_pilot'),
            ('copa_do_brasil', '2024', 'knockout', 'cdb_knockout_progressive_entry_v1', 'club', 'not_applicable', 'cdb_stage_governed_tie_rules_v1', 'pilot_proof_season'),
            ('copa_do_brasil', '2025', 'knockout', 'cdb_knockout_progressive_entry_v1', 'club', 'not_applicable', 'cdb_stage_governed_tie_rules_v1', 'pilot_proof_season'),
            ('supercopa_do_brasil', '2025', 'knockout', 'supercopa_single_final_v1', 'club', 'not_applicable', 'single_leg_extra_time_penalties_v1', 'modern_era_closed_scope'),
            ('libertadores', '2021', 'hybrid', 'lib_qualification_group_knockout_v1', 'club', 'conmebol_group_standard_v1', 'conmebol_stage_governed_tie_rules_v1', 'validated_pilot'),
            ('libertadores', '2022', 'hybrid', 'lib_qualification_group_knockout_v1', 'club', 'conmebol_group_standard_v1', 'conmebol_stage_governed_tie_rules_v1', 'validated_pilot'),
            ('libertadores', '2023', 'hybrid', 'lib_qualification_group_knockout_v1', 'club', 'conmebol_group_standard_v1', 'conmebol_stage_governed_tie_rules_v1', 'validated_pilot'),
            ('libertadores', '2024', 'hybrid', 'lib_qualification_group_knockout_v1', 'club', 'conmebol_group_standard_v1', 'conmebol_stage_governed_tie_rules_v1', 'pilot_proof_season'),
            ('libertadores', '2025', 'hybrid', 'lib_qualification_group_knockout_v1', 'club', 'conmebol_group_standard_v1', 'conmebol_stage_governed_tie_rules_v1', 'pilot_proof_season'),
            ('sudamericana', '2024', 'hybrid', 'sud_qualification_group_playoff_knockout_v1', 'club', 'conmebol_sudamericana_group_progression_v1', 'conmebol_stage_governed_tie_rules_v1', 'pilot_proof_season'),
            ('sudamericana', '2025', 'hybrid', 'sud_qualification_group_playoff_knockout_v1', 'club', 'conmebol_sudamericana_group_progression_v1', 'conmebol_stage_governed_tie_rules_v1', 'pilot_proof_season'),
            ('champions_league', '2020_21', 'hybrid', 'ucl_group_knockout_v1', 'club', 'uefa_group_standard_v1', 'uefa_stage_governed_tie_rules_v1', 'historical_format_v1'),
            ('champions_league', '2021_22', 'hybrid', 'ucl_group_knockout_v1', 'club', 'uefa_group_standard_v1', 'uefa_stage_governed_tie_rules_v1', 'historical_format_v1'),
            ('champions_league', '2022_23', 'hybrid', 'ucl_group_knockout_v1', 'club', 'uefa_group_standard_v1', 'uefa_stage_governed_tie_rules_v1', 'historical_format_v1'),
            ('champions_league', '2023_24', 'hybrid', 'ucl_group_knockout_v1', 'club', 'uefa_group_standard_v1', 'uefa_stage_governed_tie_rules_v1', 'pilot_proof_season'),
            ('champions_league', '2024_25', 'hybrid', 'ucl_league_table_knockout_v1', 'club', 'uefa_league_phase_standard_v1', 'uefa_stage_governed_tie_rules_v1', 'pilot_proof_season'),
            ('fifa_intercontinental_cup', '2024', 'knockout', 'fic_annual_champions_knockout_v1', 'club', 'not_applicable', 'single_leg_extra_time_penalties_v1_pending_tournament_regs', 'pilot_proof_season')
    ) as seeded (
        competition_key,
        season_label,
        format_family,
        season_format_code,
        participant_scope,
        group_ranking_rule_code,
        tie_rule_code,
        notes
    )
)
select
    trim(competition_key) as competition_key,
    trim(season_label) as season_label,
    trim(format_family) as format_family,
    trim(season_format_code) as season_format_code,
    trim(participant_scope) as participant_scope,
    trim(group_ranking_rule_code) as group_ranking_rule_code,
    trim(tie_rule_code) as tie_rule_code,
    trim(notes) as notes,
    now() as updated_at
from source
