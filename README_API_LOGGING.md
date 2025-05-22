# Claude Code API Logger

This is a modified version of the official Claude Code CLI that adds comprehensive API request/response logging capabilities.

## What's Modified

The `fetchWithTimeout` function in `cli.js` has been enhanced to log all API interactions with the Anthropic Claude API.

### Key Changes

1. **Added fs import**: Added `import { writeFileSync, appendFileSync } from 'fs';` at the top of the file
2. **Request logging**: Captures complete request details before sending
3. **Response logging**: Captures complete response details after receiving

### What Gets Logged

**Request Data:**
- Timestamp
- Request type ("REQUEST")
- Full URL
- HTTP method
- All headers (including authorization tokens)
- Complete request body/payload

**Response Data:**
- Timestamp
- Response type ("RESPONSE") 
- Full URL
- HTTP status code
- Status text
- All response headers
- Complete response body

### Log Location

All API interactions are logged to `claude-api.log` in the current working directory in JSON format.

## Usage

Run the modified Claude Code CLI normally:

```bash
node cli.js -p "your prompt here"
```

All API calls will be automatically logged to `claude-api.log` in the current directory.

## Log Analysis

View recent API calls:
```bash
tail -5 claude-api.log | jq -r '.url + " " + .type + " " + (.timestamp | split("T")[1] | split(".")[0])'
```

View request details:
```bash
grep '"type":"REQUEST"' claude-api.log | jq .
```

View response details:
```bash
grep '"type":"RESPONSE"' claude-api.log | jq .
```

## Security Note

⚠️ **WARNING**: The log file contains sensitive information including:
- API authentication tokens
- Complete request/response data
- Potentially sensitive conversation content

Make sure to secure the log file and avoid committing it to public repositories.

## Original Claude Code

This is based on the official Claude Code CLI v0.2.122. The original functionality remains unchanged - only logging has been added.

## Dependencies Added

- `better-sqlite3`: Required for the original CLI functionality
- `fs` module: Used for logging (Node.js built-in)