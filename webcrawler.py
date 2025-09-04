import streamlit as st
import time
import re
import json
import requests
from datetime import datetime, timezone

# Set page config FIRST
st.set_page_config(
    page_title="Firecrawl Web Scraper",
    page_icon="🔥",
    layout="wide"
)

# Hardcoded Firecrawl API key
FIRECRAWL_API_KEY = "fc-053ba42fcfe94e809cc1e8297c0993b4"

# Import FirecrawlApp with error handling
try:
    from firecrawl import FirecrawlApp
    st.sidebar.success("✅ Using FirecrawlApp")
except ImportError as e:
    st.error(f"❌ Could not import FirecrawlApp: {str(e)}")
    st.info("💡 Try: pip install firecrawl-py")
    st.stop()

def validate_url(url):
    """Basic URL validation"""
    if not url:
        return False, "URL cannot be empty"
    
    if not url.startswith(('http://', 'https://')):
        return False, "URL must start with http:// or https://"
    
    if not re.search(r'\.[a-z]{2,}', url.lower()):
        return False, "URL must have a valid domain"
    
    return True, "Valid URL"

def validate_ada_config(instance_name, ada_api_key):
    """Validate Ada configuration"""
    if not instance_name:
        return False, "Instance name is required"
    
    if not ada_api_key:
        return False, "Ada API key is required"
    
    # Basic instance name validation (should not contain special characters except hyphens)
    if not re.match(r'^[a-zA-Z0-9-]+$', instance_name):
        return False, "Instance name should only contain letters, numbers, and hyphens"
    
    return True, "Valid Ada configuration"

