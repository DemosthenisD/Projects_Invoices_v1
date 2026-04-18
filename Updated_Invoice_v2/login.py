import streamlit as st
import toml

# Load secrets
user = st.secrets["credentials"]["USER"]
password = st.secrets["credentials"]["PASSWORD"]

# Initialize session state for login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Create login form
def login():
    st.title("Login")
    username = st.text_input("Username")
    password_input = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if username == user and password_input == password:
            st.success("Logged in successfully!")
            st.session_state.logged_in = True
        else:
            st.error("Invalid username or password")