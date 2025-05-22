#!/usr/bin/env python3
"""
Sanitize sensitive data from Claude API logs before sharing
Remove auth tokens, user IDs, and other sensitive information
"""
import json
import sys
import re
from datetime import datetime

def sanitize_headers(headers):
    """Remove or mask sensitive headers"""
    if not headers:
        return headers
    
    sanitized = {}
    for key, value in headers.items():
        key_lower = key.lower()
        
        if key_lower == 'authorization':
            # Completely remove auth tokens
            sanitized[key] = "Bearer [REMOVED]"
        elif 'token' in key_lower or 'auth' in key_lower:
            # Remove any other token-related headers
            sanitized[key] = "[REMOVED]"
        elif key_lower in ['x-forwarded-for', 'x-real-ip', 'cf-connecting-ip']:
            # Remove IP addresses
            sanitized[key] = "[IP_REMOVED]"
        else:
            sanitized[key] = value
    
    return sanitized

def sanitize_request_body(body_str):
    """Remove sensitive data from request body"""
    if not body_str:
        return body_str
    
    try:
        body = json.loads(body_str)
        
        # Remove user ID if present
        if 'metadata' in body and 'user_id' in body['metadata']:
            body['metadata']['user_id'] = "[USER_ID_REMOVED]"
        
        # Sanitize messages - keep structure but remove personal info
        if 'messages' in body and isinstance(body['messages'], list):
            for message in body['messages']:
                if isinstance(message, dict) and 'content' in message:
                    content = message['content']
                    
                    # For string content, remove file paths and personal info
                    if isinstance(content, str):
                        message['content'] = sanitize_text_content(content)
                    
                    # For array content, sanitize each item
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and 'text' in item:
                                item['text'] = sanitize_text_content(item['text'])
        
        return json.dumps(body, indent=2, ensure_ascii=False)
        
    except json.JSONDecodeError:
        # If it's not JSON, sanitize as text
        return sanitize_text_content(body_str)

def sanitize_text_content(text):
    """Remove sensitive information from text content"""
    if not text:
        return text
    
    # Remove file paths that might contain usernames
    text = re.sub(r'/home/[^/\s]+', '/home/[USER]', text)
    text = re.sub(r'/Users/[^/\s]+', '/Users/[USER]', text)
    text = re.sub(r'C:\\Users\\[^\\]+', 'C:\\Users\\[USER]', text)
    
    # Remove potential email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REMOVED]', text)
    
    # Remove potential API keys or tokens (long alphanumeric strings)
    text = re.sub(r'\b[A-Za-z0-9]{32,}\b', '[TOKEN_REMOVED]', text)
    
    # Remove IP addresses
    text = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP_REMOVED]', text)
    
    return text

def sanitize_log_file(input_file, output_file):
    """Sanitize the entire log file"""
    
    stats = {
        'total_lines': 0,
        'processed': 0,
        'errors': 0,
        'sanitized_tokens': 0,
        'sanitized_user_ids': 0
    }
    
    with open(output_file, 'w') as out:
        with open(input_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                stats['total_lines'] += 1
                
                if not line.strip():
                    out.write(line)
                    continue
                
                try:
                    # Parse JSON
                    data = json.loads(line.strip())
                    
                    # Track what we're sanitizing
                    if 'headers' in data:
                        original_headers = data['headers']
                        if any('authorization' in str(h).lower() or 'token' in str(h).lower() 
                               for h in original_headers.keys()):
                            stats['sanitized_tokens'] += 1
                    
                    if 'body' in data and 'user_id' in str(data['body']):
                        stats['sanitized_user_ids'] += 1
                    
                    # Sanitize headers
                    if 'headers' in data:
                        data['headers'] = sanitize_headers(data['headers'])
                    
                    # Sanitize request body
                    if 'body' in data:
                        data['body'] = sanitize_request_body(data['body'])
                    
                    # Write sanitized JSON
                    out.write(json.dumps(data, separators=(',', ':')) + '\n')
                    stats['processed'] += 1
                    
                except json.JSONDecodeError:
                    # If not JSON, write as-is but sanitize text
                    sanitized_line = sanitize_text_content(line)
                    out.write(sanitized_line)
                    stats['errors'] += 1
                except Exception as e:
                    # Write original line if sanitization fails
                    out.write(line)
                    stats['errors'] += 1
    
    return stats

def sanitize_markdown_file(input_file, output_file):
    """Sanitize markdown files containing extracted logs"""
    
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Remove auth tokens from markdown
    content = re.sub(r'Bearer sk-[A-Za-z0-9_-]+', 'Bearer [REMOVED]', content)
    content = re.sub(r'Bearer [A-Za-z0-9_-]{7,}', 'Bearer [REMOVED]', content)
    
    # Remove user IDs
    content = re.sub(r'"user_id":\s*"[^"]*"', '"user_id": "[USER_ID_REMOVED]"', content)
    
    # Remove file paths
    content = re.sub(r'/home/[^/\s]+', '/home/[USER]', content)
    content = re.sub(r'/Users/[^/\s]+', '/Users/[USER]', content)
    
    # Remove potential tokens
    content = re.sub(r'\b[A-Za-z0-9]{32,}\b', '[TOKEN_REMOVED]', content)
    
    with open(output_file, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 sanitize_logs.py <input_file> <output_file>")
        print("Example: python3 sanitize_logs.py claude-api.log claude-api-clean.log")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    try:
        if input_file.endswith('.md') or output_file.endswith('.md'):
            # Sanitize markdown file
            sanitize_markdown_file(input_file, output_file)
            print(f"✅ Markdown file sanitized: {output_file}")
        else:
            # Sanitize JSON log file
            stats = sanitize_log_file(input_file, output_file)
            print(f"✅ Log file sanitized: {output_file}")
            print(f"   - Processed: {stats['processed']} lines")
            print(f"   - Sanitized tokens: {stats['sanitized_tokens']}")
            print(f"   - Sanitized user IDs: {stats['sanitized_user_ids']}")
            print(f"   - Errors: {stats['errors']}")
            
    except FileNotFoundError:
        print(f"❌ File not found: {input_file}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)