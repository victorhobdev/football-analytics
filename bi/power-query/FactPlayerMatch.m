let
    Source = Parquet.Document(File.Contents(SnapshotRoot & "\\FactPlayerMatch.parquet"))
in
    Source