def get_current_datetime():
    """Get current datetime in RFC 3339 format for Ada"""
    # Use UTC timezone and format as RFC 3339
    now = datetime.now(timezone.utc)
    return now.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def start_crawl_job(firecrawl, url, limit=5):
    """Start a crawl job using the correct method signature"""
    
    st.info("🔍 Analyzing available methods...")
    
    # Method 1: Try start_crawl (appears to be available)
    if hasattr(firecrawl, 'start_crawl'):
        try:
            st.info("🔄 Using start_crawl method...")
            # Try with single parameter (URL)
            result = firecrawl.start_crawl(url)
            st.success("✅ start_crawl with URL only worked!")
            return result
        except Exception as e:
            st.warning(f"start_crawl with URL failed: {str(e)}")
            try:
                # Try with parameters dict
                st.info("🔄 Trying start_crawl with params dict...")
                params = {
                    'url': url,
                    'limit': limit,
                    'crawlerOptions': {
                        'limit': limit
                    }
                }
                result = firecrawl.start_crawl(params)
                st.success("✅ start_crawl with params dict worked!")
                return result
            except Exception as e2:
                st.warning(f"start_crawl with params failed: {str(e2)}")
    
    # Method 2: Try crawl (takes 2 arguments total = self + 1 parameter)
    if hasattr(firecrawl, 'crawl'):
        try:
            st.info("🔄 Using crawl method with URL only...")
            result = firecrawl.crawl(url)
            st.success("✅ crawl with URL worked!")
            return result
        except Exception as e:
            st.warning(f"crawl with URL failed: {str(e)}")
            try:
                st.info("🔄 Using crawl method with params dict...")
                params = {
                    'url': url,
                    'limit': limit,
                    'crawlerOptions': {
                        'limit': limit
                    }
                }
                result = firecrawl.crawl(params)
                st.success("✅ crawl with params dict worked!")
                return result
            except Exception as e2:
                st.warning(f"crawl with params dict failed: {str(e2)}")
    
    # Method 3: Direct API call as last resort
    try:
        st.info("🔄 Trying direct API call...")
        headers = {
            'Authorization': f'Bearer {FIRECRAWL_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Try start crawl endpoint
        crawl_data = {
            'url': url,
            'limit': limit,
            'crawlerOptions': {
                'limit': limit
            }
        }
        
        response = requests.post(
            'https://api.firecrawl.dev/v0/crawl',
            headers=headers,
            json=crawl_data,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            st.success("✅ Direct API call worked!")
            return result
        else:
            st.warning(f"Direct API call failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        st.warning(f"Direct API call failed: {str(e)}")
    
    # If all methods fail
    available_methods = [method for method in dir(firecrawl) if 'crawl' in method.lower()]
    raise Exception(f"No working crawl method found. Available methods: {available_methods}")

def check_crawl_status(firecrawl, job_id):
    """Check crawl status using the correct method"""
    
    # Method 1: Try get_crawl_status (appears to be available)
    if hasattr(firecrawl, 'get_crawl_status'):
        try:
            return firecrawl.get_crawl_status(job_id)
        except Exception as e:
            st.warning(f"get_crawl_status failed: {str(e)}")
    
    # Method 2: Direct API call
    try:
        headers = {
            'Authorization': f'Bearer {FIRECRAWL_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.firecrawl.dev/v0/crawl/status/{job_id}',
            headers=headers,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            st.error(f"Status API call failed: {response.status_code}")
            return None
            
    except Exception as e:
        st.error(f"Direct status API call failed: {str(e)}")
    
    raise Exception("No working status method found")

def fetch_all_existing_articles(instance_name, ada_api_key, knowledge_source_id):
    """Fetch all existing articles from Ada knowledge source with pagination"""
    base_url = f"https://{instance_name}.ada.support/api/v2/knowledge/articles/"
    headers = {
        "Authorization": f"Bearer {ada_api_key}",
        "Content-Type": "application/json"
    }
    
    all_articles = []
    next_url = f"{base_url}?knowledge_source_id={knowledge_source_id}"
    page_count = 0
    
    while next_url:
        page_count += 1
        st.write(f"📄 Fetching page {page_count}...")
        
        try:
            response = requests.get(next_url, headers=headers, timeout=30)
            
            if response.status_code not in [200, 201]:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "articles": []
                }
            
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, dict):
                articles = data.get('data', data.get('results', []))
                next_url = data.get('next')
            else:
                articles = data if isinstance(data, list) else []
                next_url = None
            
            all_articles.extend(articles)
            st.write(f"   Found {len(articles)} articles on this page")
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timeout while fetching existing articles",
                "articles": all_articles
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Connection error while fetching existing articles",
                "articles": all_articles
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error fetching existing articles: {str(e)}",
                "articles": all_articles
            }
    
    return {
        "success": True,
        "error": None,
        "articles": all_articles
    }

def resolve_article_ids(scraped_articles, instance_name, ada_api_key, knowledge_source_id):
    """Check existing articles and update IDs where name matches"""
    
    st.subheader("🔍 Checking Existing Articles in Ada")
    st.info(f"Fetching existing articles from knowledge source: **{knowledge_source_id}**")
    
    # Fetch all existing articles
    with st.spinner("Fetching existing articles from Ada..."):
        result = fetch_all_existing_articles(instance_name, ada_api_key, knowledge_source_id)
    
    if not result["success"]:
        st.error(f"❌ Failed to fetch existing articles: {result['error']}")
        return scraped_articles, 0, 0
    
    existing_articles = result["articles"]
    st.success(f"✅ Found {len(existing_articles)} existing articles in Ada")
    
    # Create name-to-id mapping for existing articles
    existing_name_to_id = {}
    for article in existing_articles:
        if isinstance(article, dict):
            name = article.get('name')
            article_id = article.get('id')
            if name and article_id:
                existing_name_to_id[name] = article_id
    
    st.write(f"📋 Created mapping for {len(existing_name_to_id)} articles with valid names and IDs")
    
    # Process scraped articles
    updated_articles = []
    updates_count = 0
    new_articles_count = 0
    
    st.write("🔄 Processing scraped articles...")
    
    for i, article in enumerate(scraped_articles):
        article_copy = article.copy()
        scraped_name = article['name']
        original_id = article['id']
        
        # Check if name exists in Ada
        if scraped_name in existing_name_to_id:
            # Name match found - use existing Ada ID
            existing_id = existing_name_to_id[scraped_name]
            article_copy['id'] = existing_id
            updates_count += 1
            st.write(f"   🔄 **Update**: '{scraped_name}' (Ada ID: {existing_id})")
        else:
            # No match - keep original scraped ID
            new_articles_count += 1
            st.write(f"   ➕ **New**: '{scraped_name}' (Scraped ID: {original_id})")
        
        updated_articles.append(article_copy)
    
    # Summary
    st.markdown("---")
    st.subheader("📊 Article ID Resolution Summary")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🔄 Will Update", updates_count)
    with col2:
        st.metric("➕ Will Create", new_articles_count)
    with col3:
        st.metric("📄 Total Articles", len(scraped_articles))
    
    if updates_count > 0:
        st.success(f"✅ {updates_count} articles will be **updated** with existing Ada IDs")
    if new_articles_count > 0:
        st.info(f"ℹ️ {new_articles_count} articles will be **created** as new")
    
    return updated_articles, updates_count, new_articles_count

def upload_article_to_ada(article_data, instance_name, ada_api_key):
    """Upload a single article to Ada using the bulk endpoint"""
    url = f"https://{instance_name}.ada.support/api/v2/knowledge/bulk/articles/"
    
    headers = {
        "Authorization": f"Bearer {ada_api_key}",
        "Content-Type": "application/json"
    }
    
    # Prepare the payload as an array (bulk format) with all required fields including external_updated
    payload = [{
        "id": article_data["id"],
        "name": article_data["name"],
        "content": article_data["content"],
        "url": article_data["url"],
        "language": article_data["language"],
        "knowledge_source_id": article_data["knowledge_source_id"],
        "external_updated": article_data["external_updated"]
    }]
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        return {
            "success": response.status_code in [200, 201],
            "status_code": response.status_code,
            "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
            "error": None
        }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "status_code": None,
            "response": None,
            "error": "Request timeout (30s)"
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "status_code": None,
            "response": None,
            "error": "Connection error - check instance name and network"
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": None,
            "response": None,
            "error": str(e)
        }

