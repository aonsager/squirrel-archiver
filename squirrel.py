import sys
import os
import json
import requests
import argparse
from urllib.parse import urlparse, parse_qs
from datetime import date
import logging
from string import Template
from readability import Document
from html2text import html2text
from openai import OpenAI

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Paths
TEMPLATE_PATH = 'template.md'
current_date = date.today()
URLS_PATH = os.path.expanduser(f'~/Documents/Squirrel Archive/urls.txt')
BADURLS_PATH = os.path.expanduser(f'~/Documents/Squirrel Archive/badurls.txt')
OUTPUT_PATH = os.path.expanduser(f'~/Documents/Squirrel Archive/')


def output_folder(year, month):
    folder = f'{OUTPUT_PATH}/{year}/{month}/'
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder

def extract_youtube_video_id(url):
    # Check if the URL is a valid YouTube link
    youtube_domains = ['youtube.com', 'youtu.be']
    parsed_url = urlparse(url)
    
    if any(domain in parsed_url.netloc for domain in youtube_domains):
        # Handle standard YouTube URLs
        if 'youtube.com' in parsed_url.netloc:
            query_params = parse_qs(parsed_url.query)
            return query_params.get('v', [None])[0]
        # Handle shortened YouTube URLs
        elif 'youtu.be' in parsed_url.netloc:
            return parsed_url.path.lstrip('/')
    return None

def get_youtube_transcript(youtube_id):
    from youtube_transcript_api import YouTubeTranscriptApi
    summary = ""
    srt = YouTubeTranscriptApi.get_transcript(youtube_id)
    for i in srt:
        summary += f"{i['text']}\n"

    return summary

def fetch_content(url):
    try:
        response = requests.get(url)
    except requests.exceptions.RequestException as e:
        logging.error(f"  Error occurred while making a request to {url}: {e}")
        return None
    doc = Document(response.text)
    title = doc.title().replace('/', '_').replace(':', '-')

    # If it's a youtube video, use the transcript for the article body
    youtube_id = extract_youtube_video_id(url)
    if youtube_id:
        summary = get_youtube_transcript(youtube_id)
    else:
        summary = html2text(doc.summary())
    return summary, title

def query_openai(content):
    openai_client = OpenAI()
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "developer", 
                "content": "You create brief summaries of online articles and provide tags based on the contents."
            },
            {
                "role": "user", 
                "content": content
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "summary_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "description": "A brief summary of the article, within 30 words.",
                            "type": "string"
                        },
                        "tags": {
                            "description": "10 single-word tags based on the article contents. Include general topics as well as specific things that are mentioned.",
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                        },
                        "additionalProperties": False
                    }
                }
            }
        }
    )
    
    result = json.loads(response.choices[0].message.content)
    summary, tags = result["summary"], result["tags"]
    return summary, tags

def get_output_path(title, year, month):
    return os.path.join(output_folder(year, month), f"{title}.md")

def create_output_file(data, year, month):
    with open(TEMPLATE_PATH) as f:
        template = Template(f.read())
    tags_yaml = "\n".join([f"  - {tag.lower().replace(' ', '_')}" for tag in data['tags']])
    data['tags_yaml'] = tags_yaml
    output = template.substitute(data)
    output_path = get_output_path(data['title'], year, month)
    with open(output_path, 'w') as f:
        f.write(output)

def main():
    parser = argparse.ArgumentParser(description="By default, will look at a specified folder in your Safari bookmarks and process each URL with today's date.\nYou have the option to manually provide a url and date.")
    parser.add_argument('-u', '--url', help="Provide a single URL to process", type=str, default=None)
    parser.add_argument('-d', '--date', help="Manually set a saved date for the URL", type=str, default=None)

    args = parser.parse_args()

    if args.date is not None:
        date_string = args.date
    else:
        date_string = current_date.strftime("%Y-%m-%d")

    if args.url is not None:
        urls = [args.url]
    else:
        with open(URLS_PATH, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        if not urls:
            logging.info("No URLs found in urls.txt")
            return

    for url in urls:
        try:
            logging.info(f"Processing URL: {url}")
            year = date_string.split("-")[0]
            month = date_string.split("-")[1]
            output_path = get_output_path(url, year, month)

            # Check if the URL is already processed
            if os.path.exists(output_path):
                logging.info(f"  URL already processed")
            else:
                logging.info(f"  fetching content")
                content, title = fetch_content(url)
                summary, tags = query_openai(content)
                domain = urlparse(url).netloc
                data = {
                    "title": title,
                    "url": url,
                    "domain": domain,
                    "summary": summary,
                    "tags": tags,
                    "saved_date": date_string,
                    "content": content
                }
                logging.info(f"  creating output file")
                create_output_file(data, date_string.split("-")[0], date_string.split("-")[1])
            logging.info(f"  Successfully processed: {url}")
        except Exception as e:
            with open(BADURLS_PATH, 'a') as badurls:
                badurls.write(f"{url}\n")
            logging.error(f"  Error processing {url}: {e}, occurred at {e.__traceback__.tb_frame.f_globals['__file__']} line {e.__traceback__.tb_lineno}")

    if args.url is None:
            with open(URLS_PATH, 'w'):
                pass

if __name__ == "__main__":
    main()
