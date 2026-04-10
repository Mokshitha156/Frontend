import matplotlib.pyplot as plt
import streamlit as st

def patient_line_chart():
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"]
    values = [25, 28, 32, 30, 36, 41, 47]

    fig, ax = plt.subplots()
    ax.plot(months, values, marker='o')
    ax.set_title("Patient Analytics")
    ax.set_ylabel("Patients")

    st.pyplot(fig)

def appointment_donut_chart():
    labels = ["Male", "Female", "Child", "Senior"]
    sizes = [40, 30, 20, 10]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    centre_circle = plt.Circle((0, 0), 0.70, fc='white')
    fig.gca().add_artist(centre_circle)

    ax.set_title("Appointments Overview")
    st.pyplot(fig)
