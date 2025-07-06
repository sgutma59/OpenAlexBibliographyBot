# How to Build a Bibliography Bot with Python and the OpenAlex API

This tutorial will guide you through creating a command-line bot that automatically fetches academic research papers from scholarly graphs and saves them as a bibliography in a CSV file. We'll be using the free OpenAlex API to find papers on any topic you choose. 

By the end, you'll have a script that can run searches like this from the command line:
`python3 openalex_bib_generator.py "algorithmic bias" --pages 10 --since 2018`

And your search will instantly output a `.csv` file full of relevant research, with doi, url, title, author, year, citation count, publication venue, concepts, and abstract.

The code can be modified to work with other open scholarly graphs like Semantic Scholar. Semantic Scholar has a fairly low rate limit if you do not use an API Key, so I didn't include it in this tutorial.

### Preliminaries

Before we start, make sure you have Python installed, and replace 'python3' with 'python' as needed. You will also need to install two popular Python libraries, `requests` and `pandas`. You can install them using pip:

```bash
pip install requests pandas
```
- **requests:** A library for making HTTP requests to websites and APIs.
- **pandas:** A library for data analysis and manipulation which we will use to organize our data and save it to a formatted csv.file.

---

## Step 1: Setting Up the Script and Imports

First, create a new Python file named `openalex_bib_generator.py`. This single file will contain all of our code.

At the top of the file, we will import the libraries we'll need and define the base URL for the OpenAlex API. 

Argparse allows us to create command-line interfaces and define arguments like topic, --pages, and --since, letting us run the script directly from the terminal selecting different search options (e.g., python openalex_bib_generator.py "AI ethics" --pages 5) without having to edit the code itself each time we want to change the search query.

```python
"""
openalex_bib_generator.py
------------------------

Bibliography generator using OpenAlex API for academic research
"""

import argparse
import time
from typing import List, Dict
from pathlib import Path
import pandas as pd
import requests

BASE_URL = "https://api.openalex.org/works"
```

## Step 2: Fetching Data from the API (`fetch_works`)

This is the core function of our bot. It will contact the OpenAlex API, search for a topic, and handle fetching multiple pages of results. It specifies a search `term` (like "machine learning"), the number of pages and results to get, and other filters. It loops for each page we want, builds the correct URL with our search parameters, and makes a `GET` request. Note that we optionally add a `time.sleep(1.0)` delay between our requests. This is to avoid sending too many requests too quickly and getting blocked.
Keep in mind that we are also building a command line interface with argparse that will allow us to change these values from the command line. So if we want to change the defaults in our code, we need to change them in argparse, as the defaults specified in building argparse override these when we do not specify a value in the command line for our query.

```python
def fetch_works(
    term: str,
    per_page: int = 25,
    max_pages: int = 2,
    extra_filter: str | None = None,
    polite_delay: float = 1.0,
) -> List[Dict]:
    """Return (max_pages × per_page) records that match *term*."""
    works: list[Dict] = []
    
    for page in range(max_pages):
        print(f"🔄 Fetching page {page + 1}...")
        params = {
            'search': term,
            'per-page': per_page,
            'page': page + 1
        }
        
        if extra_filter:
            params['filter'] = extra_filter
        
        try:
            r = requests.get(
                BASE_URL, 
                params=params,
                timeout=30, 
                headers={"User-Agent": "openalex-bib-generator/1.0"} # This is to identify our script and reduce our chance of being blocked.
            )
            
            # Debug: print the actual URL being called
            print(f"   URL: {r.url}")

            if r.status_code != 200:
                print(f"   Status: {r.status_code} - Error")
                print(f"   Response: {r.text}")
                break
            
            data = r.json()
            
            if 'results' in data and data['results']:
                works.extend(data['results'])
                print(f"✅ Page {page + 1}: Found {len(data['results'])} papers")
                if len(data['results']) < per_page:
                    print("   Reached end of results")
                    break
            else:
                print(f"❌ No results found on page {page + 1}")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching page {page + 1}: {e}")
            break
            
        time.sleep(polite_delay)
    
    return works
```

## Step 3: Cleaning the Data with Pandas (`to_dataframe`)

The data we get from the API is in JSON format, which we want to turn into a simple spreadsheet. This is where we use the `pandas` library.

This function will loop through each paper we fetched and pull out the specific pieces of information we care about: title, authors, publication year, etc. It then organizes this clean data into a pandas DataFrame.

