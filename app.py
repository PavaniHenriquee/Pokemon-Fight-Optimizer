import streamlit as st

st.title("PBS")

my_pk = st.selectbox("choose",["Char","Squ"])
opp_pk = st.selectbox("choose opp", ["Char", "Squ"])

st.write = (f"You chose **{my_pk}** vs **{opp_pk}**")

if st.button("Start Battle"):
    st.write("Battle started")
