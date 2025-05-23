import os
import traceback
import json
import logging
import requests
from string import Template
from urllib.parse import urlparse
from dotenv import load_dotenv
from pyairtable import Api
from openai import OpenAI

# Configure logging
logging.basicConfig(filename="script.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
AIRTABLE_API = os.getenv('AIRTABLE_API')
AIRTABLE_BASE = os.getenv('AIRTABLE_BASE')
AIRTABLE_TABLE = os.getenv('AIRTABLE_TABLE')
TEMPLATE_PATH = 'template.md'
OUTPUT_FOLDER = os.path.expanduser("~/Documents/Squirrel Archive/")
GTS_URL = "https://gts.invisibleparade.com/api/v1/"
GTS_TOKEN = os.getenv('GTS_TOKEN')

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

    if response.choices and response.choices[0].message and response.choices[0].message.content:
        result = json.loads(response.choices[0].message.content)
        summary, tags = result["summary"], result["tags"]
        return summary, tags
    else:
        logging.error("OpenAI response did not contain expected content")
        return "Summary unavailable", ["error"]

def get_saved_articles():
    if not AIRTABLE_API or not AIRTABLE_BASE or not AIRTABLE_TABLE:
        logging.error("Missing required Airtable environment variables")
        return []

    try:
        api = Api(api_key=AIRTABLE_API)
        table = api.table(base_id=AIRTABLE_BASE, table_name=AIRTABLE_TABLE)
        articles = table.all()
        return articles
    except Exception as e:
        logging.error(f"Error fetching articles from Airtable: {e}")
        return []

def create_output_path(article_data):
    folder_path = f'{OUTPUT_FOLDER}{article_data["Domain"]}/'
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    url_path = urlparse(article_data["URL"]).path.replace('/', '_')
    return os.path.join(folder_path, f"{url_path}.md")


def create_output_file(article_data):
    output_path = create_output_path(article_data)
    if os.path.exists(output_path):
        logging.info(f"{output_path} already exists, skipping...")
        return 'skipped'

    summary, tags = query_openai(article_data["Article text"])
    tags_yaml = "\n".join([f"  - {tag.lower().replace(' ', '_')}" for tag in tags])

    data = {
        "title": article_data["Title"],
        "url": article_data["URL"],
        "domain": article_data["Domain"],
        "summary": summary,
        "tags_yaml": tags_yaml,
        "saved_date": article_data["Date"],
        "content": article_data["Article text"]
    }

    with open(TEMPLATE_PATH) as f:
        template = Template(f.read())
    output = template.substitute(data)

    with open(output_path, 'w') as f:
        f.write(output)
        logging.info(f"Wrote {output_path}")
        return 'saved'

def batch_delete_articles(article_ids):
    if not AIRTABLE_API or not AIRTABLE_BASE or not AIRTABLE_TABLE:
        logging.error("Missing required Airtable environment variables")
        return

    try:
        api = Api(api_key=AIRTABLE_API)
        table = api.table(base_id=AIRTABLE_BASE, table_name=AIRTABLE_TABLE)
        table.batch_delete(article_ids)
        logging.info(f"Deleted {len(article_ids)} articles from Airtable")
    except Exception as e:
        logging.error(f"Error deleting articles from Airtable: {e}")

def post_to_gts(status_update):
    gts_headers = {'Authorization': f'Bearer {GTS_TOKEN}'}
    post_response = requests.post(GTS_URL + "statuses", headers=gts_headers, data={"status": status_update})
    if post_response.status_code == 200:
        logging.info("Posted to GTS successfully.")
    else:
        logging.error("Posting to GTS failed: " + post_response.text)


def main():
    articles = get_saved_articles()
    results = {
        "saved": [],
        "skipped": [],
        "failed": [],
    }
    processed_article_ids = []
    for article in articles:
        try:
            r = create_output_file(article['fields'])
            if r == 'saved':
                results["saved"].append(article['fields']["URL"])
            elif r == 'skipped':
                results["skipped"].append(article['fields']["URL"])
            processed_article_ids.append(article["id"])
        except Exception as e:
            error_info = traceback.format_exc()
            logging.error(f"{article['fields']['URL']}: {e}\n{error_info}")
            results["failed"].append(f"{article['fields']['URL']}: {e}")

    if len(processed_article_ids) > 0:
        batch_delete_articles(processed_article_ids)

    status_update = f"{len(results['saved'])} articles saved: \n"
    status_update += ("\n").join(sorted(results['saved']))
    status_update += f"\n\n{len(results['skipped'])} articles skipped: \n"
    status_update += ("\n").join(sorted(results['skipped']))
    status_update += f"\n\n{len(results['failed'])} articles failed: \n"
    status_update += ("\n").join(sorted(results['failed']))

    post_to_gts(status_update)


if __name__ == "__main__":
    main()
