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

# ---------- core helpers --------------------------------------------------- #
def fetch_works(
    term: str,
    per_page: int = 25,
    max_pages: int = 2,
    extra_filter: Optional[str] = None,
    polite_delay: float = 1.0,
) -> List[Dict]:
    """Return (max_pages × per_page) records that match *term*."""
    works: List[Dict] = []
    
    for page in range(max_pages):
        # Build URL with simple parameters that work
        params = {
            'search': term,
            'per-page': per_page,
            'page': page + 1  # Use page number instead of cursor
        }
        
        # Add filters if provided
        if extra_filter:
            params['filter'] = extra_filter
        
        try:
            print(f"🔄 Fetching page {page + 1}...")
            r = requests.get(
                BASE_URL, 
                params=params,
                timeout=30, 
                headers={"User-Agent": "openalex-bib-generator/1.0"}
            )
            
            # Debug: print the actual URL being called
            print(f"   URL: {r.url}")
            
            if r.status_code != 200:
                print(f"   Status: {r.status_code}")
                print(f"   Response: {r.text}")
                break
            
            data = r.json()
            
            # OpenAlex returns results in 'results' field
            if 'results' in data and data['results']:
                works.extend(data['results'])
                print(f"✅ Page {page + 1}: Found {len(data['results'])} papers")
                
                # If we got fewer results than requested, we're at the end
                if len(data['results']) < per_page:
                    print(f"   Reached end of results")
                    break
            else:
                print(f"❌ No results found on page {page + 1}")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching page {page + 1}: {e}")
            break
            
        time.sleep(polite_delay)
    
    return works


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
                pub_year = w['publication_date'][:4] if isinstance(w.get('publication_date'), str) else ""
            except Exception:
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
            doi = w['doi'].replace('https://doi.org/', '') if isinstance(w.get('doi'), str) else ''
        
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
            "url": w.get("id", "") if isinstance(w.get("id"), str) else "",
            "open_access_pdf": open_access_url,
            "concepts": "; ".join(concepts),
            "type": w.get("type", ""),
            "is_oa": w.get("open_access", {}).get("is_oa", False),
            "abstract": "Abstract available" if w.get("abstract_inverted_index") else "",
        })
    
    return pd.DataFrame(rows)


def test_simple_query():
    """
    Test function to verify API connectivity.

    This function performs a simple query to the OpenAlex API using the term 'dna' 
    to check if the API is reachable and functioning correctly. It prints the status 
    code, the URL of the request, and the number of results found. This is useful 
    for debugging network issues or verifying that the API is operational before 
            timeout=30
    """
    print("🧪 Testing simple API call...")
    
    try:
        response = requests.get(
            "https://api.openalex.org/works",
            params={'search': 'dna'},
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   URL: {response.url}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Results found: {len(data.get('results', []))}")
            print("   ✅ API is working!")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"   Exception: {e}")
        return False


def test_with_params():
    """Test with parameters similar to our use case."""
    print("🧪 Testing with parameters...")
    
    try:
        response = requests.get(
            "https://api.openalex.org/works",
            params={
                'search': 'machine learning',
                'per-page': 5
            },
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   URL: {response.url}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Results found: {len(data.get('results', []))}")
            print("   ✅ Parameters working!")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"   Exception: {e}")
        return False


def test_pagination():
    """Test pagination to make sure our approach works."""
    print("🧪 Testing pagination...")
    
    try:
        response = requests.get(
            "https://api.openalex.org/works",
            params={
                'search': 'machine learning',
                'per-page': 5,
                'page': 2
            },
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   URL: {response.url}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Results found: {len(data.get('results', []))}")
            print("   ✅ Pagination working!")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"   Exception: {e}")
        return False


# ---------- CLI entry-point ----------------------------------------------- #
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

    # Positional topic
    p.add_argument("topic", nargs="?", default="machine learning",
                   help='Search term, e.g. "natural language processing"')

    # Pagination flags
    p.add_argument("--pages", type=int, default=2,     
                   help="How many pages to fetch (default: 2)")
    p.add_argument("--per-page", type=int, default=25, 
                   help="Results per page, max 200 (default: 25)")
    
    # Date filtering
    p.add_argument("--since", metavar="YYYY",    
                   help="From this year (inclusive)")
    p.add_argument("--until", metavar="YYYY",    
                   help="Up to this year (inclusive)")
    
    # Output options
    p.add_argument("-o", "--output",                   
                   help="Output filename (auto-generated if omitted)")
    
    # Performance options
    p.add_argument("--delay", type=float, default=1.0,
                   help="Delay between requests in seconds (default: 1.0)")
    
    # Debug option
    p.add_argument("--test", action="store_true",
                   help="Test API connectivity and exit")
    
    return p


def build_date_filter(since: str = None, until: str = None) -> str:
    """Build OpenAlex date filter string."""
    filters = []
    
    if since:
        filters.append(f"from_publication_date:{since}-01-01")
    if until:
        filters.append(f"to_publication_date:{until}-12-31")
    
    return ",".join(filters) if filters else None


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


if __name__ == "__main__":
    args = build_arg_parser().parse_args()
    
    # Validate arguments
    if args.since and args.until:
        if not args.since.isdigit() or not args.until.isdigit():
            print("Error: 'since' and 'until' must be valid numeric years.")
            exit(1)
        if int(args.since) > int(args.until):
            print("Error: 'since' year cannot be greater than 'until' year.")
            exit(1)
    
    if args.per_page <= 0 or args.pages <= 0:
        print("Error: 'per-page' and 'pages' must be positive integers.")
        exit(1)

    # Test mode
    if args.test:
        success1 = test_simple_query()
        success2 = test_with_params()
        success3 = test_pagination()
        exit(0 if (success1 and success2 and success3) else 1)

    # Validate per_page limit
    if args.per_page > 200:
        print(f"Warning: OpenAlex limits results to 200 per page. Overriding 'per-page' value to 200.")
        args.per_page = 200

    # Build date filter
    extra_filter = build_date_filter(since=args.since, until=args.until)

    # Fetch data
    print(f"🔍 Searching OpenAlex for: '{args.topic}'")
    if extra_filter:
        print(f"   Filters: {extra_filter}")
    
    works = fetch_works(
        term=args.topic,
        per_page=args.per_page,
        max_pages=args.pages,
        extra_filter=extra_filter,
        polite_delay=args.delay
    )

    if not works:
        print("\n❌ No results found. Try:")
        print("   • A different search term")
        print("   • Removing date filters")
        print("   • Running with --test flag to check connectivity")
        exit(1)

    df = to_dataframe(works)
    print_summary(df)

    # Generate output filename
    if args.output:
        output_file = Path(args.output)
    else:
        from datetime import datetime
        safe_topic = args.topic.lower().replace(" ", "_")[:40] if args.topic else "default_topic"
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_file = Path(f"openalex_{safe_topic}_{timestamp}.csv")

    # Save results
    try:
        df.to_csv(output_file, index=False)
        print(f"\n✅ Saved {output_file} with {len(df)} records")
    except Exception as e:
        print(f"\n❌ Failed to save file {output_file}: {e}")
        exit(1)
    
    # Show preview
    print(f"\n📋 Preview of results:")
    preview_cols = ['title', 'authors', 'year', 'citation_count']
    available_cols = [col for col in preview_cols if col in df.columns]
    if not df.empty:
        print(df[available_cols].head())