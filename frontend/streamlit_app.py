import streamlit as st
import requests

st.title("DevOps Build Failure Predictor")

duration = st.number_input("Build Duration (ms)")
if st.button("Predict Build Result"):
    res = requests.post("http://localhost:8000/predict", json={"duration": duration})
    st.success(f"Prediction: {res.json()['prediction']}")
