let
    Source = Parquet.Document(File.Contents(SnapshotRoot & "\\DimPlayer.parquet"))
in
    Source
