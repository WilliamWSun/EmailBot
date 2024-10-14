import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
from openai import OpenAI
import streamlit as st
import time
import difflib
import json
from collections import deque

openai_api_key = os.getenv("OPENAI_API_KEY") 
# or st.secrets.get("OPENAI_API_KEY")
if not openai_api_key:
    raise Exception("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=openai_api_key)



def normalize_url(url):
    """Normalize URL by removing query parameters, fragments, and trailing slashes."""
    parsed_url = urlparse(url)
    normalized = parsed_url._replace(query="", fragment="").geturl()
    return normalized.rstrip('/')  # Remove trailing slash

stop_recursion = False
def scrape_website_recursive(url, visited, max_depth=18, max_links_per_page=4):
    global stop_recursion  # Use the global stop_recursion flag

    # If stop_recursion is True, halt all recursion
    if stop_recursion:
        return ""

    # Print the current URL and visited set for debugging
    # print(f"Visiting: {url}")
    #print(f"Visited so far: {visited}")

    # Normalize the URL to prevent duplicate visits
    url = normalize_url(url)

    # Stop if the URL has been visited or max depth is 0
    if url in visited:
        # print(f"Skipping {url} - already visited.")
        return ""

    if max_depth == 0:
        print("Max depth reached. Stopping recursion.")
        stop_recursion = True  # Set the global flag to stop further recursion
        return ""

    try:
        # Fetch the content of the URL
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Mark the current URL as visited
        visited.add(url)

        # Extract visible text from the page
        text = ' '.join([p.get_text() for p in soup.find_all('p')])

        links_visited = 0

        # Recursively visit all internal links on the page
        for link in soup.find_all('a', href=True):

            if links_visited >= max_links_per_page:
                print(f"Reached max links per page ({max_links_per_page}). Stopping further visits.")
                break  # Stop visiting more links from this page

            next_url = urljoin(url, link['href'])  # Make absolute URL
            next_url = normalize_url(next_url)  # Normalize the URL

            # Ensure the link is internal and not visited
            if urlparse(url).netloc == urlparse(next_url).netloc:
                if next_url not in visited:
                    if not stop_recursion:  # Only add if recursion is still allowed
                        links_visited += 1 
                        print(f"Adding {next_url} to the crawl queue.")
                        time.sleep(1)  # Optional: Be polite to the server
                        text += scrape_website_recursive(next_url, visited, max_depth - 1)
                #     else:
                #         print(f"Skipping {next_url} - recursion stopped.")
                # else:
                #     print(f"Skipping {next_url} - already visited.")
        return text

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch {url}: {e}")
        return ""
    
# def scrape_website_recursive(url, visited, max_depth=5):
    # Print the current URL and visited set for debugging
    

    # Normalize the URL to prevent duplicate visits
    url = normalize_url(url)

    print(f"Visiting: {url}")
    print(f"Visited so far: {visited}")

    # Stop if the URL has been visited or the depth limit is reached
    if url in visited or max_depth == 0:
        # print(f"Skipping {url} - already visited or max depth reached.")
        return ""

    try:
        # Fetch the content of the URL
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Mark the current URL as visited
        visited.add(url)

        # Extract visible text from the page
        text = ' '.join([p.get_text() for p in soup.find_all('p')])

        # Recursively visit all internal links on the page
        for link in soup.find_all('a', href=True):
            next_url = urljoin(url, link['href'])  # Make absolute URL
            next_url = normalize_url(next_url)  # Normalize the URL

            # Ensure the link is internal and not visited
            if urlparse(url).netloc == urlparse(next_url).netloc:
                if next_url not in visited:
                    print(f"Adding {next_url} to the crawl queue.")
                    time.sleep(1)  # Optional: Be polite to the server
                    text += scrape_website_recursive(next_url, visited, max_depth - 1)
                # else:
                #     print(f"Skipping {next_url} - already visited.")
        return text

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch {url}: {e}")
        return ""



    
def scrape_website(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check for HTTP errors
        soup = BeautifulSoup(response.content, 'html.parser')
        # Extract all visible text from <p> tags (you can expand this logic as needed)
        text = ' '.join([p.get_text() for p in soup.find_all('p')])
        return text
    except requests.exceptions.RequestException as e:
        return f"Error scraping website: {str(e)}"
    
# Load previous edits from JSON file
def load_edits_log():
    try:
        with open("email_edits_log.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# Save edits to JSON log
def save_edits_log(original, edited, diff):
    edits_log = load_edits_log()
    new_entry = {"original": original, "edited": edited, "diff": diff}
    edits_log.append(new_entry)
    with open("email_edits_log.json", "w") as f:
        json.dump(edits_log, f, indent=4)

# Analyze past edits to modify prompt dynamically
def generate_refined_prompt(company_info):
    edits_log = load_edits_log()
    if not edits_log:
        return f"Here is some information about the company: {company_info}"

    # Analyze common changes made by the user
    common_phrases = [entry["diff"] for entry in edits_log if entry["diff"]]
    learning_summary = "\n".join(common_phrases[:5])  # Limit to the top 3 changes

    # Modify the prompt based on the learning summary
    return f"""
    Here is some information about the company: {company_info}

    Based on previous feedback and edits, please emphasize:
    {learning_summary}
    """


def generate_email(company_url):
    visited_set = set()
    company_info = scrape_website_recursive(company_url, visited_set)
    refined_prompt = generate_refined_prompt(company_info)
    prompt = f"""
    You are a B2B software investor at a large sized growth equity fund (JMI Equity) and writing an email to a company that you are interested in getting on a call with to learn more. 
    In the email it is important to be personalized and show knowledge in the company and the market it operates in. 
    Things to talk about include the market, the company. competitors, differentiators of the company, thesis you have in the space, tailwinds, etc. 
    Be concise but still include all relevant information. 
    Here are some good templates to take inspiration from:

    "[Founder name-

    Hope all is well. [Congratulate them on some achievement or recent event].

    From my outside-in view the [whatever industry this company falls in and some kind of tailwind or pain point that incumbents are not able to solve]. Looking at the next generation of solutions, 
    we believe that [company name] stands out with its unique approach to [something that shows you know the company well and is a differentiator of the company from the rest of the market].

    For some background on JMI, we are an $8B+ growth fund that's backed 180+ B2B software companies over the last 30 years.

    I'd love to hear more about your business and explore potential opportunities, even past capital. Let me know when works best to chat in the next week or two!

    Best,
    William"

    Now, write a personalized email introducing yourself, discussing the market, their business, and suggesting a call. Make sure the subject line is long and creative and hooky for the founder to read.

    {refined_prompt}
    """

    try:
        # Use the Chat API instead of the old Completion API
        response = client.chat.completions.create(
            model="gpt-4o",  # or "gpt-4" if you have access
            messages=[
                {"role": "system", "content": "You are a professional email writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        # Extract the email content from the response
        return response.choices[0].message.content

    except Exception as e:
        return f"Error generating email: {str(e)}"


def track_changes(original, edited):
    diff = list(difflib.unified_diff(
        original.splitlines(), edited.splitlines(), lineterm=''
    ))
    return "\n".join(diff)

# # Log changes to a file
# def log_edits(diff):
#     with open("email_edits_log.txt", "a") as log_file:
#         log_file.write(diff + "\n\n")


# Streamlit UI
st.title("Automated CEO Email Generator")

# Input field for company URL
company_url = st.text_input("Enter Company Website URL")

if "original_email" not in st.session_state:
    st.session_state.original_email = ""

# Button to generate the email
if st.button("Generate Email"):
    st.write("Processing... please wait.")
    st.session_state.original_email = generate_email(company_url)

# Display the generated email in a text area for edits
edited_email = st.text_area("Edit the Generated Email", st.session_state.original_email, height=300)

# Save edits and log them when the button is clicked
if st.button("Save Edits"):
    if edited_email and st.session_state.original_email:
        diff = track_changes(st.session_state.original_email, edited_email)
        if diff:
            save_edits_log(st.session_state.original_email, edited_email, diff)
            st.success("Edits saved and logged! Here are the changes:")
            st.code(diff, language="diff")
        else:
            st.info("No changes detected.")
    else:
        st.warning("Please generate an email first.")