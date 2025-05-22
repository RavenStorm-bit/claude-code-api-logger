#!/usr/bin/env python3
"""
Extract and parse Claude API responses
Handle both regular JSON and streaming SSE responses
"""
import json
import sys
import re
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

def parse_streaming_response(body_str):
    """Parse Server-Sent Events (SSE) streaming response"""
    if not body_str or 'event:' not in body_str:
        return None
    
    result = {
        'format': 'streaming',
        'events': [],
        'full_text': '',
        'metadata': {}
    }
    
    lines = body_str.split('\n')
    current_event = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            if current_event:
                result['events'].append(current_event)
                current_event = {}
            continue
            
        if line.startswith('event:'):
            current_event['event'] = line[6:].strip()
        elif line.startswith('data:'):
            data_str = line[5:].strip()
            try:
                if data_str and data_str != '{"type": "ping"}':
                    data_obj = json.loads(data_str)
                    current_event['data'] = data_obj
                    
                    # Extract text content
                    if data_obj.get('type') == 'content_block_delta':
                        delta = data_obj.get('delta', {})
                        if delta.get('type') == 'text_delta':
                            text_chunk = delta.get('text', '')
                            result['full_text'] += text_chunk
                    
                    # Extract metadata
                    elif data_obj.get('type') == 'message_start':
                        message = data_obj.get('message', {})
                        result['metadata'].update({
                            'id': message.get('id'),
                            'model': message.get('model'),
                            'role': message.get('role')
                        })
                        usage = message.get('usage', {})
                        if usage:
                            result['metadata']['input_tokens'] = usage.get('input_tokens')
                            result['metadata']['output_tokens'] = usage.get('output_tokens')
                    
                    elif data_obj.get('type') == 'message_delta':
                        delta = data_obj.get('delta', {})
                        usage = data_obj.get('usage', {})
                        if usage:
                            result['metadata']['final_output_tokens'] = usage.get('output_tokens')
                            result['metadata']['stop_reason'] = delta.get('stop_reason')
                            
            except json.JSONDecodeError:
                current_event['raw_data'] = data_str
    
    # Add final event if exists
    if current_event:
        result['events'].append(current_event)
    
    return result

def parse_json_response(body_str):
    """Parse regular JSON response"""
    try:
        data = json.loads(body_str)
        
        result = {
            'format': 'json',
            'full_text': '',
            'metadata': {}
        }
        
        # Extract basic metadata
        result['metadata'] = {
            'id': data.get('id'),
            'model': data.get('model'),
            'role': data.get('role'),
            'stop_reason': data.get('stop_reason')
        }
        
        # Extract usage info
        usage = data.get('usage', {})
        if usage:
            result['metadata'].update({
                'input_tokens': usage.get('input_tokens'),
                'output_tokens': usage.get('output_tokens'),
                'cache_creation_input_tokens': usage.get('cache_creation_input_tokens'),
                'cache_read_input_tokens': usage.get('cache_read_input_tokens')
            })
        
        # Extract text content
        content = data.get('content', [])
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))
            result['full_text'] = ''.join(text_parts)
        
        result['raw_data'] = data
        return result
        
    except json.JSONDecodeError:
        return None

def parse_response_body(body_str):
    """Parse response body - try streaming first, then JSON"""
    if not body_str:
        return {
            'format': 'empty',
            'full_text': '',
            'metadata': {},
            'error': 'Empty response body'
        }
    
    # Try streaming format first
    streaming_result = parse_streaming_response(body_str)
    if streaming_result:
        return streaming_result
    
    # Try regular JSON format
    json_result = parse_json_response(body_str)
    if json_result:
        return json_result
    
    # Fallback - treat as raw text
    return {
        'format': 'raw',
        'full_text': body_str[:500] + ('...' if len(body_str) > 500 else ''),
        'metadata': {},
        'raw_length': len(body_str)
    }

