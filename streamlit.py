import streamlit as st
import requests
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import os, json

def create_connection():
    conn = psycopg2.connect(
        dbname=os.getenv("POSTGRES_DBNAME"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT")
    )
    return conn

def get_chat_history():
    conn = create_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT DISTINCT ON (thread_id) 
            thread_id, 
            assistant_id, 
            tenant_id, 
            message_text, 
            created_at, 
            id
        FROM messages
        ORDER BY thread_id, created_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return pd.DataFrame(rows)

def get_messages(thread_id):
    conn = create_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT message_text FROM messages
        WHERE thread_id = %s
        ORDER BY created_at
    """, (thread_id,))
    messages = cur.fetchall()
    cur.close()
    conn.close()
    
    flattened_messages = []
    for msg in messages:
        try:
            parsed_messages = json.loads(msg['message_text'])
            flattened_messages.extend(parsed_messages)
        except json.JSONDecodeError:
            st.error(f"Error parsing JSON for message: {msg['message_text']}")
    
    return flattened_messages

def send_message(thread_id, assistant_id, tenant_id, query_text):
    base_url = "http://localhost:8501/api/v1/query"
    url = f"{base_url}?assistant_id=83a78f36-2b72-4432-b197-881be8457fa4&tenant_id=2"
    
    if thread_id:
        url += f"&thread_id={thread_id}"
    
    payload = {
        "query_text": query_text
    }
    
    response = requests.post(url, json=payload)
    return response.json()

if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'current_thread_id' not in st.session_state:
    st.session_state.current_thread_id = None
if 'current_assistant_id' not in st.session_state:
    st.session_state.current_assistant_id = "default_assistant_id"
if 'current_tenant_id' not in st.session_state:
    st.session_state.current_tenant_id = "default_tenant_id"
if 'is_new_chat' not in st.session_state:
    st.session_state.is_new_chat = False

st.sidebar.title("Chat History")

if st.sidebar.button("New Chat"):
    st.session_state.current_thread_id = None
    st.session_state.messages = []
    st.session_state.is_new_chat = True
    st.rerun()

history = get_chat_history()
selected_thread = st.sidebar.selectbox(
    "Select a chat:",
    [""] + list(history['thread_id']),
    format_func=lambda x: f"Thread {x} - {history[history['thread_id'] == x]['created_at'].iloc[0]}" if x else "Select a chat"
)

if selected_thread and selected_thread != st.session_state.current_thread_id:
    st.session_state.current_thread_id = selected_thread
    st.session_state.messages = get_messages(selected_thread)
    selected_row = history[history['thread_id'] == selected_thread].iloc[0]
    st.session_state.current_assistant_id = selected_row['assistant_id']
    st.session_state.current_tenant_id = selected_row['tenant_id']
    st.session_state.is_new_chat = False

chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

response_placeholder = st.empty()

if prompt := st.chat_input("Type your message here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with chat_container.chat_message("user"):
        st.write(prompt)

    with response_placeholder.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = send_message(
                st.session_state.current_thread_id,
                st.session_state.current_assistant_id,
                st.session_state.current_tenant_id,
                prompt
            )

            if st.session_state.is_new_chat or not st.session_state.current_thread_id:
                st.session_state.current_thread_id = response.get('thread_id')
                st.session_state.is_new_chat = False

            if response.get('message') == "Query executed":
                assistant_response = response.get('result', {}).get('response', 'No response')
            else:
                assistant_response = 'An error occurred while processing your request.'
            
            st.write(assistant_response)

    st.session_state.messages.append({"role": "assistant", "content": assistant_response})

if st.session_state.is_new_chat:
    st.info("This is a new chat session. Type a message to start the conversation.")
elif not st.session_state.current_thread_id:
    st.info("Please select a chat or start a new one to begin messaging.")