def upload_selected_articles_to_ada(selected_articles, instance_name, ada_api_key, knowledge_source_id):
    """Upload selected articles to Ada with ID resolution built-in"""
    if not selected_articles:
        st.error("No articles selected for upload")
        return 0, 0
    
    st.info(f"🚀 Starting upload of {len(selected_articles)} selected articles to **{instance_name}.ada.support**")
    
    # STEP 1: RESOLVE ARTICLE IDS (Always happens)
    st.markdown("---")
    resolved_articles, updates_count, new_count = resolve_article_ids(
        selected_articles, instance_name, ada_api_key, knowledge_source_id
    )
    
    st.markdown("---")
    st.subheader("📤 Uploading to Ada")
    
    # OVERALL PROGRESS BAR
    overall_progress = st.progress(0)
    overall_status = st.empty()
    
    # Results tracking
    successful_uploads = 0
    failed_uploads = 0
    upload_results = []
    
    # Individual upload logs container
    logs_container = st.container()
    
    for i, article in enumerate(resolved_articles):
        # Update overall progress
        progress = i / len(resolved_articles)
        overall_progress.progress(progress)
        overall_status.text(f"📤 Uploading {i + 1}/{len(resolved_articles)}: {article['name'][:50]}...")
        
        # Individual upload log
        with logs_container:
            with st.expander(f"📤 Uploading: {article['name']}", expanded=False):
                st.write(f"**URL:** {article['url']}")
                st.write(f"**ID:** {article['id']}")
                st.write(f"**External Updated:** {article['external_updated']}")
                
                # Upload the article
                with st.spinner("Uploading..."):
                    result = upload_article_to_ada(article, instance_name, ada_api_key)
                
                # Show result
                if result["success"]:
                    successful_uploads += 1
                    st.success(f"✅ Success! (Status: {result['status_code']})")
                    if result["response"]:
                        st.json(result["response"])
                else:
                    failed_uploads += 1
                    error_msg = result["error"] or f"HTTP {result['status_code']}"
                    st.error(f"❌ Failed: {error_msg}")
                    if result["response"]:
                        st.json(result["response"])
                
                upload_results.append({
                    "article_name": article['name'],
                    "article_id": article['id'],
                    "success": result["success"],
                    "status_code": result["status_code"],
                    "error": result["error"]
                })
        
        # Small delay to show progress
        time.sleep(0.5)
    
    # Complete overall progress
    overall_progress.progress(1.0)
    overall_status.text("🎉 Upload process completed!")
    
    # Final summary
    st.markdown("---")
    st.subheader("📊 Upload Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Uploaded", len(resolved_articles))
    with col2:
        st.metric("✅ Successful", successful_uploads)
    with col3:
        st.metric("❌ Failed", failed_uploads)
    with col4:
        success_rate = (successful_uploads / len(resolved_articles)) * 100 if resolved_articles else 0
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    # Results table
    if upload_results:
        with st.expander("📋 Detailed Upload Results"):
            results_df = []
            for result in upload_results:
                results_df.append({
                    "Article Name": result["article_name"][:50] + "..." if len(result["article_name"]) > 50 else result["article_name"],
                    "Article ID": result["article_id"],
                    "Status": "✅ Success" if result["success"] else "❌ Failed",
                    "Status Code": result["status_code"] or "N/A",
                    "Error": result["error"] or "None"
                })
            
            st.dataframe(results_df, use_container_width=True)
            
            # Download results
            results_json = json.dumps(upload_results, indent=2)
            st.download_button(
                "📥 Download Upload Results",
                data=results_json,
                file_name=f"ada_upload_results_{instance_name}.json",
                mime="application/json"
            )
    
    return successful_uploads, failed_uploads

