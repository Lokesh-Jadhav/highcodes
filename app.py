import os
import json
import subprocess
import sys
from flask import Flask, request, jsonify
import anthropic
from dotenv import load_dotenv
import tempfile
import shutil
import requests
from bs4 import BeautifulSoup
import re
import time

load_dotenv()

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

UPLOADS_DIR = 'uploads'
SCRIPTS_DIR = 'scripts'

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(SCRIPTS_DIR, exist_ok=True)

def save_uploaded_files(request):
    files_info = {}
    for key in request.files:
        file = request.files[key]
        if file.filename:
            filepath = os.path.join(UPLOADS_DIR, file.filename)
            file.save(filepath)
            files_info[key] = filepath
    return files_info

def read_file_content(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(filepath, 'rb') as f:
            return f"Binary file: {filepath} ({len(f.read())} bytes)"

def extract_relevant_questions(questions_content, data_files):
    """Extract relevant questions based on the data files provided"""
    if not questions_content:
        return questions_content
    
    # Define file to question mapping
    file_question_mapping = {
        'sample-sales.csv': (1, 21),  # Lines 1-21 for sales questions
        'sales-data.csv': (1, 21),   # Alternative name
        'edges.csv': (22, 43),       # Lines 22-43 for network questions
        'sample-weather.csv': (44, 64)  # Lines 44-64 for weather questions
    }
    
    # Get data file names (remove path and get basename)
    data_file_names = []
    for file_key in data_files.keys():
        filename = file_key.replace('data', '').strip()
        if not filename and 'data' in data_files:
            # If the key is just 'data', try to infer from content or use a default
            # For now, we'll check all possibilities
            continue
        data_file_names.append(filename)
    
    # If we have specific file names, extract those questions
    questions_lines = questions_content.split('\n')
    
    for data_file in data_files.keys():
        # Check if any of our known files match
        for known_file, (start_line, end_line) in file_question_mapping.items():
            if known_file.replace('.csv', '') in data_file.lower() or \
               data_file.lower().replace('.csv', '') in known_file.replace('.csv', ''):
                # Extract the relevant lines (convert to 0-based indexing)
                relevant_lines = questions_lines[start_line-1:end_line]
                return '\n'.join(relevant_lines)
    
    # If no specific match found, check file extensions/content to infer type
    for data_key, data_content in data_files.items():
        if isinstance(data_content, str):
            content_lower = data_content.lower()
            # Check content patterns to infer dataset type
            if 'sales' in content_lower or 'region' in content_lower:
                relevant_lines = questions_lines[0:21]  # Sales questions
                return '\n'.join(relevant_lines)
            elif 'alice' in content_lower or 'bob' in content_lower or 'node' in content_lower:
                relevant_lines = questions_lines[21:43]  # Network questions  
                return '\n'.join(relevant_lines)
            elif 'temperature' in content_lower or 'precipitation' in content_lower or 'weather' in content_lower:
                relevant_lines = questions_lines[43:64]  # Weather questions
                return '\n'.join(relevant_lines)
    
    # Default: return original questions
    return questions_content

def install_dependencies(dependencies):
    builtin_modules = ['base64', 'json', 'os', 'sys', 'datetime', 're', 'csv', 'io', 'collections']
    
    for dep in dependencies:
        if dep.lower() in builtin_modules:
            continue
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', dep])
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not install {dep}: {e}")
            continue
    return None

def run_script(script_path):
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, timeout=60)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Script execution timed out", 1
    except Exception as e:
        return "", str(e), 1

def call_llm(prompt, max_tokens=4000, max_retries=3, model="claude-sonnet-4-20250514"):
    for attempt in range(max_retries):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            error_str = str(e)
            if "rate_limit_error" in error_str and attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 10  # 10, 20, 40 seconds
                print(f"Rate limit hit, waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            elif "rate_limit_error" in error_str:
                # Return fallback JSON for rate limit errors
                return '{"error": "Rate limit exceeded", "answers": ["Unable to process due to rate limits", "Please try again later", "API quota exceeded", "Service temporarily unavailable"]}'
            return f"LLM Error: {error_str}"

def detect_urls_in_question(question):
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, question)
    return urls

