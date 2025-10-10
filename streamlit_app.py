import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, DateTime
from sqlalchemy import MetaData, cast, Date, func
from sqlalchemy import select, delete, insert, desc, join
from datetime import date, datetime, timedelta
import pandas as pd


def logtraining(dbsession, id, program, duration, day):
    sql_delete_today = delete(training
    ).where(training.c.user == id
    ).where(func.date(training.c.ts) == day
    )

    sql_insert_today = insert(training).values(user=id, program=program, duration=duration, ts=day)

    dbsession.execute(sql_delete_today)
    dbsession.execute(sql_insert_today)
    dbsession.commit()


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
    st.write("URL ska ha följande form, där XXXX är ditt personliga id:")
    st.write("https://fitbois.streamlit.app/?id=XXXX")
    st.stop()

# Id uppgivet, kolla mot databasen?

id = st.query_params.id
s = st.connection(
    'fitbois',
#   pool_recycle=3600,
    pool_pre_ping=True
    ).session

sql_finduser = select(user).where(user.c.id == id)

try:
    finduser = s.execute(sql_finduser).first()
except Exception as e:
    st.write("Skicka nedanstående felbeskrivning till Klabbe och försök igen, nu eller om ett tag.")
    st.write(e)

if not finduser:
    st.write("Fel id")
    st.stop()

# ID godkänt

dates = [datetime.now().date() - timedelta(days=i) for i in range(7)]
weekday = ['Måndag', 'Tisdag', 'Onsdag', 'Torsdag', 'Fredag', 'Lördag', 'Söndag']
alternativ = [weekday[date.weekday()] + " " + date.isoformat() for date in dates]
alternativ[0] = 'Idag'
alternativ[1] = 'Igår'

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

sql_earlierprograms = select(
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

### Formulär

with st.form("Loggformulär"):

    program = st.selectbox(
        "Träningsprogram",
        p,
        label_visibility="collapsed",
        index=None,
        placeholder=prev_program,
        accept_new_options=True
    )

    duration = st.slider(
        "Träningstid, minuter",
        value=prev_duration,
        min_value=5,
        max_value=120
    )

    disable_save = program is None and prevlog is None
    program = program if program else prev_program
        
    with st.container(horizontal=True):
        submitted = st.form_submit_button(
            "Logga träning",
            disabled=disable_save
        )

        trainingday = st.selectbox(
            "Träningsdag",
            alternativ,
            label_visibility="collapsed"
        )

        if submitted:
            logtraining(s, id, program, duration, dates[alternativ.index(trainingday)])
            st.session_state.saved = True
            st.rerun()

st.write("""
Obs. Vid flera loggningar på samma dag sparas bara den sista.
Träningsförslag finns [här](https://drive.google.com/drive/folders/1WbRYW0EofaMUEiLtxZXHIXEjozyYuLDn).
""")


st.header("Mina 5 senaste pass")

sql_mylatest = select(
    training
).where(
    training.c.user == id
).order_by(
    desc(training.c.ts)
).limit(5)

mylatest = s.execute(sql_mylatest).all()
if mylatest:
    df = pd.DataFrame(mylatest)
    df['day'] = df.ts.dt.date
    df['min'] = df.duration
    # df = df.set_index('ts')
    st.dataframe(df[['day', 'min', 'program']], hide_index=True)


st.header("Allas senaste 20")

sql_latestpass = select(
    training,
    user
).select_from(
    join(training, user, training.c.user == user.c.id)
).where(
    func.datediff(func.curdate(), training.c.ts) < 15
).order_by(
    desc(training.c.ts)
)

latestpass = s.execute(sql_latestpass).all()
df = pd.DataFrame(latestpass)
df['day'] = df.ts.dt.date
df['min'] = df.duration

st.dataframe(df[['day', 'name', 'min', 'program']].head(20), hide_index=True)



df = df[['day', 'name', 'min']].rename(columns={'day': 'Datum', 'name': 'Namn', 'min': 'Minuter'})

# Step 1: Convert Datum to datetime
df['Datum'] = pd.to_datetime(df['Datum'])

# Step 2: Calculate sum, mean, and count of Minuter for each Namn before padding
stats = df.groupby('Namn').agg({
    'Minuter': ['sum', 'mean'],
    'Datum': 'count'
}).reset_index()
stats.columns = ['Namn', 'Total_Minutes', 'Average_Minutes', 'Original_Count']
stats['Average_Minutes'] = stats['Average_Minutes'].round().astype(int)

# Step 3: Create all name-date combinations for padding
unique_names = df['Namn'].unique()
date_range = pd.date_range(end=df['Datum'].min(), start=df['Datum'].max(), freq='-1D')
all_combinations = pd.MultiIndex.from_product([date_range, unique_names], names=['Datum', 'Namn'])
complete_df = pd.DataFrame(index=all_combinations).reset_index()

# Step 4: Merge with original DataFrame and fill missing Minuter with 0
complete_df = complete_df.merge(df[['Datum', 'Namn', 'Minuter']], on=['Datum', 'Namn'], how='left')
complete_df['Minuter'] = complete_df['Minuter'].fillna(0).astype(int)

# Step 5: Group by Namn to get Minuter lists
grouped = complete_df.groupby('Namn')['Minuter'].agg(list).reset_index(name='Minuter_List')

# Step 6: Merge with stats (sum, mean, and count)
grouped = grouped.merge(stats, on='Namn', how='left')

# Step 7: Fill NaN in Total_Minutes, Average_Minutes, and Original_Count with 0 (for edge cases)
grouped['Total_Minutes'] = grouped['Total_Minutes'].fillna(0).astype(int)
grouped['Average_Minutes'] = grouped['Average_Minutes'].fillna(0)
grouped['Original_Count'] = grouped['Original_Count'].fillna(0).astype(int)
grouped = grouped.sort_values(by='Original_Count', ascending=False).reset_index(drop=True)

# Step 8: Convert to desired list format
output = grouped.apply(lambda x: [x['Namn'], x['Original_Count'], x['Total_Minutes'], x['Average_Minutes'], x['Minuter_List']], axis=1).tolist()

st.header("Senaste 14 dagarna")

st.dataframe(
    output,
    column_config={
        1: "Namn",
        2: "Pass",
        3: "∑ Min",
        4: "x̄ Min",
        5: st.column_config.BarChartColumn(
            label="Pass och längd, nyaste till vänster",
            y_min=0,
            y_max=int(df['Minuter'].max())
        ),
    }
)


if "saved" in st.session_state:
    del st.session_state.saved
    st.balloons()