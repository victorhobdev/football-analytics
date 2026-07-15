let
    Source = Parquet.Document(File.Contents(SnapshotRoot & "\\DimScope.parquet"))
in
    Source
