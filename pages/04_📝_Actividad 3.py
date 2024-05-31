import streamlit as st
from chatbot_helper import summarize_responses

activity_id = 'Actividad_3'
st.button("Resumir respuestas", on_click=summarize_responses(activity_id))