def extract_responses(log_file, output_file):
    """Extract and analyze all responses"""
    
    stats = {
        'total_lines': 0,
        'valid_json': 0,
        'invalid_json': 0,
        'responses': 0,
        'streaming_responses': 0,
        'json_responses': 0,
        'empty_responses': 0,
        'errors': []
    }
    
    with open(output_file, 'w') as out:
        out.write("# Claude API Responses Analysis\n\n")
        out.write("*Parsed responses from both streaming and JSON formats*\n\n")
        out.write("---\n\n")
        
        response_count = 0
        
        with open(log_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                stats['total_lines'] += 1
                
                # Validate JSON
                data, error = validate_json_line(line)
                
                if error:
                    stats['invalid_json'] += 1
                    if len(stats['errors']) < 10:
                        stats['errors'].append(f"Line {line_num}: {error}")
                    continue
                
                stats['valid_json'] += 1
                
                # Only process responses
                if data['type'] != 'RESPONSE':
                    continue
                
                stats['responses'] += 1
                response_count += 1
                
                timestamp = format_timestamp(data['timestamp'])
                url = data['url']
                status = data.get('status', 'Unknown')
                status_text = data.get('statusText', '')
                
                out.write(f"## Response #{response_count}\n\n")
                out.write(f"**Time:** {timestamp}  \n")
                out.write(f"**Status:** {status} {status_text}  \n")
                out.write(f"**URL:** `{url}`  \n\n")
                
                # Parse response body
                body = data.get('body', '')
                parsed = parse_response_body(body)
                
                # Update stats
                if parsed['format'] == 'streaming':
                    stats['streaming_responses'] += 1
                elif parsed['format'] == 'json':
                    stats['json_responses'] += 1
                elif parsed['format'] == 'empty':
                    stats['empty_responses'] += 1
                
                out.write(f"**Format:** {parsed['format'].title()}  \n")
                
                # Show metadata
                metadata = parsed.get('metadata', {})
                if metadata:
                    out.write("\n### Metadata\n\n")
                    for key, value in metadata.items():
                        if value is not None:
                            out.write(f"- **{key}:** `{value}`\n")
                    out.write("\n")
                
                # Show response headers (key ones)
                headers = data.get('headers', {})
                if headers:
                    out.write("### Key Response Headers\n\n")
                    key_headers = ['content-type', 'anthropic-ratelimit-unified-status', 'request-id']
                    for key in key_headers:
                        if key in headers:
                            out.write(f"- **{key}:** `{headers[key]}`\n")
                    out.write(f"- **Total Headers:** {len(headers)}\n\n")
                
                # Show response content
                full_text = parsed.get('full_text', '')
                if full_text:
                    out.write("### Response Content\n\n")
                    if len(full_text) > 1000:
                        out.write(f"```\n{full_text[:1000]}\n...\n```\n\n")
                        out.write(f"*Truncated - Full length: {len(full_text)} characters*\n\n")
                    else:
                        out.write(f"```\n{full_text}\n```\n\n")
                elif 'error' in parsed:
                    out.write(f"**Error:** {parsed['error']}\n\n")
                else:
                    out.write("**No text content found**\n\n")
                
                # Show streaming events summary for streaming responses
                if parsed['format'] == 'streaming' and 'events' in parsed:
                    events = parsed['events']
                    event_types = {}
                    for event in events:
                        event_type = event.get('event', 'unknown')
                        event_types[event_type] = event_types.get(event_type, 0) + 1
                    
                    out.write("### Streaming Events Summary\n\n")
                    for event_type, count in event_types.items():
                        out.write(f"- **{event_type}:** {count}\n")
                    out.write(f"- **Total Events:** {len(events)}\n\n")
                
                # Show body size
                body_size = len(body) if body else 0
                out.write(f"**Response Size:** {body_size:,} characters\n\n")
                
                out.write("---\n\n")
        
        # Write stats
        out.write("## Processing Statistics\n\n")
        out.write(f"- **Total Lines:** {stats['total_lines']}\n")
        out.write(f"- **Valid JSON:** {stats['valid_json']}\n")
        out.write(f"- **Invalid JSON:** {stats['invalid_json']}\n")
        out.write(f"- **Total Responses:** {stats['responses']}\n")
        out.write(f"- **Streaming Responses:** {stats['streaming_responses']}\n")
        out.write(f"- **JSON Responses:** {stats['json_responses']}\n")
        out.write(f"- **Empty Responses:** {stats['empty_responses']}\n")
        
        if stats['errors']:
            out.write(f"\n### First {len(stats['errors'])} Errors\n\n")
            for error in stats['errors']:
                out.write(f"- {error}\n")

if __name__ == "__main__":
    log_file = "/root/claude-api.log"  # Use root log by default
    output_file = "responses-analysis.md"
    
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    try:
        extract_responses(log_file, output_file)
        print(f"✅ Responses analyzed and saved to {output_file}")
    except FileNotFoundError:
        print(f"❌ Log file '{log_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)