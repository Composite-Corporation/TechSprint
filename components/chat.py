import streamlit as st
from pydantic import BaseModel, Field
from typing import Optional, List


# Class for storing chat message data
class Chat(BaseModel):
    name: str = Field(description="Name of the chat message sender, e.g. 'user' or 'assistant'")
    content: str = Field(description="Content of the chat message")
    info: Optional[List[str]] = Field(description="Additional supporting infomation to be displayed in expander", default=None)


# Helper function to create chat bubble widgets
def chat_bubble(chat: Chat):
    name = chat.name
    if name == "user":
        avatar = "👨‍💻"
    else:
        avatar="🤖"
    with st.chat_message(name=name, avatar=avatar):
        with st.container(border=True):
            st.markdown(chat.content)
        if chat.info:
            with st.expander(label="Intermediate Steps", expanded=False) as expander:
                for item in chat.info:
                    with st.container(border=True):
                        st.markdown(item)
                        