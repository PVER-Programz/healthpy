# healthpy
Health monitor migrated to python flask

## Patient video TURN configuration

Patient video is relay-only and requires a TURN service. Set these environment variables before starting Flask:

- `TURN_URLS`: comma-separated TURN URLs, including transport, such as `turn:turn.example.com:3478?transport=udp,turns:turn.example.com:5349?transport=tcp`
- `TURN_USERNAME`: TURN username
- `TURN_CREDENTIAL`: TURN password or credential

PowerShell example:

```powershell
$env:TURN_URLS = "turn:turn.example.com:3478?transport=udp,turns:turn.example.com:5349?transport=tcp"
$env:TURN_USERNAME = "your-turn-username"
$env:TURN_CREDENTIAL = "your-turn-credential"
python app.py
```

Replace the example host and credentials with values from a TURN provider you control. TURN credentials are delivered to browsers for WebRTC, so use short-lived credentials for production. Without valid TURN settings, the caretaker dashboard reports that TURN is not configured and video cannot connect.
