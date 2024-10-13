import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
from openai import OpenAI
import streamlit as st
import time




def normalize_url(url):
    """Normalize URL by removing query parameters and fragments."""
    parsed_url = urlparse(url)
    return parsed_url._replace(query="", fragment="").geturl()

def scrape_website_recursive(url, visited=None, max_depth=2):
    if visited is None:
        visited = set()  # To avoid visiting the same link multiple times

    # Normalize the URL to prevent duplicate visits
    url = normalize_url(url)

    if max_depth == 0 or url in visited:
        return ""  # Stop if max depth reached or link already visited

    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Mark the current URL as visited
        visited.add(url)

        # Extract all visible text from the page
        text = ' '.join([p.get_text() for p in soup.find_all('p')])

        # Find all internal links and recursively scrape them
        for link in soup.find_all('a', href=True):
            next_url = urljoin(url, link['href'])
            next_url = normalize_url(next_url)  # Normalize the URL

            # Ensure the link is internal by checking the domain
            if urlparse(url).netloc == urlparse(next_url).netloc and next_url not in visited:
                print(f"Visiting: {next_url}")
                time.sleep(1)  # Optional: Sleep to avoid overloading the server
                text += scrape_website_recursive(next_url, visited, max_depth - 1)

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
    



# Set your OpenAI API key
# openai_api_key = os.getenv("OPENAI_API_KEY")
openai_api_key = st.secrets["OPENAI_API_KEY"]
if not openai_api_key:
    raise Exception("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=openai_api_key)


def generate_email(company_url):
    company_info = scrape_website(company_url)
    prompt = f"""
    You are a B2B software investor at a large sized growth equity fund (JMI Equity) and writing an email to a company that you are interested in getting on a call with to learn more. 
    In the email it is important to be personalized and show knowledge in the company and the market it operates in. 
    Things to talk about include the market, the company. competitors, differentiators of the company, thesis you have in the space, tailwinds, etc. 
    Be concise but still include all relevant information. 
    Here are three good templates to take inspiration from:

    "Hi [Founder name],
    Hope you're doing well - we've yet to meet, but I wanted to congratulate you on [recent relevant event regarding the company or the founder.]

    [Talk about the current state of the market and how the company is differentiating itself and creating a moat for itself among competitors.]

    Over the years, we've invested extensively in [the industry that the company operates in, specifically within (portfolio companies of JMI that fall into the same industry).] 
    From what we've gathered, [talk about any sleepy incumbents in the space and how they are falling behind to growing startups. talk about this company is wedging itself into the flaws of competitors, etc.]

    All this to say we're incredibly excited about what you've built at [company name], how you're looking [what they are doing that differentiates themselves], and we're eager to find ways to be helpful. 
    
    I'd love to find some time to connect over a quick call at your convenience. 

    Let me know what you think, and I'm happy to send through a calendar invite if schedule aligns.

    Best,
    William "

    "Hi [Founder Name],

    [Talk about the current state of the market and some of the tailwinds and pain points to really show you know where the company operates in. 
    Then tie it back to the company and how they are doing a great job in whatever they're doing for this specific market.]

    I really enjoyed reading/seeing/hearing about [something specific to the company - maybe its a blog post from their website, or a linkedin post, or a conference speech, anything that could have relevant information about 
    the company that shows that you as an investor have put time into looking at the coompany.] It's clear from that, that [company] provides signifcant value to the pain point in [said industry].

    If you have time in the next couple weeks, I'd love to connect, hear more about how you and your team are revolutionizing [whatever space the company operates in], and discuss how my firm can be helpful 
    as successful founders continue to scale their businesses. What's the best way to schedule a quick chat?

    Best,
    William"

    "[Founder name-

    Hope all is well. [Congratulate them on some achievement or recent event].

    From my outside-in view the [whatever industry this company falls in and some kind of tailwind or pain point that incumbents are not able to solve]. Looking at the next generation of solutions, 
    we believe that [company name] stands out with its unique approach to [something that shows you know the company well and is a differentiator of the company from the rest of the market].

    For some background on JMI, we are an $8B+ growth fund that's backed 180+ B2B software companies over the last 30 years.

    I'd love to hear more about your business and explore potential opportunities, even past capital. Let me know when works best to chat in the next week or two!

    Best,
    William"

    Now, write a personalized email introducing yourself, discussing the market, their business, and suggesting a call. Make sure the subject line is long and creative and hooky for the founder to read.

    Here is some information on the comapny:
    {company_info}
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


st.title("Automated CEO Email Generator")

# User input: Company website URL
company_url = st.text_input("Enter Company Website URL")

if st.button("Generate Email"):
    st.write("Processing... please wait.")
    # Call the scraping and email generation functions (defined later)
    
    email_draft = generate_email(company_url)
    st.text_area("Generated Email Draft", email_draft, height=300)



