# How to Build a Bibliography Bot with Python and the OpenAlex API

This tutorial will guide you through creating a command-line python bot that automatically fetches academic research papers from scholarly graphs and saves them as a bibliography in a CSV file. 

We'll be using the free OpenAlex API to find papers on any topic you choose. We won't have time to look at any other graphs but this code can be easily modified to work with other scholarly graphs like Semantic Scholar.

By the end, we will have a script that runs searches from the command line: (`python3 openalex.py "algorithmic bias" --since 2020`) and instantly outputs a bibliography of relevant research in a `.csv` file, including title, year, authors, venue, citation count, doi, url, open access status, linked pdf, concepts, type of record, and abstract. 

### Preliminaries

Before we start, make sure you have Python installed (and remember to replace 'python3' with 'python' and vice versa as needed.) You will also need to install two Python libraries, `requests` and `pandas`. You can install them using pip:

```bash
pip install requests pandas
```
- **requests:** This is a library for making HTTP requests to websites and APIs.
- **pandas:** This is a library for data analysis and manipulation which we use to organize our data and save it to a formatted csv.file.

---

## Step 1: Setting Up the Script and Imports

First, create a new Python file named `openalex.py`. This single file will contain all of our necessary code. (However, we will need to create a few small additional files if we want to automate the workflow on git. I won't be going over that part as it's equivalent to what we did in class with the twitterbot minus the API key, but it's in the git if you're interested.)

At the top of the .py file, we start by defining the base URL for the OpenAlex API, and importing all the libraries we need, including argparse. Argparse allows us to create command-line interfaces and define arguments like topic, --pages, and --since, letting us select different search queries and options from the terminal without having to edit the code itself each time we want to change the search.

```python
"""
openalex.py
------------------------

Bibliography generator using OpenAlex API for academic research
"""

import argparse
import time
from typing import List, Dict, Optional
from pathlib import Path
import pandas as pd
import requests

BASE_URL = "https://api.openalex.org/works"
```

## Step 2: Fetching Data from the API (`fetch_works`)

This is the core function of our bot. It will contact the OpenAlex API, search for a topic, and handle fetching multiple pages of results. It specifies a search `term` (like "algorithmic bias "), the number of pages and results to get, and potentially other filters. It loops for each page we want, builds the correct URL with our search parameters, and makes a `GET` request. Note that we optionally add a `time.sleep(1.0)` delay between our requests. This is to avoid sending too many requests too quickly and getting blocked.

**Keep in mind that we are also building a command line interface with argparse that will allow us to change these values from the command line. So if we want to change the defaults in our code, we need to change them in argparse, as the defaults specified in building argparse override these when we do not specify a value in the command line for our query.**

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
        print(f"[INFO] Fetching page {page + 1}...")
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
                headers={"User-Agent": "openalex-bib-generator/1.0"} 
                # This is to identify our script and reduce our chance of being blocked.
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

The data we get from the API is in JSON format, which we want to turn into a formatted spreadsheet via the `pandas` library.

This function will loop through each paper we fetched and pull out the specific pieces of information and metadata we care about in our bibliography: title, authors, publication year, abstract, venue, type, citations, etc. It then organizes this clean data into a pandas DataFrame.

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

**For completeness, I've initially shown a compact version that does not extract the abstract but just extracts the metadata of whether the paper includes an abstract, as OpenAlex stores the abstracts in the non-readable inverted index format, and saving the abstracts makes the CSV about 3x larger. But since the csv files are small to begin with, I would default to always extracting the full abstract to our bibliography. We can make two changes to tell the to_dataframe function to extract the abstract and to convert the abstract inverted index into readable text. If you are especially interested in extracting abstracts, it's worth noting that semantic scholar doesn't store abstracts in inverted index, and also offers 1-sentence AI-generated mini abstracts that will fit nicely into the rows of our bibliography csv file.**

```python

# Change the line beginning with "abstract:" in the to_dataframe function to extract the abstract
"abstract": extract_abstract(w.get("abstract_inverted_index", {})),

# Add after the to_dataframe function to make the inverted index abstract readable
def extract_abstract(inverted_index):
    """Convert OpenAlex inverted index to readable text."""
    if not inverted_index:
        return ""
    
    word_positions = []
    for word, positions in inverted_index.items():
        for position in positions:
            word_positions.append((position, word))
    
    word_positions.sort(key=lambda x: x[0])
    abstract = ' '.join([word for _, word in word_positions])
    
    return abstract
```
```python
 def print_summary(df: pd.DataFrame):
    """Print a summary of the retrieved data."""
    if df.empty:
        print("❌ No data retrieved.")
        return
    
    print(f"\n📊 Dataset Summary:")
    print(f"   Total papers: {len(df)}")
    
    # Year analysis
    years = df['year'].replace('', pd.NA).dropna()
    if not years.empty:
        year_nums = pd.to_numeric(years, errors='coerce').dropna()
        if not year_nums.empty:
            print(f"   Year range: {int(year_nums.min())} - {int(year_nums.max())}")
            print(f"   Median year: {int(year_nums.median())}")
    
    # Citation analysis
    print(f"   Average citations: {df['citation_count'].mean():.1f}")
    print(f"   Median citations: {df['citation_count'].median():.0f}")
    print(f"   Max citations: {df['citation_count'].max()}")
    
    # Other stats
    print(f"   Open access papers: {df['is_oa'].sum()} ({df['is_oa'].mean():.1%})")
    print(f"   Papers with PDFs: {(df['open_access_pdf'] != '').sum()}")
    print(f"   Unique venues: {df['venue'].nunique()}")
    
    # Top venues
    top_venues = df['venue'].value_counts().head(3)
    if not top_venues.empty:
        print("\n   Top venues:")
        for venue, count in top_venues.items():
            if venue:  # Skip empty venues
                print(f"   - {venue}: {count} papers")
```

