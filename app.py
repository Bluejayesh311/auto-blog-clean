from flask import Flask, render_template, request, redirect, url_for, flash
from pytrends.request import TrendReq
from openai import OpenAI
import requests
from requests.auth import HTTPBasicAuth
import threading
import time
import os

app = Flask(__name__)
app.secret_key = 'replace_this_with_a_secure_random_key'

# Initialize OpenAI client with your API key from environment
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# WordPress credentials from environment variables
WP_URL = os.getenv('WP_URL')          # e.g. https://yourdomain.com/wp-json/wp/v2/posts
WP_USER = os.getenv('WP_USER')
WP_APP_PASSWORD = os.getenv('WP_APP_PASSWORD')

logs = []

def log(message):
    print(message)
    logs.append(message)
    if len(logs) > 50:
        logs.pop(0)

def get_related_keywords(base_keyword, max_keywords=5):
    log(f"Fetching related keywords for '{base_keyword}' ...")
    pytrends = TrendReq(hl='en-US', tz=360)
    try:
        pytrends.build_payload([base_keyword], timeframe='today 12-m')
        related_queries = pytrends.related_queries()
        top = related_queries.get(base_keyword, {}).get('top')
        if top is not None:
            keywords = top['query'].head(max_keywords).tolist()
            log(f"Found related keywords: {keywords}")
            return keywords
    except Exception as e:
        log(f"Error fetching keywords: {e}")
    log("Using base keyword as fallback")
    return [base_keyword]

def generate_content(keyword):
    log(f"Generating content for '{keyword}' ...")
    prompt = f"Write a detailed, SEO optimized blog post about '{keyword}'. Include headings and subheadings."
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200,
            temperature=0.7
        )
        content = response.choices[0].message.content.strip()
        log(f"Content generated for '{keyword}'.")
        return content
    except Exception as e:
        log(f"Error generating content: {e}")
        return ""

def post_to_wordpress(title, content):
    log(f"Posting to WordPress: {title}")
    post_data = {
        'title': title,
        'content': content,
        'status': 'publish'  # use 'draft' if you want to review posts first
    }
    try:
        response = requests.post(
            WP_URL,
            json=post_data,
            auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD)
        )
        if response.status_code == 201:
            log(f"Post '{title}' published successfully.")
        else:
            log(f"Failed to publish '{title}': {response.status_code} {response.text}")
    except Exception as e:
        log(f"Error posting to WordPress: {e}")

def run_generation(base_keyword, num_posts):
    keywords = get_related_keywords(base_keyword, num_posts)
    for kw in keywords:
        content = generate_content(kw)
        if content:
            post_to_wordpress(kw, content)
        time.sleep(5)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        base_keyword = request.form.get('keyword')
        num_posts = int(request.form.get('num_posts'))
        if not base_keyword or num_posts < 1:
            flash("Please enter a valid keyword and number of posts.")
            return redirect(url_for('index'))

        threading.Thread(target=run_generation, args=(base_keyword, num_posts)).start()
        flash(f"Started generating {num_posts} posts for '{base_keyword}'. Check logs below.")
        return redirect(url_for('index'))
    return render_template('index.html', logs=logs)

if __name__ == '__main__':
    app.run(debug=True)



