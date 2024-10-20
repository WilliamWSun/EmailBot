import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
from openai import OpenAI
import streamlit as st
import time
import difflib
import json

openai_api_key = os.getenv("OPENAI_API_KEY") 
if not openai_api_key:
    raise Exception("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
client = OpenAI(api_key=openai_api_key)


def normalize_url(url):
    parsed_url = urlparse(url)
    normalized = parsed_url._replace(query="", fragment="").geturl()
    return normalized.rstrip('/')  

def extract_core_content_no_chunking(soup):
    important_tags = ['h1', 'h2', 'h3', 'p', 'li'] 
    text_content = []

    for tag in important_tags:
        for element in soup.find_all(tag):
            text_content.append(element.get_text())

    return ' '.join(text_content)

def summarize_page(content):
    prompt = f"Summarize the following content, extracting key points and relevant information while ignoring boilerplate and repetitive content:\n\n{content}"
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  
            messages=[
                {"role": "system", "content": "You are a summarization assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,  
            temperature=0.5
        )
        summary = response.choices[0].message.content
        return summary.strip()  

    except Exception as e:
        print(f"Error summarizing HTML: {str(e)}")
        return ""

stop_recursion = False
def scrape_website_recursive(url, visited, max_depth=20, max_links_per_page=3):
    global stop_recursion  

    unwanted_keywords = ["webinar", "podcast", "blog"]

    if stop_recursion:
        return ""

    url = normalize_url(url)

    if any(keyword in url for keyword in unwanted_keywords):
        print(f"Skipping URL due to unwanted keyword: {url}")
        return ""

    if url in visited:
        return ""

    if max_depth == 0:
        print("Max depth reached. Stopping recursion.")
        stop_recursion = True  
        return ""

    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        visited.add(url)

        core_content = extract_core_content_no_chunking(soup)
        summarized_text = summarize_page(core_content)

        links_visited = 0
        combined_summary = summarized_text

        for link in soup.find_all('a', href=True):

            if links_visited >= max_links_per_page:
                print(f"Reached max links per page ({max_links_per_page}). Stopping further visits.")
                break  

            next_url = urljoin(url, link['href'])  
            next_url = normalize_url(next_url) 

            if urlparse(url).netloc == urlparse(next_url).netloc:
                if next_url not in visited:
                    if not stop_recursion: 
                        links_visited += 1 
                        print(f"Adding {next_url} to the crawl queue.")
                        time.sleep(0.25) 
                        combined_summary += scrape_website_recursive(next_url, visited, max_depth - 1)

        return combined_summary

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch {url}: {e}")
        return ""


def load_edits_log():
    try:
        with open("email_edits_log.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_edits_log(original, edited, diff):
    edits_log = load_edits_log()
    new_entry = {"original": original, "edited": edited, "diff": diff}
    edits_log.append(new_entry)
    with open("email_edits_log.json", "w") as f:
        json.dump(edits_log, f, indent=4)

def generate_refined_prompt(company_info):
    edits_log = load_edits_log()
    if not edits_log:
        return f"Here is some information about the company: {company_info}"

    common_phrases = [entry["diff"] for entry in edits_log if entry["diff"]]
    learning_summary = "\n".join(common_phrases[:10]) 

    return f"""
    Here is some information about the company: {company_info}

    You are also an AI email assistant that has been trained to adapt its writing style based on historical editing patterns. 
    You have access to a collection of previous emails and their corresponding edits, which demonstrate my preferred writing style 
    and content preferences.

    I am providing you with a collection of previous email drafts and their edited versions. Each entry shows:
    * The original email you generated
    * My edited version
    * The differences between your original email and the edited one
    {learning_summary}

    Before drafting any new emails, please:
    1. Take note of the differences between your original drafts and my edits
    2. Note patterns in:
        Tone adjustments (formal vs casual)
        Common phrases I add or remove
        Structural changes I make
        Length preferences
        Greeting and closing styles
        Any specific vocabulary choices
    
    If you notice I consistently make certain types of edits (e.g., making things more concise, adding specific phrases), proactively 
    incorporate these preferences
    Maintain the core message while adapting the style to match my demonstrated preferences
    If you're unsure about a particular aspect, default to the style most commonly seen in my edited versions
    """


def generate_email(company_info):
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
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional email writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"Error generating email: {str(e)}"

def track_changes(original, edited):
    diff = list(difflib.unified_diff(
        original.splitlines(), edited.splitlines(), lineterm=''
    ))
    return "\n".join(diff)

def regenerate_email(first_email, company_info, regeneration_comments):
    refined_prompt = generate_refined_prompt(company_info)
    prompt = f"""
    You are a B2B software investor at a large sized growth equity fund (JMI Equity) and writing an email to a company that you are interested in getting on a call with to learn more. 
    In the email it is important to be personalized and show knowledge in the company and the market it operates in. 
    Things to talk about include the market, the company. competitors, differentiators of the company, thesis you have in the space, tailwinds, etc. 
    Be concise but still include all relevant information. 
    
    Here was the original email you generated: {first_email}
    
    Generate me a new email for this company with the following comments regarding the original email: {regeneration_comments}

    {refined_prompt}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  
            messages=[
                {"role": "system", "content": "You are a professional email writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"Error generating email: {str(e)}"

def ask_openai(question, context=""):
    """Function to query OpenAI GPT model"""
    prompt = f"Answer the following question using the context provided: \n\nContext: {context}\n\nQuestion: {question}"
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=500
        )
        answer = response.choices[0].message.content
        return answer.strip()
    except Exception as e:
        return f"Error querying OpenAI: {str(e)}"


######### GUI ###########


st.title("Automated CEO Email Generator")

company_url = st.text_input("Enter Company Website URL")

if "original_email" not in st.session_state:
    st.session_state.original_email = ""
if "comments" not in st.session_state:
    st.session_state.comments = ""
if "email_generated" not in st.session_state:
    st.session_state.email_generated = False 
if "company_info" not in st.session_state:
    st.session_state.company_info = ""  
if "visited_set" not in st.session_state:
    st.session_state.visited_set = set()  

if st.button("Generate Email"):
    st.write("Processing... please wait.")

    if not st.session_state.company_info:
        st.session_state.company_info = scrape_website_recursive(company_url, st.session_state.visited_set)

    st.session_state.original_email = generate_email(st.session_state.company_info)
    st.session_state.email_generated = True  

if st.session_state.email_generated:
    edited_email = st.text_area("Edit the Generated Email", st.session_state.original_email, height=300)

    comments_for_changes = st.text_area("Comments to Regenerate", st.session_state.comments, height=100)

    if st.button("Regenerate"):
        if edited_email and comments_for_changes:
            st.write("Processing... please wait.")
            st.session_state.original_email = regenerate_email(edited_email, st.session_state.company_info, comments_for_changes)
        else:
            st.warning("Please provide both comments and edits to regenerate the email.")

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
else:
    st.warning("Please generate an email before proceeding.")

#### Chat bot section ########

col1, col2 = st.columns([2, 3])

with col1:
    st.write("Ask the chatbot questions about the company or general questions:")

    user_question = st.text_input("Enter your question here:")
    
    chat_context = st.radio(
        "What context should the chatbot consider?",
        ('Use company info', 'General question')
    )
    
    if st.button("Ask Chatbot"):
        if chat_context == 'Use company info' and "company_info" in st.session_state:
            answer = ask_openai(user_question, context=st.session_state.get("company_info", ""))
        else:
            answer = ask_openai(user_question)
        
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = ""
        st.session_state.chat_history += f"**You:** {user_question}\n\n**Bot:** {answer}\n\n"
    
with col2:
    st.write("Chat History:")
    
    st.text_area("Conversation", value=st.session_state.get("chat_history", ""), height=400, disabled=True)