**OpenAlex does not store full texts, so we are not grabbing full text either but we do fetch the paper's open access status as part of the metadata in our bibliography, including extracting the open access pdf url to our csv, creating a one click download of the pdf. We could add a script to our code to automatically download the pdf if it's available from the open access URL and automate this click but I haven't done that, for a variety of reasons. This is not really geared towards mass downloading of texts, open access or not.**

## Step 4: Building the Command-Line Interface (CLI)

**To make our script easy to use, we provide it a command-line interface using the `argparse` library. This allows us to pass in arguments like the search topic or the number of pages directly from the terminal, without having to edit the code to change the query. This function defines all the arguments our script will accept.**

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
    # Change default search values for command line interface here

    p.add_argument("topic", nargs="?", default="algorithmic bias",
                   help='Search term, e.g. "natural language processing"')
    p.add_argument("--pages", type=int, default=2,     
                   help="How many pages to fetch (default: 2)")
    p.add_argument("--per-page", type=int, default=25, 
                   help="Results per page, max 200 (default: 25)")
    p.add_argument("--since", metavar="YYYY", help="From this year (inclusive)")
    p.add_argument("--until", metavar="YYYY", help="Up to this year (inclusive)")
    p.add_argument("-o", "--output", help="Output filename (auto-generated if omitted)")

    # Add more powerful search filters for open access, has pdf, citation count, specific venue, type of text (book, article, pre-print, review, etc.,)

    p.add_argument("--type", choices=["article", "review", "preprint", "book-chapter", "book", "paratext", "dataset", "other"],
               help="Filter by publication type")
    p.add_argument("--only-oa", action="store_true", 
               help="Only open access papers")
    p.add_argument("--only-pdf", action="store_true",
               help="Only papers with downloadable PDFs")
    p.add_argument("--min-citations", type=int,
               help="Minimum citation count")
    p.add_argument("--max-citations", type=int,
               help="Maximum citation count")
    p.add_argument("--venue", help="Filter by specific venue")
    p.add_argument("--has-doi", action="store_true",
               help="Only papers with DOIs")
    
    return p
```

## We need a helper function to convert our command-line arguments into OpenAlex API filters:
  ```python

    def build_filters(
    since: Optional[str] = None,
    until: Optional[str] = None,
    publication_type: Optional[str] = None,
    only_oa: bool = False,
    min_citations: Optional[int] = None,
    max_citations: Optional[int] = None,
    has_doi: bool = False
) -> List[str]:
    """Build OpenAlex filter list."""
    filters = []
    if since:
        filters.append(f"from_publication_date:{since}-01-01")
    if until:
        filters.append(f"to_publication_date:{until}-12-31")
    if publication_type:
        filters.append(f"type:{publication_type}")
    if only_oa:
        filters.append("is_oa:true")
    if min_citations:
        filters.append(f"cited_by_count:>{min_citations}")
    if max_citations:
        filters.append(f"cited_by_count:<{max_citations}")
    if has_doi:
        filters.append("has_doi:true")
    return filters
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

    # Build all filters
    filters = build_filters(
        since=args.since,
        until=args.until,
        publication_type=args.type,
        only_oa=args.only_oa,
        min_citations=args.min_citations,
        max_citations=args.max_citations,
        has_doi=args.has_doi
    )
    extra_filter = ",".join(filters) if filters else None

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

# Apply local filters after fetching
    if args.venue:
        df = df[df['venue'].str.contains(args.venue, case=False, na=False)]
    if args.only_pdf:
        df = df[df['open_access_pdf'] != '']

    print_summary(df)

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

    # Build a preview

    print(f"\n📋 Preview of results:")
    preview_cols = ['title', 'authors', 'year', 'citation_count']
    available_cols = [col for col in preview_cols if col in df.columns]
    if not df.empty:
        print(df[available_cols].head())
                
```

## How to Run Your Bot

Save your file. Now you can run your bot from your terminal. Open a terminal, navigate to the directory where you saved your file, and try these commands:

**Basic search:**
```bash
python openalex.py "algorithmic bias"
'''
**Search for X pages of results:**
python openalex.py "large language models" --pages 9
'''
**Search for papers since/until:**
python openalex.py "AI in education" --since 2022
python openalex.py "Artificial Intelligence" --since 1500 --until 2500
'''
## Advanced Search Examples

**Filter by publication type:**
python openalex.py "algorithmic bias" --type article
python openalex.py "AI ethics" --type review
python openalex.py "neural networks" --type preprint
python openalex.py --type book-chapter
python openalex.py --type book
python openalex.py --type paratext
python openalex.py --type other
'''

**Filter by citations:**
python openalex.py "machine learning" --min-citations 100
python openalex.py "deep learning" --max-citations 50
python openalex.py "fairness" --min-citations 10 --max-citations 100
'''

**Filter by access:**
python openalex.py "computer vision" --only-oa
python openalex.py "NLP" --only-pdf
python openalex.py "robotics" --has-doi
'''

**Filter by venue:**
python openalex.py "CRISPR" --venue "Nature"
python openalex.py "quantum computing" --venue "Science"
'''

**Combine multiple filters:**
python openalex.py "bias in AI" --since 2020 --type article --min-citations 50 --only-oa
```
#Each time you run the search, a new `.csv` file will be created in the same folder, ready for you to use.

** We can also automate this code the same way we created the github actions in .yml for our twitter bot in class, simply omitting the API key. This is included in my code in Github but I leave it out of the tutorial due to time constraints. **