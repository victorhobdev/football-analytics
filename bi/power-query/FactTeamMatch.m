let
    Source = Parquet.Document(File.Contents(SnapshotRoot & "\\FactTeamMatch.parquet"))
in
    Source
