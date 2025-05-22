#!/usr/bin/env python3
"""
Extract FULL REQUEST bodies from Claude API logs
Show complete request payloads with proper formatting
"""
import json
import sys
from datetime import datetime

def validate_json_line(line):
    """Validate if line is proper JSON with required fields"""
    try:
        if not line.strip():
            return None, "Empty line"
        
        data = json.loads(line.strip())
        
        # Must have required fields
        required_fields = ['timestamp', 'type', 'url']
        for field in required_fields:
            if field not in data:
                return None, f"Missing required field: {field}"
        
        # Type must be REQUEST or RESPONSE
        if data['type'] not in ['REQUEST', 'RESPONSE']:
            return None, f"Invalid type: {data['type']}"
        
        return data, None
        
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"
    except Exception as e:
        return None, f"Validation error: {e}"

def format_timestamp(iso_timestamp):
    """Convert ISO timestamp to readable format"""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return iso_timestamp

def format_request_body(body_str):
    """Format request body with proper JSON indentation"""
    if not body_str:
        return "No body"
    
    try:
        # Parse and re-format with proper indentation
        body_obj = json.loads(body_str)
        return json.dumps(body_obj, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return f"Invalid JSON body:\n{body_str}"

def extract_full_requests(log_file, output_file):
    """Extract complete REQUEST entries with full bodies"""
    
    stats = {
        'total_lines': 0,
        'valid_json': 0,
        'invalid_json': 0,
        'requests': 0,
        'responses': 0,
        'errors': []
    }
    
    with open(output_file, 'w') as out:
        out.write("# Complete Claude API Requests\n\n")
        out.write("*Full request bodies with all details*\n\n")
        out.write("---\n\n")
        
        request_count = 0
        
        with open(log_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                stats['total_lines'] += 1
                
                # Validate JSON
                data, error = validate_json_line(line)
                
                if error:
                    stats['invalid_json'] += 1
                    if len(stats['errors']) < 10:  # Keep first 10 errors
                        stats['errors'].append(f"Line {line_num}: {error}")
                    continue
                
                stats['valid_json'] += 1
                
                # Count by type
                if data['type'] == 'REQUEST':
                    stats['requests'] += 1
                else:
                    stats['responses'] += 1
                    continue  # Skip responses
                
                # Process REQUEST
                request_count += 1
                timestamp = format_timestamp(data['timestamp'])
                url = data['url']
                method = data.get('method', 'GET').upper()
                
                out.write(f"## Request #{request_count}\n\n")
                out.write(f"**Time:** {timestamp}  \n")
                out.write(f"**Method:** {method}  \n")
                out.write(f"**URL:** `{url}`  \n\n")
                
                # Show headers
                headers = data.get('headers', {})
                if headers:
                    out.write("### Headers\n\n")
                    for key, value in headers.items():
                        # Mask authorization token
                        if key.lower() == 'authorization' and value.startswith('Bearer '):
                            value = f"Bearer {value[7:14]}...{value[-8:]}"
                        out.write(f"- **{key}:** `{value}`\n")
                    out.write("\n")
                
                # Show FULL request body
                out.write("### Complete Request Body\n\n")
                body = data.get('body', '')
                formatted_body = format_request_body(body)
                
                out.write("```json\n")
                out.write(formatted_body)
                out.write("\n```\n\n")
                
                # Show body size info
                body_size = len(body) if body else 0
                out.write(f"**Body Size:** {body_size:,} characters\n\n")
                
                out.write("---\n\n")
        
        # Write stats
        out.write("## Processing Statistics\n\n")
        out.write(f"- **Total Lines:** {stats['total_lines']}\n")
        out.write(f"- **Valid JSON:** {stats['valid_json']}\n")
        out.write(f"- **Invalid JSON:** {stats['invalid_json']}\n")
        out.write(f"- **Requests:** {stats['requests']}\n")
        out.write(f"- **Responses:** {stats['responses']}\n")
        
        if stats['errors']:
            out.write(f"\n### First {len(stats['errors'])} Errors\n\n")
            for error in stats['errors']:
                out.write(f"- {error}\n")

if __name__ == "__main__":
    log_file = "/root/claude-api.log"  # Use root log by default
    output_file = "full-requests.md"
    
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    try:
        extract_full_requests(log_file, output_file)
        print(f"✅ Full requests extracted to {output_file}")
    except FileNotFoundError:
        print(f"❌ Log file '{log_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)