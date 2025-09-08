import streamlit as st
import time
import re
import json
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse
import hashlib

# Set page config FIRST
st.set_page_config(
    page_title="Firecrawl Web Scraper",
    page_icon="🔥",
    layout="wide"
)

# Hardcoded Firecrawl API key
FIRECRAWL_API_KEY = "fc-053ba42fcfe94e809cc1e8297c0993b4"

# Import FirecrawlApp
try:
    from firecrawl import FirecrawlApp
    st.sidebar.success("✅ Using FirecrawlApp")
except ImportError as e:
    st.error(f"❌ Could not import FirecrawlApp: {str(e)}")
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

def generate_article_id_from_url(source_url, index):
    """Generate article ID from URL path"""
    try:
        parsed_url = urlparse(source_url)
        
        # Get the path part of the URL
        path = parsed_url.path.strip('/')
        
        # If path is empty (root page), use domain + "home"
        if not path:
            domain = parsed_url.netloc.replace('www.', '').replace('.', '_')
            return f"{domain}_home"
        
        # Clean up the path for use as ID
        # Replace common separators with underscores
        clean_path = path.replace('/', '_').replace('-', '_').replace('.', '_')
        
        # Remove file extensions
        clean_path = re.sub(r'\.(html?|php|asp|jsp)$', '', clean_path, flags=re.IGNORECASE)
        
        # Remove special characters except underscores and alphanumeric
        clean_path = re.sub(r'[^a-zA-Z0-9_]', '', clean_path)
        
        # Ensure it starts with a letter (for valid ID)
        if clean_path and not clean_path[0].isalpha():
            clean_path = f"page_{clean_path}"
        
        # If clean_path is empty after cleaning, generate from hash
        if not clean_path:
            url_hash = hashlib.md5(source_url.encode()).hexdigest()[:8]
            clean_path = f"page_{url_hash}"
        
        # Limit length to reasonable size
        if len(clean_path) > 50:
            clean_path = clean_path[:50]
        
        return clean_path
        
    except Exception as e:
        # Fallback to hash-based ID if URL parsing fails
        url_hash = hashlib.md5(source_url.encode()).hexdigest()[:8]
        return f"page_{url_hash}"

def generate_unique_title_from_url(source_url, original_title, index):
    """Generate meaningful title from URL when original title is generic"""
    
    try:
        parsed_url = urlparse(source_url)
        path_parts = parsed_url.path.strip('/').split('/')
        
        # Take the last meaningful part (usually the most descriptive)
        if path_parts:
            last_part = path_parts[-1]
            
            # Clean up the descriptive part
            # Remove leading numbers and hyphens: "7-petting-zoo..." -> "petting-zoo..."
            clean_part = re.sub(r'^\d+-', '', last_part)
            
            # Convert to readable title: "petting-zoo-and-farm-animals-around-selangor"
            # -> "Petting Zoo And Farm Animals Around Selangor"
            readable_title = clean_part.replace('-', ' ').replace('_', ' ')
            readable_title = ' '.join(word.capitalize() for word in readable_title.split())
            
            return readable_title if readable_title.strip() else f"Page {index + 1}"
        
        return f"Page {index + 1}"
        
    except:
        return f"Page {index + 1}"

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
    
    # Process scraped articles - HIDE THE LONG LIST
    with st.expander("📋 View Article Processing Details", expanded=False):
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
                st.write(f"   ➕ **New**: '{scraped_name}' (Generated ID: {original_id})")
            
            updated_articles.append(article_copy)
    
    # Summary - KEEP THIS VISIBLE
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

