import sys
import os
import json
import plistlib
import requests
import argparse
import re
from urllib.parse import urlparse, parse_qs
from datetime import date
import logging
from string import Template
from readability import Document
from html2text import html2text
from openai import OpenAI

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

openai_client = OpenAI()

# Paths
BOOKMARKS_PLIST_PATH = os.path.expanduser('~/Library/Safari/Bookmarks.plist')
BOOKMARKS_FOLDER_NAME = 'Squirrel'
TEMPLATE_PATH = 'template.md'
current_date = date.today()
OUTPUT_PATH = os.path.expanduser(f'~/Documents/Squirrel Archive/')


def output_folder(year, month):
    folder = f'{OUTPUT_PATH}/{year}/{month}/'
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder

def get_bookmarks(folder_name):
    # Retrieve URLs from the specified Safari bookmarks folder.
    with open(BOOKMARKS_PLIST_PATH, 'rb') as f:
        plist_data = plistlib.load(f)
    
    def find_folder(bookmarks, folder_name):
        #Recursively search for the folder in the bookmarks.
        for item in bookmarks:
            if item.get('Title') == folder_name and item.get('WebBookmarkType') == 'WebBookmarkTypeList':
                return item.get('Children', [])
        return []

    # Find the folder and extract URLs
    root = plist_data.get('Children', [])
    folder = find_folder(root, folder_name)
    urls = [item.get('URLString') for item in folder if item.get('WebBookmarkType') == 'WebBookmarkTypeLeaf']
    return urls

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
    

def delete_bookmark(folder_name, url_to_remove):
    # Remove a URL from a specific folder in Safari's Bookmarks.plist.
    with open(BOOKMARKS_PLIST_PATH, 'rb') as f:
        plist_data = plistlib.load(f)

    def find_and_remove(bookmarks, folder_name, url):
        # Recursively find the folder and remove the URL.
        for item in bookmarks:
            # Check if the item is the target folder
            if item.get('Title') == folder_name and item.get('WebBookmarkType') == 'WebBookmarkTypeList':
                # Filter out the URL to remove
                item['Children'] = [child for child in item['Children'] if child.get('URLString') != url]
                return True  # Found and removed the URL
            # Recursively check nested folders
            if 'Children' in item:
                if find_and_remove(item['Children'], folder_name, url):
                    return True
        return False

    # Attempt to find and remove the URL
    if find_and_remove(plist_data['Children'], folder_name, url_to_remove):
        with open(BOOKMARKS_PLIST_PATH, 'wb') as f:
            plistlib.dump(plist_data, f)
        logging.info(f"  Successfully removed {url_to_remove} from folder '{folder_name}'.")
    else:
        logging.info(f"  URL {url_to_remove} not found in folder '{folder_name}'.")

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
        urls = get_bookmarks(BOOKMARKS_FOLDER_NAME)
        if not urls:
            logging.info("No URLs found in the bookmarks folder.")
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
            if args.url is None:
                delete_bookmark(BOOKMARKS_FOLDER_NAME, url)
            logging.info(f"  Successfully processed: {url}")
        except Exception as e:
            logging.error(f"  Error processing {url}: {e}, occurred at {e.__traceback__.tb_frame.f_globals['__file__']} line {e.__traceback__.tb_lineno}")

if __name__ == "__main__":
    main()