def poll_crawl_status(firecrawl, job_id):
    """Poll the crawl job status until completion"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    max_attempts = 60  # Maximum polling attempts
    attempt = 0
    
    while attempt < max_attempts:
        try:
            status_response = check_crawl_status(firecrawl, job_id)
            
            if isinstance(status_response, dict):
                status = status_response.get('status')
                completed = status_response.get('completed', 0)
                total = status_response.get('total', 0)
                data = status_response.get('data', [])
            else:
                status = getattr(status_response, 'status', None)
                completed = getattr(status_response, 'completed', 0)
                total = getattr(status_response, 'total', 0)
                data = getattr(status_response, 'data', [])
            
            if status == "scraping":
                progress = completed / total if total > 0 else 0.1
                progress_bar.progress(min(progress, 0.9))
                status_text.text(f"🔄 Crawling in progress... {completed}/{total} pages completed")
                
            elif status == "completed":
                progress_bar.progress(1.0)
                status_text.text(f"✅ Crawl completed! {completed} pages scraped")
                return status_response
                
            elif status == "failed":
                status_text.text("❌ Crawl failed")
                st.error("Crawl job failed")
                return None
                
            else:
                progress_bar.progress(0.1)
                status_text.text(f"🔄 Status: {status}... {completed}/{total} pages")
            
            time.sleep(5)
            attempt += 1
            
        except Exception as e:
            st.error(f"Error checking status: {str(e)}")
            return None
    
    st.error("⏰ Polling timeout - crawl may still be running")
    return None

def format_for_ada_upload(page_data, index, language, knowledge_source_id):
    """Format scraped content for Ada upload"""
    if isinstance(page_data, dict):
        markdown_content = page_data.get('markdown', page_data.get('content', ''))
        metadata = page_data.get('metadata', {})
        title = metadata.get('title', f'Page {index + 1}')
        source_url = metadata.get('sourceURL', metadata.get('url', 'N/A'))
        scrape_id = metadata.get('scrapeId', f'scrape_{index + 1}')
    else:
        markdown_content = getattr(page_data, 'markdown', getattr(page_data, 'content', ''))
        metadata = getattr(page_data, 'metadata', {})
        if isinstance(metadata, dict):
            title = metadata.get('title', f'Page {index + 1}')
            source_url = metadata.get('sourceURL', metadata.get('url', 'N/A'))
            scrape_id = metadata.get('scrapeId', f'scrape_{index + 1}')
        else:
            title = getattr(metadata, 'title', f'Page {index + 1}')
            source_url = getattr(metadata, 'sourceURL', getattr(metadata, 'url', 'N/A'))
            scrape_id = getattr(metadata, 'scrapeId', f'scrape_{index + 1}')
    
    # Format for Ada API with ALL required fields including external_updated
    ada_format = {
        "id": scrape_id,
        "name": title,
        "content": markdown_content,
        "url": source_url,
        "language": language,
        "knowledge_source_id": knowledge_source_id,
        "external_updated": get_current_datetime()
    }
    
    return ada_format

def display_crawl_results(crawl_data, language, knowledge_source_id):
    """Display only crawl results summary - no article previews"""
    if not crawl_data:
        st.warning("No data found in crawl results")
        return
    
    # Handle different response formats
    if isinstance(crawl_data, dict):
        data = crawl_data.get('data', [])
        status = crawl_data.get('status', 'completed')
        completed = crawl_data.get('completed', len(data))
        total = crawl_data.get('total', len(data))
        credits_used = crawl_data.get('creditsUsed', 'N/A')
    else:
        data = getattr(crawl_data, 'data', [])
        status = getattr(crawl_data, 'status', 'completed')
        completed = getattr(crawl_data, 'completed', len(data))
        total = getattr(crawl_data, 'total', len(data))
        credits_used = getattr(crawl_data, 'creditsUsed', 'N/A')
    
    st.success(f"🎉 Crawl {status}! Found {len(data)} pages")
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Pages Found", len(data))
    with col2:
        st.metric("Completed", f"{completed}/{total}")
    with col3:
        st.metric("Credits Used", credits_used)
    
    # Format all data for Ada
    ada_formatted_data = []
    for i, page in enumerate(data):
        ada_format = format_for_ada_upload(page, i, language, knowledge_source_id)
        ada_formatted_data.append(ada_format)
    
    # Store Ada formatted data in session state
    st.session_state['ada_formatted_data'] = ada_formatted_data
    
    # Simple confirmation message only
    st.info(f"✅ {len(ada_formatted_data)} articles formatted and ready for Ada upload. Use the upload section below to proceed.")

def display_paginated_articles(filtered_articles, search_term=""):
    """Display articles with pagination (100 per page)"""
    
    if not filtered_articles:
        st.warning("No articles to display")
        return []
    
    # Pagination settings
    ARTICLES_PER_PAGE = 100
    total_articles = len(filtered_articles)
    total_pages = (total_articles - 1) // ARTICLES_PER_PAGE + 1
    
    # Initialize page number in session state
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 1
    
    # Reset to page 1 if search term changes
    if 'last_search' not in st.session_state:
        st.session_state['last_search'] = ""
    
    if st.session_state['last_search'] != search_term:
        st.session_state['current_page'] = 1
        st.session_state['last_search'] = search_term
    
    # Ensure current page is within bounds
    if st.session_state['current_page'] > total_pages:
        st.session_state['current_page'] = total_pages
    if st.session_state['current_page'] < 1:
        st.session_state['current_page'] = 1
    
    current_page = st.session_state['current_page']
    
    # Calculate start and end indices
    start_idx = (current_page - 1) * ARTICLES_PER_PAGE
    end_idx = min(start_idx + ARTICLES_PER_PAGE, total_articles)
    current_page_articles = filtered_articles[start_idx:end_idx]
    
    # Display pagination info
    st.info(f"📄 Showing articles {start_idx + 1}-{end_idx} of {total_articles} total articles (Page {current_page} of {total_pages})")
    
    # Pagination controls
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
    
    with col1:
        if st.button("⏮️ First", disabled=(current_page == 1)):
            st.session_state['current_page'] = 1
            st.rerun()
    
    with col2:
        if st.button("◀️ Previous", disabled=(current_page == 1)):
            st.session_state['current_page'] -= 1
            st.rerun()
    
    with col3:
        # Page selector
        new_page = st.selectbox(
            f"Page {current_page} of {total_pages}",
            range(1, total_pages + 1),
            index=current_page - 1,
            key="page_selector"
        )
        if new_page != current_page:
            st.session_state['current_page'] = new_page
            st.rerun()
    
    with col4:
        if st.button("▶️ Next", disabled=(current_page == total_pages)):
            st.session_state['current_page'] += 1
            st.rerun()
    
    with col5:
        if st.button("⏭️ Last", disabled=(current_page == total_pages)):
            st.session_state['current_page'] = total_pages
            st.rerun()
    
    # Select All / None buttons for current page
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("☑️ Select All (This Page)", key=f"select_all_page_{current_page}"):
            for i in range(start_idx, end_idx):
                st.session_state[f"article_selected_{i}"] = True
            st.rerun()
    
    with col2:
        if st.button("☐ Deselect All (This Page)", key=f"deselect_all_page_{current_page}"):
            for i in range(start_idx, end_idx):
                st.session_state[f"article_selected_{i}"] = False
            st.rerun()
    
    # Display current page articles
    selected_indices = []
    st.write(f"**Select articles to upload (Page {current_page}):**")
    
    for page_idx, article in enumerate(current_page_articles):
        global_idx = start_idx + page_idx
        
        # Default to selected if not set
        default_selected = st.session_state.get(f"article_selected_{global_idx}", True)
        
        is_selected = st.checkbox(
            f"**{article['name']}**\n🔗 {article['url']}\n🆔 {article['id']}\n📅 {article['external_updated']}",
            value=default_selected,
            key=f"article_selected_{global_idx}"
        )
        
        if is_selected:
            selected_indices.append(global_idx)
    
    # Bottom pagination controls (duplicate)
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
    
    with col1:
        if st.button("⏮️ First", disabled=(current_page == 1), key="bottom_first"):
            st.session_state['current_page'] = 1
            st.rerun()
    
    with col2:
        if st.button("◀️ Previous", disabled=(current_page == 1), key="bottom_prev"):
            st.session_state['current_page'] -= 1
            st.rerun()
    
    with col3:
        st.write(f"**Page {current_page} of {total_pages}** ({len(selected_indices)} selected on this page)")
    
    with col4:
        if st.button("▶️ Next", disabled=(current_page == total_pages), key="bottom_next"):
            st.session_state['current_page'] += 1
            st.rerun()
    
    with col5:
        if st.button("⏭️ Last", disabled=(current_page == total_pages), key="bottom_last"):
            st.session_state['current_page'] = total_pages
            st.rerun()
    
    # Return all selected articles (from all pages)
    all_selected_indices = []
    for i in range(len(filtered_articles)):
        if st.session_state.get(f"article_selected_{i}", True):
            all_selected_indices.append(i)
    
    return [filtered_articles[i] for i in all_selected_indices]

def main():
    st.title("🔥 Firecrawl → Ada Integration")
    st.markdown("Scrape websites with Firecrawl and upload to Ada knowledge base")
    
    # Show hardcoded Firecrawl API key status
    st.sidebar.success("✅ Firecrawl API Key: Configured")
    
    # Configuration in sidebar
    st.sidebar.header("🎯 Ada Configuration")
    instance_name = st.sidebar.text_input(
        "Ada Instance Name:",
        placeholder="your-instance-name",
        help="Your Ada subdomain (e.g., 'mycompany' for mycompany.ada.support)"
    )
    
    ada_api_key = st.sidebar.text_input(
        "Ada API Key:",
        type="password",
        placeholder="your-ada-api-key",
        help="Your Ada API Bearer token"
    )
    
    # Show Ada URL preview
    if instance_name:
        st.sidebar.info(f"🔗 Target URL: https://{instance_name}.ada.support/api/v2/knowledge/bulk/articles/")
    
    # Validate configurations
    ada_config_valid, ada_config_message = validate_ada_config(instance_name, ada_api_key)
    
    if not ada_config_valid:
        st.warning(f"⚠️ Ada Configuration: {ada_config_message}")
        st.info("💡 Please configure your Ada instance name and API key in the sidebar to enable upload functionality")
    else:
        st.success("✅ All configurations look good!")
    
    # URL input
    st.sidebar.header("🌐 Website to Crawl")
    url = st.sidebar.text_input(
        "Website URL:",
        placeholder="https://example.com",
        value="https://example.com"
    )
    
    # Knowledge configuration
    st.sidebar.header("📚 Knowledge Configuration")
    language = st.sidebar.text_input(
        "Language:",
        value="en",
        placeholder="e.g. en, es, fr, de",
        help="Language code for the scraped content"
    )
    
    knowledge_source_id = st.sidebar.text_input(
        "Knowledge Source ID:",
        value="123",
        placeholder="e.g. 123, kb_001, source_main",
        help="Your Ada knowledge source identifier"
    )
    
    # Crawl options
    st.sidebar.header("⚙️ Crawl Options")
    limit = st.sidebar.slider(
        "Max pages to crawl:",
        min_value=1,
        max_value=20,
        value=5
    )
    
    # Validate URL
    if url:
        is_valid, message = validate_url(url)
        if is_valid:
            st.sidebar.success("✅ URL looks valid")
        else:
            st.sidebar.error(f"❌ {message}")
    
    # Show current configuration
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Current Config")
    st.sidebar.write(f"**Language:** {language}")
    st.sidebar.write(f"**Knowledge Source:** {knowledge_source_id}")
    st.sidebar.write(f"**Max Pages:** {limit}")
    if ada_config_valid:
        st.sidebar.write(f"**Ada Instance:** {instance_name}")
    
    # Show current datetime that will be used
    st.sidebar.markdown("---")
    st.sidebar.subheader("⏰ System Time")
    current_time = get_current_datetime()
    st.sidebar.info(f"**External Updated Time:**\n{current_time}")
    
    # Main content area - CRAWLING SECTION
    st.header("🕷️ Web Crawling")
    
    # Initialize FirecrawlApp
    try:
        firecrawl = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
        st.success("✅ Firecrawl client initialized successfully")
        
        # Show available methods for debugging
        available_methods = [method for method in dir(firecrawl) if 'crawl' in method.lower()]
        st.info(f"🔍 Available crawl methods: {available_methods}")
            
    except Exception as e:
        st.error(f"❌ Failed to initialize Firecrawl: {str(e)}")
        st.info("💡 Make sure firecrawl-py is installed: `pip install firecrawl-py`")
        return
    
    # Crawl button
    if st.button("🚀 Start Crawling", type="primary", key="start_crawl_button"):
        if not url or not validate_url(url)[0]:
            st.error("Please enter a valid URL")
        elif not language or not knowledge_source_id:
            st.error("Please specify language and knowledge source ID")
        else:
            try:
                st.info(f"🔄 Starting crawl of {url} (max {limit} pages)...")
                
                # Start the crawl job using our corrected method
                with st.spinner("Starting crawl job..."):
                    job_response = start_crawl_job(firecrawl, url, limit)
                
                # Handle response format to get job ID
                if isinstance(job_response, dict):
                    job_id = job_response.get('jobId') or job_response.get('id')
                    success = job_response.get('success', True)
                    
                    # Handle synchronous response (when method returns data directly)
                    if 'data' in job_response and not job_id:
                        st.success("✅ Synchronous crawl completed!")
                        display_crawl_results(job_response, language, knowledge_source_id)
                        
                        # Store in session state
                        st.session_state['crawl_results'] = job_response
                        st.session_state['crawl_url'] = url
                        st.session_state['language'] = language
                        st.session_state['knowledge_source_id'] = knowledge_source_id
                        return
                        
                else:
                    job_id = getattr(job_response, 'jobId', None) or getattr(job_response, 'id', None)
                    success = getattr(job_response, 'success', True)
                
                if not success or not job_id:
                    st.error("Failed to start crawl job or got synchronous result")
                    st.json(job_response)
                else:
                    st.success(f"✅ Crawl job started! Job ID: `{job_id}`")
                    
                    # Poll for completion
                    st.subheader("📊 Crawl Progress")
                    final_result = poll_crawl_status(firecrawl, job_id)
                    
                    # Display results
                    if final_result:
                        st.subheader("📈 Results")
                        display_crawl_results(final_result, language, knowledge_source_id)
                        
                        # Store in session state
                        st.session_state['crawl_results'] = final_result
                        st.session_state['crawl_url'] = url
                        st.session_state['job_id'] = job_id
                        st.session_state['language'] = language
                        st.session_state['knowledge_source_id'] = knowledge_source_id
                    else:
                        st.error("❌ Failed to get crawl results")
                        
            except Exception as e:
                st.error(f"❌ Crawling failed: {str(e)}")
                
                error_str = str(e).lower()
                if "unauthorized" in error_str or "401" in error_str:
                    st.info("💡 Check your Firecrawl API key")
                elif "400" in error_str:
                    st.info("💡 Check your URL format")
                elif "no working" in error_str:
                    st.info("💡 Firecrawl library version mismatch - try updating: `pip install --upgrade firecrawl-py`")
                
                st.exception(e)

    # Show previous crawl results if available
    if 'crawl_results' in st.session_state:
        st.markdown("---")
        st.subheader("📂 Previous Crawl Results")
        st.write(f"**Last crawled URL:** {st.session_state.get('crawl_url', 'N/A')}")
        
        if st.button("🔄 Show Last Crawl Results", key="show_last_results"):
            display_crawl_results(
                st.session_state['crawl_results'], 
                st.session_state.get('language', 'en'),
                st.session_state.get('knowledge_source_id', '123')
            )

    # PERMANENT ADA UPLOAD SECTION AT THE BOTTOM
    st.markdown("---")
    st.header("🚀 Upload to Ada")
    
    # Check if we have data to upload
    if 'ada_formatted_data' in st.session_state and st.session_state['ada_formatted_data']:
        articles_data = st.session_state['ada_formatted_data']
        
        st.success(f"✅ {len(articles_data)} articles ready for upload")
        
        # Show Ada configuration status
        ada_config_valid, ada_config_message = validate_ada_config(instance_name, ada_api_key)
        
        if not ada_config_valid:
            st.error(f"❌ Ada Configuration: {ada_config_message}")
            st.info("Please configure your Ada instance name and API key in the sidebar.")
        else:
            st.success(f"✅ Ready to upload to **{instance_name}.ada.support**")
            
            # ARTICLE SELECTION WITH SEARCH AND PAGINATION
            st.subheader("📋 Select Articles to Upload")
            
            # Search functionality
            search_term = st.text_input("🔍 Search articles by name or URL:", placeholder="Type to search...")
            
            # Filter articles based on search
            if search_term:
                filtered_articles = [
                    article for article in articles_data
                    if search_term.lower() in article['name'].lower() or search_term.lower() in article['url'].lower()
                ]
                st.info(f"🔍 Found {len(filtered_articles)} articles matching '{search_term}'")
            else:
                filtered_articles = articles_data
            
            if filtered_articles:
                # Global Select All / None buttons
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("☑️ Select All Articles", key="select_all_global"):
                        for i in range(len(filtered_articles)):
                            st.session_state[f"article_selected_{i}"] = True
                        st.rerun()
                
                with col2:
                    if st.button("☐ Deselect All Articles", key="select_none_global"):
                        for i in range(len(filtered_articles)):
                            st.session_state[f"article_selected_{i}"] = False
                        st.rerun()
                
                # PAGINATED ARTICLE DISPLAY
                selected_articles = display_paginated_articles(filtered_articles, search_term)
                
                # Show selection summary
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Available", len(filtered_articles))
                with col2:
                    st.metric("Selected", len(selected_articles))
                with col3:
                    st.metric("Target Instance", instance_name)
                
                # Show sample payloads for first 10 selected articles
                if selected_articles:
                    with st.expander(f"📋 Sample Payloads (First {min(10, len(selected_articles))} Selected Articles)"):
                        sample_articles = selected_articles[:10]  # Show first 10
                        for i, article in enumerate(sample_articles):
                            st.write(f"**Article {i+1}: {article['name']}**")
                            st.json(article)
                            if i < len(sample_articles) - 1:  # Add separator except for last item
                                st.markdown("---")
                
                # THE UPLOAD BUTTON
                st.markdown("---")
                
                if not selected_articles:
                    st.warning("⚠️ Please select at least one article to upload")
                else:
                    st.info("🔄 Upload Process: Check existing articles → Resolve IDs → Upload to Ada")
                    
                    if st.button(
                        f"🚀 Upload {len(selected_articles)} Selected Articles to Ada",
                        type="primary",
                        key="upload_selected_articles"
                    ):
                        st.write(f"🎯 Starting upload process for {len(selected_articles)} articles...")
                        try:
                            success_count, fail_count = upload_selected_articles_to_ada(
                                selected_articles, instance_name, ada_api_key, knowledge_source_id
                            )
                            st.balloons()
                            st.success(f"🎉 Upload complete! {success_count} successful, {fail_count} failed")
                                
                        except Exception as e:
                            st.error(f"❌ Upload error: {str(e)}")
                            st.exception(e)
            
            else:
                st.warning(f"No articles found matching '{search_term}'")
                
    else:
        st.info("📋 No articles available for upload. Please crawl a website first.")
        st.markdown("👆 Use the crawling section above to scrape content from a website.")

if __name__ == "__main__":
    main()
