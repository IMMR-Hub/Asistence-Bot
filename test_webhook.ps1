$tenant_slug = "test"
$body = "From=whatsapp%3A%2B595987654321&Body=Me%20duele%20la%20muela&MessageSid=SM123"

# Test 1: Using /webhooks/whatsapp/inbound with tenant_slug query parameter
Write-Host "Test 1: /webhooks/whatsapp/inbound with query parameter"
$uri1 = "http://localhost:8000/webhooks/whatsapp/inbound?tenant_slug=$tenant_slug"
try {
    $response1 = Invoke-WebRequest -Uri $uri1 -Method POST -ContentType "application/x-www-form-urlencoded" -Body $body -UseBasicParsing -ErrorAction Stop
    Write-Host "Status: $($response1.StatusCode)"
    Write-Host "Response: $($response1.Content)"
} catch {
    Write-Host "Error: $($_.Exception.Response.StatusCode)"
    $resp = $_.Exception.Response.GetResponseStream() | ForEach-Object { New-Object System.IO.StreamReader($_) } | ForEach-Object { $_.ReadToEnd() }
    Write-Host "Response: $resp"
}

Write-Host "`n---`n"

# Test 2: Using /webhooks/whatsapp/twilio with tenant_slug query parameter
Write-Host "Test 2: /webhooks/whatsapp/twilio with query parameter"
$uri2 = "http://localhost:8000/webhooks/whatsapp/twilio?tenant_slug=$tenant_slug"
try {
    $response2 = Invoke-WebRequest -Uri $uri2 -Method POST -ContentType "application/x-www-form-urlencoded" -Body $body -UseBasicParsing -ErrorAction Stop
    Write-Host "Status: $($response2.StatusCode)"
    Write-Host "Response: $($response2.Content)"
} catch {
    Write-Host "Error: $($_.Exception.Response.StatusCode)"
    $resp = $_.Exception.Response.GetResponseStream() | ForEach-Object { New-Object System.IO.StreamReader($_) } | ForEach-Object { $_.ReadToEnd() }
    Write-Host "Response: $resp"
}
