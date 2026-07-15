select
    md5(pg_get_viewdef('mart.stg_matches'::regclass, true)) as active_view_hash,
    md5(pg_get_viewdef('{{ ref('stg_matches') }}'::regclass, true)) as versioned_view_hash
where md5(pg_get_viewdef('mart.stg_matches'::regclass, true))
   <> md5(pg_get_viewdef('{{ ref('stg_matches') }}'::regclass, true))
