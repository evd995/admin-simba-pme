from google.oauth2 import service_account
from google.cloud import firestore
import openai
from openai import OpenAI
import streamlit as st
import logging
import time

openai.api_key = st.secrets["OPENAI_API_KEY"]
openai_client = OpenAI(default_headers={"OpenAI-Beta": "assistants=v2"})

GCP_PROJECT = st.secrets["GCP_PROJECT"]
COURSE_ID = st.secrets["COURSE_ID"]

import json
creds = service_account.Credentials.from_service_account_info(st.secrets["FIRESTORE_CREDS"])
db = firestore.Client(credentials=creds, project=GCP_PROJECT)

def get_activity_thread(activity_id):
    user_id = st.session_state['username']
    course_db = db.collection('courses').document(str(COURSE_ID))
    users_db = course_db.collection('users')
    user_db = users_db.document(str(user_id))

    # Get thread_id from Firebase
    activity_thread = user_db.collection('activity_threads').document(activity_id)

    # If thread_id is None, create a new thread
    activity_thread_exists = activity_thread.get().exists
    if not activity_thread_exists:
        thread = openai_client.beta.threads.create()
        activity_thread.set({'thread_id': thread.id})
        create_message("Hola!", thread.id, st.secrets["ASSISTANT_IDS"][activity_id])

    return activity_thread.get().get('thread_id')


def get_messages(thread_id):
    # Get messages from thread
    messages = openai_client.beta.threads.messages.list(
         thread_id=thread_id,
         order="asc",
         limit=100
    )
    
    clean_messages = []
    for message in messages.data[1:]:
        clean_messages.append({
            "role": message.role if message.role == "user" else "model",
            "content": message.content[0].text.value
        })

    # Reassign roles to messages
    return clean_messages


def create_message(input_message, thread_id, assistant_id):
    message = openai_client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=input_message,
    )

    logging.info('Starting run...')
    # The assistant's id belongs to the run, not the thread
    run = openai_client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )

    logging.info('Checking run status...')
    run = openai_client.beta.threads.runs.retrieve(
        thread_id=thread_id,
        run_id=run.id
    )
    
    while run.status not in ["completed", "failed", "cancelled", "expired"]:
        run = openai_client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )
        time.sleep(.1)

    logging.info('Run completed.')

    messages = openai_client.beta.threads.messages.list(
            thread_id=thread_id,
    )
    response_message = messages.data[0].content[0].text.value
    logging.info(f'Response message: {response_message}')
    return response_message


def get_all_users_messages(activity_id):
    course_db = db.collection('courses').document(str(COURSE_ID))
    users_db = course_db.collection('users')
    users_stream = users_db.stream()
    conversations = []
    for user_doc in users_stream:
        activity_db = users_db.document(user_doc.id).collection('activity_threads').document(activity_id)
        thread_id = activity_db.get().get('thread_id')
        thread_messages = get_messages(thread_id)
        conversations.append(thread_messages)
    return conversations

def summarize_responses(activity_id):
    conversations = get_all_users_messages(activity_id)
    
    SYSTEM_PROMPT = "A continuación verás una serie de conversaciones. Resume brevemente las respuestas de **los usuarios (user)**. No consideres las respuestas de modelo (model). Termina con una sugerencia de tema para una discusión grupal."
    USER_PROMPT = f"---- CONVERSACIONES ----\n{conversations}"

    response = openai_client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT}
        ]
    )

    response_message = response.choices[0].message.content

    st.write(response_message)