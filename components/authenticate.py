import sys
import os

# # Recognize packages from utils folder
# CWD = os.getcwd()
# sys.path.insert(1, CWD + "/utils")

# from utils.log import Log
from utils.auth import auth
# from utils.db import DB
import streamlit as st

# db = DB()
# log = Log()

# Account authentication page component
def authenticate():

    # Set logo and title
    st.image("static/composite.png", output_format="PNG", width=400)
    st.header(body="**Account Authentication**", anchor=False)

    # Tabs for Sign Up, Login, and Forgot Password
    tab1, tab2, tab3 = st.tabs(["Sign In", "Sign Up", "Forgot Password"])

    with tab1:
        st.write("**Log into an Existing Account**")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Sign In"):
            session_data, message = auth.sign_in(email, password)
            if session_data:
                st.session_state["page"] = {
                    "name": "Home",
                    "data": {
                        "processing_supplier": False,
                        "session_data": session_data,
                    },
                }
                st.success(message)
                # log.login_event(user_id=session["localId"], email=email)
                st.rerun()
            else:
                st.error(message)

    with tab2:
        st.write("**Create a New Account**")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        st.selectbox(
            label="Join Organization",
            options=("Scientific Laboratory Supplies (SLS) Ltd."),
            index=0,
            disabled=True,
        )
        
        if st.button("Sign Up"):
            if password != confirm_password:
                st.error("Passwords must match.")
            elif "@college.harvard.edu" not in email and "@scientific-labs.com" not in email:
                st.error("Your are not authorized to join this organization.")
            else:
                session_data, message = auth.sign_up(email, password)
                if session_data:
                    st.session_state["page"] = {
                        "name": "Home",
                        "data": {
                            "processing_supplier": False,
                            "session_data": session_data,
                        },
                    }
                    st.success(message)
                    # log.account_creation_event(user_id=session["localId"], email=email)
                    # db.create_user(uid=session["localId"])
                    st.rerun()
                else:
                    st.error(message)
        
    with tab3:
        st.write("**Reset Your Password**")
        email = st.text_input("Email", key="forgot_email")
        
        if st.button("Reset Password"):
            status, message = auth.reset_password(email)
            if status:
                st.success(message)
                # log.password_reset_event(email=email)
            else:
                st.error(message)
            