def poll_crawl_status(firecrawl, crawl_id):
    """Poll the crawl job status until completion using get_crawl_status"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    debug_text = st.empty()
    
    max_attempts = 60
    attempt = 0
    start_time = time.time()
    
    debug_text.info(f"🔍 Starting to poll crawl ID: {crawl_id}")
    
    while attempt < max_attempts:
        try:
            attempt += 1
            elapsed_time = int(time.time() - start_time)
            
            # Pulsing status indicator
            if attempt % 4 == 0: 
                status_indicator = "🔄"
            elif attempt % 4 == 1: 
                status_indicator = "⏳"  
            elif attempt % 4 == 2: 
                status_indicator = "🔍"
            else: 
                status_indicator = "📡"
            
            debug_text.success(f"✅ System responsive - Last check: {datetime.now().strftime('%H:%M:%S')} | Elapsed: {elapsed_time}s")
            
            # Use get_crawl_status as per documentation
            status_response = firecrawl.get_crawl_status(crawl_id)
            
            # Handle response format based on documentation
            if isinstance(status_response, dict):
                status = status_response.get('status')
                completed = status_response.get('completed', 0)
                total = status_response.get('total', 0)
                data = status_response.get('data', [])
            elif hasattr(status_response, 'status'):
                # SDK object format
                status = getattr(status_response, 'status', None)
                completed = getattr(status_response, 'completed', 0)
                total = getattr(status_response, 'total', 0)
                data = getattr(status_response, 'data', [])
            else:
                debug_text.error(f"❌ Unexpected response format: {status_response}")
                status = None
                completed = 0
                total = 0
                data = []
            
            if status == "scraping":
                progress = completed / total if total > 0 else 0.1
                progress_bar.progress(min(progress, 0.9))
                status_text.text(f"{status_indicator} Crawling active... {completed}/{total} pages (Check #{attempt})")
                
            elif status == "completed":
                progress_bar.progress(1.0)
                status_text.text(f"✅ Crawl completed! {completed} pages scraped")
                debug_text.success(f"🎉 Crawl completed successfully with {len(data)} pages")
                debug_text.empty()  # Clear debug on success
                return status_response
                
            elif status == "failed":
                status_text.text("❌ Crawl failed")
                debug_text.error("💥 Crawl job failed")
                st.error("Crawl job failed")
                return None
                
            else:
                progress_bar.progress(0.1)
                status_text.text(f"{status_indicator} Status: {status}... {completed}/{total} pages (Check #{attempt})")
            
            time.sleep(5)
            
        except Exception as e:
            debug_text.error(f"💥 Exception in attempt {attempt}: {str(e)}")
            st.error(f"Error checking status: {str(e)}")
            time.sleep(5)
    
    debug_text.error("⏰ Max polling attempts reached")
    st.error("⏰ Polling timeout - crawl may still be running")
    return None

def format_for_ada_upload(page_data, index, language, knowledge_source_id, use_url_titles=False):
    """Format scraped content for Ada upload with URL path-based ID and optional URL titles"""
    if isinstance(page_data, dict):
        markdown_content = page_data.get('markdown', page_data.get('content', ''))
        metadata = page_data.get('metadata', {})
        title = metadata.get('title', f'Page {index + 1}')
        source_url = metadata.get('sourceURL', metadata.get('url', 'N/A'))
    else:
        markdown_content = getattr(page_data, 'markdown', getattr(page_data, 'content', ''))
        metadata = getattr(page_data, 'metadata', {})
        if isinstance(metadata, dict):
            title = metadata.get('title', f'Page {index + 1}')
            source_url = metadata.get('sourceURL', metadata.get('url', 'N/A'))
        else:
            title = getattr(metadata, 'title', f'Page {index + 1}')
            source_url = getattr(metadata, 'sourceURL', getattr(metadata, 'url', 'N/A'))
    
    # Generate ID from URL path
    article_id = generate_article_id_from_url(source_url, index)
    
    # TITLE LOGIC WITH TOGGLE
    if use_url_titles:
        # Use cleaned URL title
        final_title = generate_unique_title_from_url(source_url, title, index)
    else:
        # Use original scraped title
        final_title = title
    
    # Format for Ada API with ALL required fields including external_updated
    ada_format = {
        "id": article_id,
        "name": final_title,
        "content": markdown_content,
        "url": source_url,
        "language": language,
        "knowledge_source_id": knowledge_source_id,
        "external_updated": get_current_datetime()
    }
    
    return ada_format

def update_existing_crawl_data(language, knowledge_source_id, use_url_titles):
    """Re-format existing crawl data when sidebar settings change"""
    if 'crawl_results' in st.session_state and st.session_state['crawl_results']:
        # Re-format with new settings
        crawl_data = st.session_state['crawl_results']
        if isinstance(crawl_data, dict):
            data = crawl_data.get('data', [])
        else:
            data = getattr(crawl_data, 'data', [])
        
        # Re-format all data with current settings
        ada_formatted_data = []
        for i, page in enumerate(data):
            ada_format = format_for_ada_upload(
                page, i, language, knowledge_source_id, use_url_titles
            )
            ada_formatted_data.append(ada_format)
        
        # Update session state
        st.session_state['ada_formatted_data'] = ada_formatted_data
        return True
    
    return False

def detect_and_update_settings(language, knowledge_source_id, use_url_titles):
    """Detect any setting changes and auto-update existing crawl data"""
    
    settings_changed = False
    changes = []
    
    # Check each setting for changes
    if st.session_state.get('current_language') != language:
        st.session_state['current_language'] = language
        settings_changed = True
        changes.append("Language")

    if st.session_state.get('current_knowledge_source') != knowledge_source_id:
        st.session_state['current_knowledge_source'] = knowledge_source_id
        settings_changed = True
        changes.append("Knowledge Source ID")
        
    if st.session_state.get('current_use_url_titles') != use_url_titles:
        st.session_state['current_use_url_titles'] = use_url_titles
        settings_changed = True
        changes.append("Title Format")

    # AUTO-UPDATE existing crawl data if any settings changed
    if settings_changed and 'crawl_results' in st.session_state:
        if update_existing_crawl_data(language, knowledge_source_id, use_url_titles):
            st.sidebar.success(f"✅ Updated: {', '.join(changes)}")
            st.sidebar.info("💾 Existing crawl data refreshed - no re-crawling needed!")
    
    return settings_changed

def display_crawl_results(crawl_data, language, knowledge_source_id, use_url_titles=False):
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
    
    # Format all data for Ada with current settings
    ada_formatted_data = []
    for i, page in enumerate(data):
        ada_format = format_for_ada_upload(page, i, language, knowledge_source_id, use_url_titles)
        ada_formatted_data.append(ada_format)
    
    # Store Ada formatted data in session state
    st.session_state['ada_formatted_data'] = ada_formatted_data
    
    # Simple confirmation message only
    st.info(f"✅ {len(ada_formatted_data)} articles formatted and ready for Ada upload. Use the upload section below to proceed.")

def display_paginated_articles(filtered_articles, search_term=""):
    """Display articles with pagination (100 per page) and enhanced search with persistent selection"""
    
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
            for article in current_page_articles:
                # Find the original index in filtered_articles
                original_idx = next(i for i, a in enumerate(filtered_articles) if a == article)
                st.session_state[f"article_selected_{original_idx}"] = True
            st.rerun()
    
    with col2:
        if st.button("☐ Deselect All (This Page)", key=f"deselect_all_page_{current_page}"):
            for article in current_page_articles:
                # Find the original index in filtered_articles
                original_idx = next(i for i, a in enumerate(filtered_articles) if a == article)
                st.session_state[f"article_selected_{original_idx}"] = False
            st.rerun()
    
    # Display current page articles
    selected_indices = []
    st.write(f"**Select articles to upload (Page {current_page}):**")
    
    for page_idx, article in enumerate(current_page_articles):
        # Find the original index in the filtered articles list
        original_idx = start_idx + page_idx
        
        # Default to selected if not set
        default_selected = st.session_state.get(f"article_selected_{original_idx}", True)
        
        is_selected = st.checkbox(
            f"**{article['name']}**\n🔗 {article['url']}\n🆔 {article['id']}\n📅 {article['external_updated']}",
            value=default_selected,
            key=f"article_selected_{original_idx}"
        )
        
        if is_selected:
            selected_indices.append(original_idx)
    
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
    st.title("🔥 APAC WEB SCRAPER")
    st.markdown("Scrape websites and upload to Ada")
    
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
    
    # URL Titles Toggle
    use_url_titles = st.sidebar.checkbox(
        "🏷️ Use URL-based Titles",
        value=False,
        help="Generate titles from URL paths instead of scraped page titles (useful when all pages have the same title)"
    )
    
    # Show preview of what this toggle does
    if use_url_titles:
        st.sidebar.info("📝 **Title Source:** URL paths\n\nExample:\n`7-petting-zoo-animals` → `Petting Zoo Animals`")
        if 'ada_formatted_data' in st.session_state and st.session_state['ada_formatted_data']:
            sample_articles = st.session_state['ada_formatted_data'][:3]
            with st.sidebar.expander("📋 Title Preview"):
                for article in sample_articles:
                    st.write(f"• {article['name'][:40]}...")
    else:
        st.sidebar.info("📝 **Title Source:** Scraped page titles")
    
    # DETECT AND UPDATE SETTINGS AUTOMATICALLY
    detect_and_update_settings(language, knowledge_source_id, use_url_titles)
    
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
    st.sidebar.write(f"**Title Mode:** {'URL-based' if use_url_titles else 'Scraped'}")
    st.sidebar.info("**Crawling:** Will find all pages on the website")
    st.sidebar.info("**Article IDs:** Generated from URL paths")
    if ada_config_valid:
        st.sidebar.write(f"**Ada Instance:** {instance_name}")
    
    # Show current datetime that will be used
    st.sidebar.markdown("---")
    st.sidebar.subheader("⏰ System Time")
    current_time = get_current_datetime()
    st.sidebar.info(f"**External Updated Time:**\n{current_time}")
    
    # Main content area - CRAWLING SECTION
    st.header("🕷️ Web Crawling")
    
    # Crawl button
    if st.button("🚀 Start Crawling", type="primary", key="start_crawl_button"):
        if not url or not validate_url(url)[0]:
            st.error("Please enter a valid URL")
        elif not language or not knowledge_source_id:
            st.error("Please specify language and knowledge source ID")
        else:
            try:
                # Initialize FirecrawlApp with hardcoded API key
                firecrawl = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
                
                st.info(f"🔄 Starting crawl of {url} (will find all available pages)...")
                st.warning("⚠️ This will crawl all pages found on the website. This may take time and use credits based on the site size.")
                
                # Step 1: Start crawl and get job ID (no limit = crawl all pages)
                with st.spinner("Starting crawl job..."):
                    job_response = firecrawl.start_crawl(
                        url=url,
                        scrape_options={
                            'onlyMainContent': True,
                            'formats': ['markdown']
                        }
                    )
                
                st.write(f"**Debug - Job Response Type:** {type(job_response)}")
                st.write(f"**Debug - Job Response:** {job_response}")
                
                # Step 2: Extract job ID from response
                if isinstance(job_response, dict):
                    crawl_id = job_response.get('id') or job_response.get('jobId')
                    success = job_response.get('success', True)
                elif hasattr(job_response, 'id'):
                    crawl_id = getattr(job_response, 'id', None)
                    success = getattr(job_response, 'success', True)
                else:
                    crawl_id = None
                    success = False
                
                if not success or not crawl_id:
                    st.error("Failed to start crawl job")
                    st.json(job_response)
                else:
                    st.success(f"✅ Crawl job started! Crawl ID: `{crawl_id}`")
                    
                    # Step 3: Poll for completion using get_crawl_status
                    st.subheader("📊 Crawl Progress")
                    final_result = poll_crawl_status(firecrawl, crawl_id)
                    
                    # Step 4: Display results
                    if final_result:
                        st.subheader("📈 Results")
                        display_crawl_results(final_result, language, knowledge_source_id, use_url_titles)
                        
                        # Store in session state
                        st.session_state['crawl_results'] = final_result
                        st.session_state['crawl_url'] = url
                        st.session_state['crawl_id'] = crawl_id
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
                elif "payment" in error_str or "402" in error_str:
                    st.info("💡 Check your Firecrawl account credits")
                
                if st.sidebar.checkbox("Show error details"):
                    st.exception(e)

    # Show previous crawl results if available
    if 'crawl_results' in st.session_state:
        st.markdown("---")
        st.subheader("📂 Previous Crawl Results")
        st.write(f"**Last crawled URL:** {st.session_state.get('crawl_url', 'N/A')}")
        
        if st.button("🔄 Show Last Crawl Results", key="show_last_results"):
            display_crawl_results(
                st.session_state['crawl_results'], 
                language,
                knowledge_source_id,
                use_url_titles
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
            
            # ARTICLE SELECTION WITH ENHANCED SEARCH AND PAGINATION
            st.subheader("📋 Select Articles to Upload")
            
            # Enhanced search functionality with content search
            search_term = st.text_input(
                "🔍 Search articles (name, URL, or content):", 
                placeholder="e.g., 'page not found' to find error pages"
            )
            
            # Filter articles based on search
            if search_term:
                filtered_articles = [
                    article for article in articles_data
                    if search_term.lower() in article['name'].lower() 
                    or search_term.lower() in article['url'].lower()
                    or search_term.lower() in article.get('content', '').lower()
                ]
                st.info(f"🔍 Found {len(filtered_articles)} articles matching '{search_term}'")
            else:
                filtered_articles = articles_data
            
            # Calculate selection counts for ALL articles (not just filtered)
            total_selected = sum(1 for i in range(len(articles_data)) 
                                if st.session_state.get(f"article_selected_{i}", True))
            
            if filtered_articles:
                # Global Select All / None buttons
                col1, col2, col3, col4 = st.columns(4)
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
                
                # Display selection counts
                with col3:
                    st.metric("Total Articles", len(articles_data))
                with col4:
                    st.metric("Currently Selected", total_selected)
                
                # PAGINATED ARTICLE DISPLAY WITH PERSISTENT SELECTION
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
                
                # Show sample payloads for first 3 selected articles to see the URL path IDs
                if selected_articles:
                    with st.expander(f"📋 Sample Payloads with URL Path IDs (First {min(3, len(selected_articles))} Selected Articles)"):
                        sample_articles = selected_articles[:3]  # Show first 3
                        for i, article in enumerate(sample_articles):
                            st.write(f"**Article {i+1}: {article['name']}**")
                            st.write(f"**Generated ID from URL path:** `{article['id']}`")
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
