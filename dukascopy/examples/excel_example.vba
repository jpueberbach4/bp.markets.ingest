' Press ALT + F11, go to Insert > Module, and paste the following:
Sub ImportBPData()
    Dim ws As Worksheet
    Dim url As String
    Dim qt As QueryTable
    
    ' The URL (Concatenated for readability)
    url = "TEXT;http://localhost:8000/ohlcv/1.1/select/EUR-USD,1h[" & _
          "adx(14):atr(14):ema(20):bbands(20,2.0):macd(12,26,9)" & _
          "]/after/2025-11-17+19:00:00/output/CSV?limit=1000&order=asc"


    url = url & "&cb=" & Timer ' Adds a unique number to force a fresh request
    
    Set ws = ThisWorkbook.Sheets(1) ' Target the first sheet
    ws.Cells.ClearContents ' Optional: Clear old data
    
    ' Create the QueryTable
    Set qt = ws.QueryTables.Add(Connection:=url, Destination:=ws.Range("A1"))
    
    With qt
        .TextFileParseType = xlDelimited
        .TextFileCommaDelimiter = True ' Ensure CSV comma separation
        .TextFilePlatform = 65001 ' UTF-8 support
        .Refresh Period:=0, BackgroundQuery:=False
    End With
    
    ' Cleanup to keep the file light
    qt.Delete
    
    MsgBox "Data Imported Successfully!", vbInformation
End Sub