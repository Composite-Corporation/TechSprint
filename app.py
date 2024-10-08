import streamlit as st
from dotenv import load_dotenv

from utils.agent import Agent
from components import (
    authenticate,
    home_page,
    supplier_details,
)
from compositeai.tools import GoogleSerperApiTool, WebScrapeTool
from compositeai.drivers import OpenAIDriver


# Load environment variables
load_dotenv()


# Set up page session state
if "chat_agent" not in st.session_state:
    st.session_state["chat_agent"] = Agent(
        driver=OpenAIDriver(
            model="gpt-4o-mini", 
            seed=1337,
        ),
        description=f"""
        You are an analyst searches the web for a company's sustainability and ESG information.

        Use the Google search tool to find relevant data sources and links.
        Then, use the Web scraping tool to analyze the content of links of interest.
        Cite quotes from the source to support your answer.
        Provide a link to the sources.

        Here is an example response with the format you should respond:
            - [INSERT EXPLANATION ON WHAT YOU HAVE FOUND]
            - [INSERT KEY QUOTES THAT YOU HAVE FOUND]
            - [INSERT LINKS TO SOURCES]
        """,
        tools=[
            WebScrapeTool(),
            GoogleSerperApiTool(),
        ],
        max_iterations=20,
    )
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "page" not in st.session_state:
    st.session_state["page"] = {
        "name": "Auth",
        "data": None,
    }


# Main app function
if __name__=="__main__":
    st.set_page_config(page_title="Composite.ai", page_icon="♻️")

    if st.session_state["page"]["name"] == "Auth":
        authenticate()
    elif st.session_state["page"]["name"] == "Home":
        home_page()
    elif st.session_state["page"]["name"] == "Supplier Details":
        supplier_details()
    else:
        st.error(body="Page Not Found.")
