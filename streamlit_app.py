import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, DateTime
from sqlalchemy import MetaData, cast, Date, func
from sqlalchemy import select, delete, insert, desc

metadata = MetaData()

user = Table(
    "user",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String),
)

training = Table(
    "training",
    metadata,
    Column("user", String, primary_key=True),
    Column("program", String),
    Column("duration", Integer),
    Column("ts", DateTime)
)

if not "id" in st.query_params:
    st.write("Inget id")
    st.stop()

id = st.query_params.id
s = st.connection('fitbois').session

sql_finduser = select(user).where(user.c.id == id)
finduser = s.execute(sql_finduser).first()

if not len(finduser):
    st.write("Fel id")
    st.stop()

# Användare accepterad!

sql_prevtraining = select(training).where(training.c.user == id).order_by(desc(training.c.ts)).limit(1)
prevtraining = s.execute(sql_prevtraining).first()

prev_program = "Välj ett träningsprogram eller skriv in ett eget"
prev_duration = 15

if prevtraining:
    prev_program = prevtraining.program
    prev_duration = prevtraining.duration

sql_earlierprograms = select( # XXX Lägg till tidsgräns på tidigare
    training.c.program,
    func.max(training.c.ts).label('max_date')
).where(
    training.c.user == id
).group_by(
    training.c.program
).order_by(
    desc('max_date')
)

earlierprograms = s.execute(sql_earlierprograms).all() # Lägg in i listan

st.write("Logga träning för", finduser.name)

duration = st.slider("Träningstid i minuter", value=prev_duration, min_value=5, max_value=60)

program = st.selectbox(
    "Träningsprogram",
    ["Stretch", "Paolo Nybörjare 1", "Paolo Nybörjare 2", "Paolo Medel", "Paolo Utmanare", "Löp 5k", "Löp 10k"],
    index=None,
    placeholder=prev_program,
    accept_new_options=True
)

if st.button("Logga träning"):

    sql_delete_today = delete(training
    ).where(training.c.user == id
    ).where(func.date(training.c.ts) >= func.curdate()
    )

    sql_insert_today = insert(training).values(user=id, program=program, duration=duration)
   
    print(sql_delete_today)

    s.execute(sql_delete_today)
    s.execute(sql_insert_today)

    s.commit()
    st.balloons()
