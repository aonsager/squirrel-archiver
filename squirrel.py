import os
import sys
import json
import logging
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
OUTPUT_FOLDER = os.path.expanduser(f'~/Documents/Squirrel Archive/')

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

def get_saved_articles():
    api = Api(AIRTABLE_API)
    table = api.table(AIRTABLE_BASE, AIRTABLE_TABLE)
    articles = table.all()
    return articles

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
    api = Api(AIRTABLE_API)
    table = api.table(AIRTABLE_BASE, AIRTABLE_TABLE)
    table.batch_delete(article_ids)
    logging.info(f"Deleted {len(article_ids)} articles from Airtable")
    

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
            logging.error(f"{article['fields']['URL']}: {e}. Occurred at {e.__traceback__.tb_frame.f_globals['__file__']} line {e.__traceback__.tb_lineno}")
            results["failed"].append(f"{article['fields']['URL']}: {e}")

    if len(processed_article_ids) > 0:
        batch_delete_articles(processed_article_ids)

    print(f"{len(results["saved"])} articles saved: ")
    print(f"{("\n").join(sorted(results["saved"]))}")
    print(f"\n{len(results["skipped"])} articles skipped: ")
    print(f"{("\n").join(sorted(results["skipped"]))}")
    print(f"\n{len(results["failed"])} articles failed: ")
    print(f"{("\n").join(sorted(results["failed"]))}")
    

if __name__ == "__main__":
    main()
