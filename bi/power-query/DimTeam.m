let
    Source = Parquet.Document(File.Contents(SnapshotRoot & "\\DimTeam.parquet"))
in
    Source