```python
def to_dataframe(works: List[Dict]) -> pd.DataFrame:
    """Convert raw OpenAlex JSON to a tidy DataFrame."""
    rows = []
    
    for w in works:
        # Extract authors
        authors_list = []
        if w.get('authorships'):
            for authorship in w['authorships']:
                author = authorship.get('author', {})
                if author.get('display_name'):
                    authors_list.append(author['display_name'])
        
        # Extract venue information
        venue = ""
        if w.get('primary_location') and w['primary_location'].get('source'):
            venue = w['primary_location']['source'].get('display_name', '')
        elif w.get('host_venue') and w['host_venue'].get('display_name'):
            venue = w['host_venue']['display_name']
        
        # Extract publication year
        pub_year = ""
        if w.get('publication_year'):
            pub_year = w['publication_year']
        elif w.get('publication_date'):
            try:
                pub_year = w['publication_date'][:4]
            except:
                pub_year = ""
        
        # Check for open access
        open_access_url = ""
        if w.get('open_access') and w['open_access'].get('oa_url'):
            open_access_url = w['open_access']['oa_url']
        elif w.get('primary_location') and w['primary_location'].get('pdf_url'):
            open_access_url = w['primary_location']['pdf_url']
        
        # Extract DOI
        doi = ""
        if w.get('doi'):
            doi = w['doi'].replace('https://doi.org/', '')
        
        # Extract concepts/keywords
        concepts = []
        if w.get('concepts'):
            concepts = [c.get('display_name', '') for c in w['concepts'][:5]]  # Top 5 concepts
        
        rows.append({
            "title": w.get("display_name", ""),
            "year": pub_year,
            "authors": "; ".join(authors_list),
            "venue": venue,
            "citation_count": w.get("cited_by_count", 0),
            "openalex_id": w.get("id", "").replace('https://openalex.org/', ''),
            "doi": doi,
            "url": w.get("id", ""),
            "open_access_pdf": open_access_url,
            "concepts": "; ".join(concepts),
            "type": w.get("type", ""),
            "is_oa": w.get("open_access", {}).get("is_oa", False),
            "abstract": "Abstract available" if w.get("abstract_inverted_index") else "",
        })
    
    return pd.DataFrame(rows)
```

## Step 4: Building the Command-Line Interface (CLI)

To make our script easy to use, we give it a command-line interface using the `argparse` library. This allows users to pass in arguments like the search topic or the number of pages directly from the terminal, without having to edit the code.

This function defines all the arguments our script will accept.

```python

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Harvest OpenAlex papers and save a customized bibliography",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "machine learning"
  %(prog)s "natural language processing" --pages 3
  %(prog)s "computer vision" --since 2020
        """
    )

    p.add_argument("topic", nargs="?", default="machine learning",
                   help='Search term, e.g. "natural language processing"')
    p.add_argument("--pages", type=int, default=2,     
                   help="How many pages to fetch (default: 2)")
    p.add_argument("--per-page", type=int, default=25, 
                   help="Results per page, max 200 (default: 25)")
    p.add_argument("--since", metavar="YYYY", help="From this year (inclusive)")
    p.add_argument("--until", metavar="YYYY", help="Up to this year (inclusive)")
    p.add_argument("-o", "--output", help="Output filename (auto-generated if omitted)")
    
    return p
```

## Step 5: Putting It All Together

Finally, we need a main execution block. This code will only run when you execute the script directly from the command line.

This section orchestrates the whole process:
1.  It calls `build_arg_parser()` to read the user's command-line inputs.
2.  It calls `fetch_works()` with the user's topic to get the data.
3.  It passes that data to `to_dataframe()` to clean it.
4.  It generates a unique filename for the output.
5.  It uses the `.to_csv()` method from pandas to save the results.
6.  It prints a helpful summary to the screen.

```python
if __name__ == "__main__":
    args = build_arg_parser().parse_args()

    # Validate per_page limit (OpenAlex has a max of 200)
    if args.per_page > 200:
        print("⚠️  OpenAlex limits results to 200 per page. Setting to 200.")
        args.per_page = 200

    # Build date filter if --since or --until were used
    date_filters = []
    if args.since:
        date_filters.append(f"from_publication_date:{args.since}-01-01")
    if args.until:
        date_filters.append(f"to_publication_date:{args.until}-12-31")
    extra_filter = ",".join(date_filters) if date_filters else None

    # --- Main Workflow ---
    print(f"🔍 Searching OpenAlex for: '{args.topic}'")
    works = fetch_works(
        term=args.topic,
        per_page=args.per_page,
        max_pages=args.pages,
        extra_filter=extra_filter
    )

    if not works:
        print("\n❌ No results found. Exiting.")
        exit(1)

    df = to_dataframe(works)

    # --- Saving the Output ---
    if args.output:
        output_file = Path(args.output)
    else:
        from datetime import datetime
        safe_topic = args.topic.lower().replace(" ", "_")[:40]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_file = Path(f"openalex_{safe_topic}_{timestamp}.csv")

    df.to_csv(output_file, index=False)
    print(f"\n✅ Saved {output_file} with {len(df)} records")

    # Show a preview
    print(f"\n📋 Preview of results:")
    print(df[['title', 'authors', 'year', 'citation_count']].head())
```

## How to Run Your Bot

Save your file. Now you can run your bot from your terminal. Open a terminal, navigate to the directory where you saved your file, and try these commands:

**Basic search:**
```bash
python openalex_bib_generator.py "algorithmic bias"
```

**Search for 3 pages of results:**
```bash
python openalex_bib_generator.py "large language models" --pages 3
```

**Search for papers since 2022:**
```bash
python openalex_bib_generator.py "AI in education" --since 2022
```

Each time you run it, a new `.csv` file will be created in the same folder, ready for you to use