# Squirrel

![Squirrel](squirrel.png?raw=true)

A simple script that saves article text into a local folder for archive and search.  
I will be writing a blog post about the motivation behind this project.

Disclaimer: I wrote this just for my personal use, so it's probably written fairly poorly. Feel free to fork, but please use at your own discretion.

# Installation

```
git clone git@github.com:aonsager/squirrel-archiver.git
cd squirrel-archiver
pip install virtualenv
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

# Usage

```python squirrel.py```

By default the script will look at a specified folder in your Safari bookmarks (default is "Squirrel") and process each URL there. After processing successfully, the bookmark will be removed from the folder.

The bookmark folder is specified inside the script with `BOOKMARKS_FOLDER_NAME` and the current date is used as the saved date.

Alternatively, you can specify a URL directly, as well as a saved date.

```python squirrel.py -u https://www.example.com -d 2000-01-01```

# Archiving

You can modify `template.md` to change the format of the file that is saved. There is some basic YAML front matter, followed by the main article body.

The outputted file is saved in the `OUTPUT_PATH` directory, with subcategories for the year and month.

The logic for finding the main text is very simple, so some sites may not work very well. There is also a chance of being blocked by Cloudflare etc. because I'm not doing anything to spoof user agents. I think trying to fix this programmatically is overkill and will instead fix any problems manually as they come up.   
It may be worth it to at least have some sort of detection for when intervention is needed.

# Summary and tagging by AI

I have a function that uses ChatGPT to generate summaries for each article, as well as 10 tags based on the content. Both of these are included in the YAML front matter.

## ChatGPT usage
Creating the OpenAI object looks for an `OPENAI_API_KEY` environment variable, so be sure to set this if you're going to be using it ([docs reference](https://github.com/openai/openai-python?tab=readme-ov-file#usage)).

# Browse and search

I open the directory in [Obsidian](https://obsidian.md), which lets me search the contents, and see a graph of connected pages via common tags.