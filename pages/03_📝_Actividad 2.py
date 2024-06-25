import streamlit as st
from chatbot_helper import summarize_responses

activity_id = ('Actividad_2',)
st.button("Resumir respuestas", on_click=summarize_responses, args=activity_id)

