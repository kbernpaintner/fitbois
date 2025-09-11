import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, DateTime
from sqlalchemy import MetaData, cast, Date, func
from sqlalchemy import select, delete, insert, desc, join
from datetime import date
import pandas as pd


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
s = st.connection('fitbois', pool_recycle=3600).session

sql_finduser = select(user).where(user.c.id == id)
finduser = s.execute(sql_finduser).first()

if not finduser:
    st.write("Fel id")
    st.stop()

# Användare godkänd

st.header("Träningslogg " + finduser.name)

sql_prevlog = select(training).where(training.c.user == id).order_by(desc(training.c.ts)).limit(1)
prevlog = s.execute(sql_prevlog).first()

prev_program = "Välj ett program eller skriv in eget"
prev_duration = 15

if prevlog:
    prev_program = prevlog.program
    prev_duration = prevlog.duration
    st.write("Senast", prevlog.ts.date())
else:
    st.write("Första loggningen!")

sql_earlierprograms = select( # XXX Lägg till tidsgräns på tidigare
    training.c.program,
    func.max(training.c.ts).label('max_date')
).where(training.c.user == id
).where(func.datediff(func.curdate(), training.c.ts) < 30
).group_by(training.c.program
).order_by(desc('max_date')
)

earlierprograms = s.execute(sql_earlierprograms).all()
p = [program for program, ts in earlierprograms]

standardprograms = ["Stretch", "Paolo Nybörjare", "Paolo Medel", "Paolo Utmanare", "Löpning 3k", "Löpning 5k", "Löpning 10k"]
p.extend(sp for sp in standardprograms if sp not in p)

program = st.selectbox(
    "Träningsprogram",
    p,
    label_visibility="collapsed",
    index=None,
    placeholder=prev_program,
    accept_new_options=True
)

disable_save = program is None and prevlog is None
program = program if program else prev_program
duration = st.slider("Träningstid, minuter", value=prev_duration, min_value=5, max_value=60)

# st.write("XXX Valt program:", program)
# st.write("XXX Prev log:", prevlog)
# st.write("XXX Disable:", disable_save)
# st.write("XXX Program:", program)

if st.button("Logga träning", disabled=disable_save):

    sql_delete_today = delete(training
    ).where(training.c.user == id
    ).where(func.date(training.c.ts) >= func.curdate()
    )

    sql_insert_today = insert(training).values(user=id, program=program, duration=duration)

    s.execute(sql_delete_today)
    s.execute(sql_insert_today)

    s.commit()
    st.balloons()
    st.rerun()

st.write("""
Obs. Vid flera loggningar på samma dag sparas bara den sista.
Träningsprogram finns [HÄR](https://drive.google.com/drive/folders/1WbRYW0EofaMUEiLtxZXHIXEjozyYuLDn)
""")


st.header("Mina senaste pass")

sql_mylatest = select(
    training
).where(
    training.c.user == id
).order_by(
    desc(training.c.ts)
).limit(10)

df = pd.DataFrame(s.execute(sql_mylatest).all())
if df:
    df['day'] = df.ts.dt.date
    df['min'] = df.duration
    # df = df.set_index('ts')
    st.dataframe(df[['day', 'min', 'program']], hide_index=True)


st.header("Andras senaste pass")

sql_otherslatest = select(
    training,
    user
).select_from(
    join(training, user, training.c.user == user.c.id)
).where(
    user.c.id != id
).order_by(
    desc(training.c.ts)
).limit(20)

otherlatest = s.execute(sql_otherslatest).all()
df = pd.DataFrame(otherlatest)
df['day'] = df.ts.dt.date
df['min'] = df.duration
st.dataframe(df[['day', 'name', 'min', 'program']], hide_index=True)