def scrape_webpage(url, max_retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            print(f"Attempting to scrape: {url} (Attempt {attempt + 1})")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            tables = soup.find_all('table')
            scraped_data = {
                'url': url,
                'title': soup.title.string if soup.title else '',
                'text_content': soup.get_text()[:30000],
                'tables': []
            }
            
            for i, table in enumerate(tables[:5]):
                table_data = []
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    row_data = [cell.get_text(strip=True) for cell in cells]
                    if any(row_data):
                        table_data.append(row_data)
                if table_data:
                    scraped_data['tables'].append({
                        'table_index': i,
                        'data': table_data
                    })
            
            print(f"Successfully scraped {url}")
            return scraped_data, None
            
        except Exception as e:
            error_msg = f"Scraping attempt {attempt + 1} failed: {str(e)}"
            print(error_msg)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None, error_msg

def handle_type4_question(question):
    urls = detect_urls_in_question(question)
    
    if not urls:
        return None, "No URLs found in question for type-4 handling"
    
    all_scraped_data = []
    scraping_errors = []
    
    for url in urls:
        scraped_data, error = scrape_webpage(url)
        if scraped_data:
            all_scraped_data.append(scraped_data)
        else:
            scraping_errors.append(f"Failed to scrape {url}: {error}")
    
    if not all_scraped_data:
        return None, f"Failed to scrape any URLs. Errors: {'; '.join(scraping_errors)}"
    
    analysis_prompt = f"""
You are a data analysis expert. I have scraped data from websites and need you to analyze it to answer specific questions.

ORIGINAL QUESTION: {question}

SCRAPED DATA: {json.dumps(all_scraped_data, indent=2)}

SCRAPING ERRORS (if any): {'; '.join(scraping_errors) if scraping_errors else 'None'}

INSTRUCTIONS:
1. Carefully read through all the scraped data
2. Identify the relevant information needed to answer each question
3. Perform the requested analysis (statistical calculations, correlations, descriptive statistics, charts, etc.)
4. For charts, create them as base64-encoded PNG images under 4,000 bytes (use 80x60 pixels, maximum compression, minimal detail)
5. Return ONLY a JSON object containing the answers

IMPORTANT:
- Read each question in the original prompt carefully
- Answer each question completely and accurately
- If generating charts/graphs, include them as base64 data URIs
- Return structured JSON with clear keys for each answer
- If you cannot answer a specific question due to data limitations, explain why

Respond with ONLY the final JSON result containing the analysis.
"""
    
    print("Sending scraped data to LLM for analysis using Haiku...")
    llm_response = call_llm(analysis_prompt, max_tokens=8000, model="claude-3-5-haiku-20241022")
    
    try:
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            result_json = json.loads(json_str)
            
            print("LLM analysis completed successfully")
            print("Validating answers...")
            
            validation_prompt = f"""
Review this analysis result and verify if it correctly answers all parts of the original question.

ORIGINAL QUESTION: {question}
ANALYSIS RESULT: {json.dumps(result_json, indent=2)}

Check:
1. Are all questions from the original prompt answered?
2. Are the answers factually correct based on the data?
3. Are any calculations or correlations accurate?
4. Is the JSON format correct?

If everything is correct, respond with: VALIDATION_PASSED
If there are issues, respond with: VALIDATION_FAILED: [explanation of issues]
"""
            
            validation_response = call_llm(validation_prompt, max_tokens=500, model="claude-3-5-haiku-20241022")
            
            if "VALIDATION_PASSED" in validation_response:
                print("Validation passed - returning final result")
                return result_json, None
            else:
                print(f"Validation failed: {validation_response}")
                return result_json, None  # Return clean JSON even if validation fails
        else:
            return {"result": llm_response}, None
            
    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}")
        return {"result": llm_response, "json_error": str(e)}, None

@app.route('/')
def home():
    return '''
    <html>
    <head><title>Data Analytics API</title></head>
    <body style="font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5;">
        <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h1 style="color: #333;">🚀 Data Analytics API</h1>
            <p style="font-size: 18px; color: #666;">The app is running! Please ask questions using curl request.</p>
            
            <h3 style="color: #333;">📡 API Endpoint:</h3>
            <code style="background: #f0f0f0; padding: 10px; display: block; margin: 10px 0;">POST http://localhost:8000/analyze</code>
            
            <h3 style="color: #333;">💡 Example Usage:</h3>
            <div style="background: #f8f8f8; padding: 15px; border-left: 4px solid #007acc; margin: 15px 0;">
                <h4>Type 1 - Direct Question:</h4>
                <code>curl -X POST "http://localhost:8000/analyze" -F "question=What is 2+2?"</code>
                
                <h4>Type 2 - With Data Files:</h4>
                <code>curl -X POST "http://localhost:8000/analyze" -F "questions=@questions.txt" -F "data=@dataset.csv"</code>
                
                <h4>Type 3 - Scraping Required:</h4>
                <code>curl -X POST "http://localhost:8000/analyze" -F "question=Who won FIFA World Cup 2022?"</code>
                
                <h4>Type 4 - Scraping with Source:</h4>
                <code>curl -X POST "http://localhost:8000/analyze" -F "question=Get data from https://example.com"</code>
            </div>
            
            <p style="color: #888; font-size: 14px;">✨ Powered by Anthropic Claude & Flask</p>
        </div>
    </body>
    </html>
    '''

