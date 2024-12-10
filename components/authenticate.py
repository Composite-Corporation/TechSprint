import sys
import os

# # Recognize packages from utils folder
# CWD = os.getcwd()
# sys.path.insert(1, CWD + "/utils")

# from utils.log import Log
from utils.auth import auth
from utils.db import db
import streamlit as st

# db = DB()
# log = Log()

# Account authentication page component
def authenticate():

    # Set logo and title
    #st.image("static/composite.png", output_format="PNG", width=400)
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
                user_data = db.get_user(uid=session_data["localId"])
                user_org_id = user_data["org_id"]
                session_data["org_id"] = user_org_id
                st.session_state["page"] = {
                    "name": "Home",
                    "data": {
                        "processing_supplier": False,
                        "session_data": session_data,
                    },
                }
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with tab2:
        st.write("**Create a New Account**")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        org_name = st.selectbox(
            label="Join Organization",
            options=(
                "Scientific Laboratory Supplies (SLS) Ltd.",
                "Evonik Industries",
                "Arteco Coolants",
                "Alides",
                "Dutscher",
                "Gantrade Europe BV",
            ),
            index=0,
        )
        
        if st.button("Sign Up"):
            if password != confirm_password:
                st.error("Passwords must match.")
                return
            
            org_id = None
            org_error = False
            if "@college.harvard.edu" in email:
                org_id = "aeh6JBvXAkrbuDVaGQkG"
                org_error = org_name != "Scientific Laboratory Supplies (SLS) Ltd."
            elif "@scientific-labs.com" in email:
                org_id = "aeh6JBvXAkrbuDVaGQkG"
                org_error = org_name != "Scientific Laboratory Supplies (SLS) Ltd."
            elif "@evonik.com" in email:
                org_id = "YFFNUqZ8WFt4DLQ9FwvP"
                org_error = org_name != "Evonik Industries"
            elif "@arteco-coolants.com" in email:
                org_id = "s41UQTwtMZsueu5K3MZS"
                org_error = org_name != "Arteco Coolants"
            elif "@alides.be" in email:
                org_id = "cvyXtH4aNuKikh0MSWvM"
                org_error = org_name != "Alides"
            elif "@dutscher.com" in email:
                org_id = "mq7mcPrZ67wJRTcBiP9L"
                org_error = org_name != "Dutscher"
            elif "@gantrade.com" in email:
                org_id = "1VUdDwkZAhV5UP5anUZn"
                org_error = org_name != "Gantrade Europe BV"

            if org_id is None:
                st.error("Unrecognized organization.")
                return
            if org_error:
                st.error("You are not authorized to join this organization.")
                return
            
            session_data, message = auth.sign_up(email, password)
            if session_data:
                session_data["org_id"] = org_id
                st.session_state["page"] = {
                    "name": "Home",
                    "data": {
                        "processing_supplier": False,
                        "session_data": session_data,
                    },
                }
                st.success(message)
                db.create_user(uid=session_data["localId"], org_id=org_id)
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
            