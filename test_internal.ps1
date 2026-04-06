$payload = @{
    tenant_slug = "test"
    channel = "whatsapp"
    contact_name = "Juan Pérez"
    contact_phone = "+595987654321"
    contact_email = $null
    text_content = "Me duele mucho la muela"
} | ConvertTo-Json

Write-Host "Testing internal test endpoint: /api/test/process-message"
Write-Host "Payload: $payload"

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/test/process-message" `
        -Method POST `
        -ContentType "application/json" `
        -Body $payload `
        -UseBasicParsing `
        -ErrorAction Stop
    
    Write-Host "Status: $($response.StatusCode)"
    Write-Host "Response:" 
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $content = $reader.ReadToEnd()
        Write-Host "Response: $content"
    }
}
