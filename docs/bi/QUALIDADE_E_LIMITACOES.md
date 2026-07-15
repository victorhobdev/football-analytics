# Qualidade e limitacoes

## Snapshot público exportado em 2026-07-15

- O mart bruto contém 259.872 partidas em 1.004 escopos `provider|competition_key|season_label`.
- A exportação pública seleciona 861 escopos, um por competição e temporada, resultando em 245.603 partidas e 491.198 linhas time-partida.
- A precedência pública é `sportmonks`, `dataset_brasileirao`, `transfermarkt`, `eloratings` e, por último, qualquer outro provedor disponível.
- `DimScope` preserva os 1.004 escopos e identifica os 861 preferenciais; as páginas públicas não oferecem filtro por provedor.
- `sportmonks|la_liga|2024_25`: 380 partidas com placar e 380 com estatisticas de jogador. A fixture retornou `PASS`.
- Nesse recorte, 11.647 das 16.922 linhas jogador-partida possuem nota: cobertura de 68,8276%. O card de cobertura deve acompanhar qualquer leitura de nota média.
- O snapshot público contém 491.198 linhas de time-partida, 607.096 linhas de jogador-partida, 3.060 registros na dimensão de times e 32.968 registros na dimensão de jogadores.
- Estatisticas de jogador estavam presentes em 50 escopos, todos do provedor `sportmonks`: 14.147 partidas cobertas de 14.193 nesses escopos.

Esses numeros sao evidencias do snapshot local, nao promessas para refreshes futuros. Rode `bi/validation/selecionar_recorte.sql` antes de publicar novamente.

## Regras de comunicacao no relatorio

1. O recorte público é identificado por competição e temporada e usa somente o provedor preferencial. Comparações entre provedores ficam restritas à página interna de diagnóstico.
2. A classificacao calculada e uma agregacao por pontos; ela nao substitui uma tabela oficial quando a competicao possui desempates regulamentares, pontos deduzidos ou fases eliminatorias.
3. Partidas sem os dois placares nunca entram em partidas, pontos, PPG, gols ou evolucao.
4. Ranking de jogador, posse e precisão de passe respeitam os limites de suficiência; o relatório não converte ausência em zero nem afirma cobertura integral.
5. Nulo nao vira zero: ausencia de minutos, nota ou finalizacao permanece ausente na medida correspondente.
6. Casa/fora e uma associacao observada. O visual deve declarar que nao demonstra causalidade.

## Limites conhecidos

- `competition_sk` e `league_id` nao sao a chave de escopo do Power BI; use a chave composta documentada.
- Times e jogadores relacionam-se às fatos pelas chaves substitutas `team_sk` e `player_sk`. Isso evita separar aliases conhecidos; por exemplo, `Kylian Mbappé`, `Kylian Mbappé Lottin` e `K. Mbappé` são apresentados pela identidade canônica da `DimPlayer`.
- A cobertura de estatísticas de jogador é muito menor que a de resultados de partidas. O diagnóstico interno expõe essa diferença e as páginas públicas suprimem métricas sem amostra suficiente.
- O ranking calculado não implementa critérios oficiais de desempate, deduções ou regulamentos de fases. Ele é uma análise agregada, não uma classificação oficial.
- **Publicar na Web** torna o conteúdo acessível sem autenticação. O iframe só deve ser gerado após confirmar que todos os campos expostos são adequados para publicação pública.
