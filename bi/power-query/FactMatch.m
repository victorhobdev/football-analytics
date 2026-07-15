let
    Source = Parquet.Document(File.Contents(SnapshotRoot & "\\FactMatch.parquet"))
in
    Source
