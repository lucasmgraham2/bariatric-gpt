$ErrorActionPreference = 'Stop'

$ts = Get-Date -Format 'yyyyMMddHHmmss'
$username = "convtest_$ts"
$email = "$username@example.com"
$pass = 'TestPass123!'

$regBody = @{ email = $email; username = $username; password = $pass } | ConvertTo-Json
$reg = Invoke-RestMethod -Method Post -Uri 'http://localhost:8002/register' -ContentType 'application/json' -Body $regBody
$userId = $reg.id

$profile = @{
  surgery_date = '2025-12-01'
  diet_type = 'Standard'
  allergies = @('peanuts')
  activity_level = 'Lightly Active'
  todays_meals = @()
  protein_today = 0
}

$profileBody = @{ profile = $profile } | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Put -Uri "http://localhost:8002/me/$userId/profile" -ContentType 'application/json' -Body $profileBody | Out-Null

$convLog = $null

$req1 = @{
  message = 'Can you suggest a high-protein lunch for me today?'
  user_id = "$userId"
  profile = $profile
  conversation_log = $convLog
  debug = $true
} | ConvertTo-Json -Depth 15
$r1 = Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/api/v1/invoke_agent_graph' -ContentType 'application/json' -Body $req1
$convLog = $r1.conversation_log

$req2 = @{
  message = 'Record that meal'
  user_id = "$userId"
  profile = $profile
  conversation_log = $convLog
  debug = $true
} | ConvertTo-Json -Depth 15
$r2 = Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/api/v1/invoke_agent_graph' -ContentType 'application/json' -Body $req2
$convLog = $r2.conversation_log

$meAfter = Invoke-RestMethod -Method Get -Uri "http://localhost:8002/me/$userId"

$req3 = @{
  message = 'Thanks, and can you remind me why that choice fit my phase?'
  user_id = "$userId"
  profile = $meAfter.profile
  conversation_log = $convLog
  debug = $true
} | ConvertTo-Json -Depth 15
$r3 = Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/api/v1/invoke_agent_graph' -ContentType 'application/json' -Body $req3

Write-Output "USER_ID=$userId"
Write-Output "TURN1=$($r1.response_text)"
Write-Output "TURN2=$($r2.response_text)"
Write-Output "TURN2_DATA=$($r2.data_response)"
Write-Output "MEALS_JSON=$((@($meAfter.profile.todays_meals) | ConvertTo-Json -Depth 10 -Compress))"
Write-Output "PROTEIN_TODAY=$($meAfter.profile.protein_today)"
Write-Output "TURN3=$($r3.response_text)"