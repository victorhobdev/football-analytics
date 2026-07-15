let
    Source = Parquet.Document(File.Contents(SnapshotRoot & "\\DimDate.parquet"))
in
    Source
