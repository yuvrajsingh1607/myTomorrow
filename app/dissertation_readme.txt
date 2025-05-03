$trainData = @'
[
    {"timestamp": "2025-04-01 09:00:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "success"},
    {"timestamp": "2025-04-01 03:15:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "success"},
    {"timestamp": "2025-04-01 09:15:00", "user_id": "user_2", "ip_address": "192.168.1.2", "result": "success"},
    {"timestamp": "2025-04-01 10:30:00", "user_id": "user_3", "ip_address": "192.168.1.3", "result": "success"},
    {"timestamp": "2025-04-01 11:45:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "failure"},
    {"timestamp": "2025-04-01 12:00:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "failure"},
    {"timestamp": "2025-04-01 14:00:00", "user_id": "user_2", "ip_address": "192.168.1.2", "result": "success"},
    {"timestamp": "2025-04-01 15:30:00", "user_id": "user_3", "ip_address": "192.168.1.3", "result": "failure"},
    {"timestamp": "2025-04-01 16:45:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "success"},
    {"timestamp": "2025-04-01 17:00:00", "user_id": "user_1", "ip_address": "192.168.1.5", "result": "failure"},
    {"timestamp": "2025-04-02 08:30:00", "user_id": "user_2", "ip_address": "192.168.1.2", "result": "success"},
    {"timestamp": "2025-04-02 09:45:00", "user_id": "user_3", "ip_address": "192.168.1.3", "result": "failure"},
    {"timestamp": "2025-04-02 10:30:00", "user_id": "user_2", "ip_address": "192.168.1.2", "result": "failure"},
    {"timestamp": "2025-04-02 11:00:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "success"},
    {"timestamp": "2025-04-02 13:15:00", "user_id": "user_2", "ip_address": "192.168.1.4", "result": "success"},
    {"timestamp": "2025-04-02 14:30:00", "user_id": "user_3", "ip_address": "192.168.1.3", "result": "success"},
    {"timestamp": "2025-04-02 15:00:00", "user_id": "user_2", "ip_address": "10.0.0.1", "result": "success"},
    {"timestamp": "2025-04-02 16:45:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "success"},
    {"timestamp": "2025-04-02 23:50:00", "user_id": "user_3", "ip_address": "192.168.1.3", "result": "success"}
]
'@
# Send training data
Invoke-RestMethod -Uri "http://localhost:59879/train" -Method POST -Body $trainData -ContentType "application/json"


$detectData = @'
[
    {"timestamp": "2025-04-03 09:00:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "success"},  
    {"timestamp": "2025-04-03 03:15:00", "user_id": "user_2", "ip_address": "192.168.1.2", "result": "success"},  
    {"timestamp": "2025-04-03 09:30:00", "user_id": "user_99", "ip_address": "192.168.1.99", "result": "success"}, 
    {"timestamp": "2025-04-03 10:00:00", "user_id": "user_3", "ip_address": "10.0.0.1", "result": "success"},       
    {"timestamp": "2025-04-03 10:15:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "failure"},    
    {"timestamp": "2025-04-03 10:30:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "failure"},    
    {"timestamp": "2025-04-03 10:45:00", "user_id": "user_1", "ip_address": "192.168.1.1", "result": "failure"},    
    {"timestamp": "2025-04-03 11:00:00", "user_id": "user_3", "ip_address": "192.168.1.3", "result": "success"},  
    {"timestamp": "2025-04-03 11:15:00", "user_id": "user_3", "ip_address": "192.168.1.3", "result": "failure"},   
    {"timestamp": "2025-04-03 11:30:00", "user_id": "user_2", "ip_address": "192.168.1.2", "result": "success"}     
]
'@

# Detect anomalies with color output
$response = Invoke-RestMethod -Uri "http://localhost:59879/detect" -Method POST -Body $detectData -ContentType "application/json"

$response.results | ForEach-Object {
    $color = if ($_.is_anomaly) { "Red" } else { "Green" }
    Write-Host "Time: $($_.timestamp) | User: $($_.user_id) | IP: $($_.ip_address)" -ForegroundColor $color
    Write-Host "Result: $($_.result) | Anomaly: $($_.is_anomaly) | Score: $($_.anomaly_score)" -ForegroundColor $color
    Write-Host "----------------------------------------"
}



$response.results | ForEach-Object {
    $color = if ($_.is_anomaly) { "Red" } else { "Green" }
    $output = "Time: {0,-19} | User: {1,-8} | IP: {2,-15} | Result: {3,-8} | Anomaly: {4,-6} | Score: {5,-8} | Unknown: {6}" -f 
        $_.timestamp,
        $_.user_id,
        $_.ip_address,
        $_.result,
        $_.is_anomaly,
        [math]::Round($_.anomaly_score, 4),
        $_.unknown_ip
    
    Write-Host $output -ForegroundColor $color
    
    if ($_.is_anomaly -and $_.reason) {
        Write-Host ("  -> Reasons: " + ($_.reason -join ', ')) -ForegroundColor "Yellow"
    }
    
    Write-Host ("-" * 120)
}