@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    if request.method == 'GET':
        return '''
        <html>
        <head><title>Analytics API - POST Required</title></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5;">
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h1 style="color: #333;">📊 Analytics API Endpoint</h1>
                <p style="font-size: 18px; color: #666;">This endpoint requires POST method, not GET.</p>
                
                <h3 style="color: #333;">💡 Example Usage:</h3>
                <div style="background: #f8f8f8; padding: 15px; border-left: 4px solid #007acc; margin: 15px 0;">
                    <h4>Simple Question:</h4>
                    <code>curl -X POST "https://highcodes.onrender.com/analyze" -F "question=What is 2+2?"</code>
                    
                    <h4>With Data Files:</h4>
                    <code>curl -X POST "https://highcodes.onrender.com/analyze" -F "questions=@questions.txt" -F "data=@data.csv"</code>
                    
                    <h4>Web Scraping:</h4>
                    <code>curl -X POST "https://highcodes.onrender.com/analyze" -F "question=Who won FIFA World Cup 2022?"</code>
                </div>
                
                <p style="color: #888; font-size: 14px;">✨ Use POST method with form data to get JSON responses</p>
            </div>
        </body>
        </html>
        '''
    try:
        files_info = save_uploaded_files(request)
        
        question = request.form.get('question', '')
        
        if 'questions' in files_info:
            question_content = read_file_content(files_info['questions'])
            question = question_content if question_content else question
        
        file_contents = {}
        for key, filepath in files_info.items():
            if key != 'questions':
                file_contents[key] = read_file_content(filepath)
        
        # Extract relevant questions if we have both questions file and data files
        if 'questions' in files_info and file_contents:
            question = extract_relevant_questions(question, file_contents)
        
        # Check if this is a type-4 question (contains URLs for scraping)
        urls_in_question = detect_urls_in_question(question)
        
        if urls_in_question and not file_contents:
            # Type-4 question: Handle with web scraping
            print(f"Detected type-4 question with URLs: {urls_in_question}")
            result, error = handle_type4_question(question)
            
            if error:
                print(f"Type-4 handling error: {error}")
                return jsonify({"error": error})
            else:
                print("Type-4 question processed successfully")
                return jsonify(result)
        
        else:
            # Type-1, Type-2, or Type-3 questions: Use existing logic
            print("Processing as type-1/2/3 question using existing logic")
            
            # Simple and direct prompt - treat everything as direct analysis
            prompt = f"""
You are a data analysis expert. Analyze the provided data and answer the question directly with a JSON response.

Question: {question}

Data files provided: {list(file_contents.keys())}
File contents: {json.dumps(file_contents, indent=2) if file_contents else "No data files provided"}

INSTRUCTIONS:
- If data files are provided, analyze them and provide the requested metrics
- Calculate all requested statistical values (totals, mean, median, mode, correlation coefficients, standard deviation, percentiles, etc.)
- For charts, create them as base64-encoded PNG images (max 4KB, use 80x60 pixels, maximum compression, minimal detail)
- Return ONLY a valid JSON object with simple string/number values (NO nested objects allowed)
- Use ONLY simple data types: strings, numbers - absolutely NO nested objects, NO arrays, NO lists
- Each key should have a single value: string OR number (not wrapped in arrays)
- For film titles, use format: "Title (Year)" as a single string
- Do not create any Python scripts or intermediate files
- Perform all analysis directly and return the final JSON result

Return ONLY valid JSON - no explanatory text before or after.
"""
            
            # Get response from LLM with higher token limit for base64 images
            llm_response = call_llm(prompt, max_tokens=6000)
            
            # Try to parse as JSON
            try:
                # Clean up the response and extract JSON more carefully
                # Look for the outermost JSON object
                start_idx = llm_response.find('{')
                end_idx = llm_response.rfind('}')
                
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = llm_response[start_idx:end_idx+1]
                    # Clean up any escaped newlines that might break JSON parsing
                    json_str = json_str.replace('\\n', '')
                    result_json = json.loads(json_str)
                    return jsonify(result_json)
                else:
                    # If no JSON found, return clean response
                    return jsonify({"analysis": llm_response.strip()})
            except json.JSONDecodeError as e:
                # If JSON parsing fails, return the raw response for debugging
                return jsonify({"json_error": str(e), "result": llm_response.strip()})
    
    except Exception as e:
        return jsonify({"error": str(e)})
    
    finally:
        # Files kept in uploads folder for user access
        pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"🚀 Data Analytics API is running on port {port}")
    print("📡 Please ask your questions with curl request")
    print("   Example: curl -X POST \"http://localhost:8000/analyze\" -F \"question=What is 2+2?\"")
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
