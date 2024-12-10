import streamlit as st
from pydantic import BaseModel, Field
from typing import Optional, List
from compositeai.agents import AgentResult
from utils.auth import auth



# Class for storing chat message data
class ChatMessage(BaseModel):
    name: str = Field(description="Name of the chat message sender, e.g. 'user' or 'assistant'")
    content: str = Field(description="Content of the chat message")
    info: Optional[List[str]] = Field(description="Additional supporting infomation to be displayed in expander", default=None)


# Helper function to create chat bubble widgets
def chat_bubble(chat: ChatMessage):
    name = chat.name
    if name == "user":
        avatar = "👨‍💻"
    else:
        avatar="🤖"
    with st.chat_message(name=name, avatar=avatar):
        st.markdown(chat.content)
        if chat.info:
            with st.expander(label="Intermediate Steps", expanded=False) as expander:
                for item in chat.info:
                    st.markdown(item)


def confirm_delete_account(user_id: str, email: str):

    st.markdown("Are you sure? This action cannot be undone. You will lose access to your organization.")
    col1, col2 = st.columns([0.25, 1])

    with col1:
        if st.button(label="Confirm", type="primary"):
            # Attempt user account deletion
            status, message = auth.delete_user(user_id)
            print(status)

            if status:
                # Display deletion confirmation
                st.success(message)

                # Upon log out, clear entire session state
                st.session_state["page"] = {
                    "name": "Auth",
                    "data": None,
                }

                ## Log event
                #log.account_deletion_event(user_id=user_id, email=email)
            else:
                # Otherwise, display error messeage
                st.error(message)

            # Rerun app regardless
            st.rerun()
    with col2:
        if st.button(label="Cancel"):
            st.rerun()


@st.dialog(title="User Settings")
def user_settings_dialog():
    if st.button(label="Sign Out", use_container_width=True):
        st.session_state["page"] = {
            "name": "Auth",
            "data": None,
        }
        st.rerun()
    if st.button(label="Delete Account", type="primary", use_container_width=True):
        # Retrieve account info
        uid = st.session_state["page"]["data"]["session_data"]["localId"]
        email = st.session_state["page"]["data"]["session_data"]["email"]
        confirm_delete_account(user_id=uid, email=email)


# Chat widget for supplier details page
def chat_suppliers():
    # Retrieve agent from session state
    agent = st.session_state["chat_agent"]

    # Setup sidebar chat
    with st.sidebar:
        # Display CompositeAI logo
        st.image("static/composite.png", output_format="PNG", width=300)

        # Display sidebar title and user settings button
        col1, col2 = st.columns([0.8, 0.2])
        with col1:
            st.write("## **AI Assistant**")
        with col2:
            if st.button(label=":material/person:", use_container_width=True):
                user_settings_dialog()

        # Container of chat messages
        chat_container = st.container(height=450)
        with chat_container:
            # Display intro chat message
            chat_bubble(
                chat=ChatMessage(
                    name="assistant", 
                    content=f"Hi! I can help you with any questions you might have about your suppliers.",
                ),
            )

            # Display all chat history in session state
            for chat in st.session_state["chat_history"]:
                chat_bubble(chat=chat)

        # User input field and logic
        if user_input := st.chat_input(placeholder="Ask any question here"):
            with chat_container:
                # Create user chat
                user_chat = ChatMessage(name="user", content=user_input)
                chat_bubble(chat=user_chat)
                st.session_state["chat_history"].append(user_chat)

                # Process AI response and display intermediate steps
                intermediate_steps = []
                with st.chat_message(name="assistant", avatar="🤖"):
                    with st.status("AI Processing...") as status:
                        for chunk in agent.execute(user_input, stream=True):
                            if isinstance(chunk, AgentResult):
                                agent_result = chunk.content
                                status.update(label="AI Processing Complete.", state="complete", expanded=False)
                            else:
                                intermediate_steps.append(chunk.content)
                                with st.container(border=True):
                                    st.markdown(chunk.content)

                # Add AI response to chat history
                ai_chat = ChatMessage(name="assistant", content=agent_result, info=intermediate_steps)
                st.session_state["chat_history"].append(ai_chat)

            # Rerun to update chat history
            st.rerun()
