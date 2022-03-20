import geopandas as gpd
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output
import dash_bootstrap_components as dbc
import os

dash_app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app = dash_app.server

cwd = os.getcwd()

def find(name, path):
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)

tabeller = 'Tabeller.csv'

data = pd.read_csv(find(tabeller, cwd), sep=";")

data = data[['Område', 'Startdato', 'Slutdato']]
data['Område'] = data['Område'].astype('str')

data['Startdato'] = pd.to_datetime(data['Startdato'], format='%d-%m-%Y', errors='coerce')
data['Slutdato'] = pd.to_datetime(data['Slutdato'], format='%d-%m-%Y', errors='coerce')

områder = 'Egedal-områder.gpkg'

omr_gdf = gpd.read_file(find(områder, cwd))
omr_gdf = omr_gdf[["Distriktets navn", "geometry"]]
omr_gdf["Distriktets navn"] = omr_gdf["Distriktets navn"].astype('str')

#join the tables
gdf_mrgd = omr_gdf.merge(data, how='left', left_on='Distriktets navn', right_on='Område')

gdf_mrgd = gpd.GeoDataFrame.to_crs(gdf_mrgd, epsg=4326)
gdf_mrgd = gdf_mrgd.drop(columns=['Distriktets navn'])

map_json = gdf_mrgd.__geo_interface__

# calculate years in working
earliestStart = gdf_mrgd['Startdato'].min()
latestEnd = gdf_mrgd['Slutdato'].max()

earliestYear = earliestStart.year - 1
latestYear = latestEnd.year + 2

sliderRange = list(range(earliestYear, latestYear))

# function to calculate the color for a specific year
def getStatus(startYear, endYear, currentYear):
    if currentYear < startYear:
        return "Eksisterende" #'#ff0000'
    elif currentYear >= startYear and currentYear <= endYear:
        return "Igangværende" #'#ffff00'
    else: return "Afsluttet" #'#008000'

color_map = {"Eksisterende": "Red", "Igangværende": "Yellow", "Afsluttet": "Green"}

# function that applies getColor to create extra columns
def f(row, year):
    return getStatus(row['Startdato'].year, row['Slutdato'].year, year)
# drop geometry to make reading easier (can be omitted)
gdf_mrgd = gdf_mrgd.drop(columns=['geometry'])

# create the extra columns for each year
for year in sliderRange:
    colName = str(year)
    gdf_mrgd[colName] = gdf_mrgd.apply(lambda row: f(row, year), axis=1)

#create custom marks
markers = {}
for i in sliderRange:
    markers[i] = str(i)

controls = dbc.Card(
    [
        html.Div(
            [
                dcc.Slider(
                    min=earliestYear,
                    max=latestYear-1,
                    step = 1,
                    value=earliestYear,
                    marks=markers,
                    id='yearslider'
                    ),
            ]),
        html.Div
        (
            id='table-container',
        )
    ],
    body=True,
)

graph = dbc.Card([dcc.Graph(id='choropleth')])

dash_app.layout = dbc.Container(
    [
        html.H1('Status for Egedal fjernvarmeområder'),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(controls, width=4),
                dbc.Col(graph, width=8),
            ]
        )
    ], fluid=True
)

@dash_app.callback(
    Output('choropleth', 'figure'),
    Input('yearslider', 'value'))
def display_choropleth(year):
    fig = px.choropleth(
        gdf_mrgd, geojson=map_json, color=str(year),
        locations="Område", featureidkey="properties.Område",
        projection="mercator", color_discrete_map=color_map
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(legend_orientation="h", margin={"r":0,"t":0,"l":0,"b":0}, height=750)
    return fig

@dash_app.callback(
    Output('table-container', 'children'),
    Input('yearslider', 'value'))
def populate_table(year):
    header = html.H4(['Status for ' + str(year)])

    listEks = []
    for i in range(len(gdf_mrgd[str(year)])):
        if gdf_mrgd[str(year)][i] == "Eksisterende":
            listEks.append(gdf_mrgd['Område'][i])

    listIgang = []
    for i in range(len(gdf_mrgd[str(year)])):
        if gdf_mrgd[str(year)][i] == "Igangværende":
            listIgang.append(gdf_mrgd['Område'][i])

    listAfsluttet = []
    for i in range(len(gdf_mrgd[str(year)])):
        if gdf_mrgd[str(year)][i] == "Afsluttet":
            listAfsluttet.append(gdf_mrgd['Område'][i])

    # Pad the lists with empty strings if they are too short
    maxCount = max(len(listEks), len(listIgang), len(listAfsluttet))
    listEks.extend([""] * (maxCount - len(listEks)))
    listIgang.extend([""] * (maxCount - len(listIgang)))
    listAfsluttet.extend([""] * (maxCount - len(listAfsluttet)))

    data = {'Eksisterende': listEks, 'Igangværende': listIgang, 'Afsluttet': listAfsluttet}
    df = pd.DataFrame(data, columns=['Eksisterende', 'Igangværende', 'Afsluttet'])
    return [header, generate_dbc_table(df)]

# generate a HTML table from a pandas dataframe
# not used
def generate_table(dataframe, max_rows=30):
    return html.Table(
        # Header
        [html.Tr([html.Th(col) for col in dataframe.columns], style={'border': '1px solid black', 'border-collapse': 'collapse'}) ] +
        # Body
        [html.Tr([
            html.Td(dataframe.iloc[i][col]) for col in dataframe.columns
        ], style={'border': '1px solid black', 'border-collapse': 'collapse'}) for i in range(min(len(dataframe), max_rows))], style={'width': '100%'}
    )

# alternative table from dbc
def generate_dbc_table(dataframe):
    return dbc.Table.from_dataframe(dataframe, striped=True, bordered=True, hover=True, responsive=True)

if __name__ == '__main__':
    dash_app.run_server(debug=True)