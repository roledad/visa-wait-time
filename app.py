'''
This module runs the Plotly Dash to plot the visa wait time and send to server
'''

from datetime import datetime
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# pylint: disable=C0116
# pylint: disable=C0413
# pylint: disable=C0301
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, no_update
import dash_ag_grid as dag
import dash_bootstrap_components as dbc

from data import VisaWaitTimeData

asof_date = datetime.today().date()
df = pd.read_csv("data.csv") # read the saved data parsed from the website
countries = len(df["country"].unique())
cities = df["city_ascii"].nunique()
last_update = str(df["update_date"].unique()[0])

VISA_TYPES = [
        "Petition-Based Temporary Workers (H, L, O, P, Q)",
        "Student/Exchange Visitors (F, M, J)",
        "Crew and Transit\xa0(C, D, C1/D)",
        "Visitors (B1/B2)"]

app = Dash(__name__,  external_stylesheets=[dbc.themes.SPACELAB])
server = app.server

header = html.Div(
    children=[
        html.H1(children="Global Visa Wait Times",
                style={"font-family": "Courier", "font-size": "30px", "font-weight": "bold", 'color': 'darkblue'}),
        html.Div(children=f"As of: {asof_date}",
                style={"font-family": "Courier", "font-size": "15px"}),
        html.Div([
            html.A("Data Source: Travel.State.Gov",
                href=VisaWaitTimeData.VISA_WAIT_TIME_URL,
                style={"font-family": "Courier", "font-size": "15px"})]),
    ])

# helper function to create metric cards
def make_metric_card(name, value):
    if name == 'Last Update':
        child_p = value
        f_color = 'forestgreen'
    else:
        child_p = f'{value:,.0f}'
        f_color = 'rgb(53 86 120)'

    return dbc.Col(
        dbc.Card([
            dbc.CardBody([
                html.H4(name, className="card-title",
                        style={'margin': '0px', 'fontSize': '18px', 'fontWeight': 'bold'}),
                html.P(child_p, className="card-value",
                       style={'margin': '0px', 'fontWeight': 'bold', 'color': f_color}),
            ], style={'textAlign': 'center', "font-family": "Courier"}),
        ],
        style={
            'border-left': '7px solid #3E638D',
            'paddingBlock': '10px',
            'borderRadius': '10px',
            'box-shadow': '0 4px 8px 0 rgba(0, 0, 0, 0.1)'
        }),
        width=3  # This ensures 4 cards in one row
    )

metrics_value = [countries, cities, len(VISA_TYPES), last_update]
metrics_name = ['Countries', 'Cities', 'Visa Types', 'Last Update']
cards = [make_metric_card(name, value) for name, value in zip(metrics_name, metrics_value)]

# function to create visa wait time global map
def plot_global_map(visa_type: str="Petition-Based Temporary Workers (H, L, O, P, Q)"):
    "select the visa type to plot in map"
    assert visa_type in VISA_TYPES

    plot_df = df.rename(columns={visa_type: "Wait Days"}).sort_values("country")
    fig = px.scatter_map(
        plot_df, lat="lat", lon="lng", color="country",
        hover_name="city_ascii", hover_data=["Wait Days"],
        title = "Global Wait Time in Days: " + visa_type,
        width=1250, height=700
        )
    fig.update_layout(
        autosize=True,
        hovermode='closest',
        showlegend=True,
        title=dict(font={"color": "darkblue", "size": 20}, ),
        legend=dict(entrywidth=50),
        map=dict(
            bearing=0,
            center=dict(lat=25, lon=25),
            pitch=0,
            zoom=0.9,
            style='light'
        ),
    )
    fig.add_annotation(
        text="**double click legend to isolate one or more countries**",
        align="right", showarrow=False,
        xref="paper", yref="paper",
        x=0, y=1.05,
        )
    return fig

wait_time_map = plot_global_map()

# function to create the country data grid
def get_country_data():
    "get the country data for the grid"
    column_defs = [
        { 'field': 'City/Post' },
        { 'field': 'Petition-Based Temporary Workers (H, L, O, P, Q)' },
        { 'field': 'Student/Exchange Visitors (F, M, J)' },
        { 'field': 'Crew and Transit\xa0(C, D, C1/D)'},
        { 'field': 'Visitors (B1/B2)'},
        { 'field': 'country'}
    ]
    grid = dag.AgGrid(
        id="country-waiting-days",
        rowData=df[["City/Post"] + VISA_TYPES + ["country"]].to_dict("records"),
        columnDefs=column_defs,
        defaultColDef={"sortable": True, "filter": True, "resizable": True,
                       "wrapHeaderText": True, "autoHeaderHeight": True,},
        style={'height': '400px', 'width': '100%'}
    )
    return grid

country_wait_time = get_country_data()

# dropdown list for visa type
visa_dropdown = html.Div(
        children=[
                    html.A("Select Visa Type:", style={"font-weight": "bold", 'color': 'darkblue'}),
                    dcc.Dropdown(
                        id="visa-type-dropdown",
                        options=[{"label": visa_type, "value": visa_type} for visa_type in VISA_TYPES],
                        value="Petition-Based Temporary Workers (H, L, O, P, Q)"
                    ),
                    html.Div(id="output")
                ],
                style={"width": "50%", "font-family": "Courier", "font-size": "15px"},
    )

# dropdown list for countries
country_dropdown = html.Div(
        children=[
                    html.A("Select Country:", style={"font-weight": "bold", 'color': 'darkblue'}),
                    dcc.Dropdown(
                        id="country-dropdown",
                        options=[{"label": country, "value": country} for country in df["country"].sort_values().unique()],
                    ),
                    html.Div(id="country")
                ],
                style={"width": "20%", "font-family": "Courier", "font-size": "15px"},
    )

reset_button = html.Div(
    id="reset_btn", children=html.Button(id="reset-btn", children="Reset", n_clicks=0)
)

# Callback to manage selection changes for radio buttons
@app.callback( Output('wait-time-map', 'figure'),
               Input('visa-type-dropdown', 'value'),
               prevent_initial_call=True
               )

def update_map_plot(visa_type):
    "update the map plot based on the selected visa type"
    return plot_global_map(visa_type)

@app.callback( Output('country-waiting-days', 'rowData'),
               [Input('country-dropdown', 'value')],
               prevent_initial_call=True
               )

def update_country_data(country):
    "update the country data based on the selected country"
    filter_df = df[df["country"] == country][["City/Post"] + VISA_TYPES + ["country"]].to_dict("records")
    return filter_df if country is not None else df[["City/Post"] + VISA_TYPES + ["country"]].to_dict("records")

@app.callback( [Output('country-waiting-days', 'rowData', allow_duplicate=True),
                Output('country-waiting-days', 'filterModel', allow_duplicate=True),
                Output('country-waiting-days', 'columnState', allow_duplicate=True)
                ],
               Input('reset-btn', "n_clicks"),
               prevent_initial_call=True
               )

def reset_country_data(n_clicks):
    # If button is clicked, reset the grid to the original DataFrame
    if n_clicks > 0:
        return df[["City/Post"] + VISA_TYPES + ["country"]].sort_values("City/Post").to_dict("records"), {}, []
    return no_update, no_update, no_update


# Create app layout
app.layout = dbc.Container([
    dbc.Row(id='title', children=header, style={"padding": 0}),
    html.Br(),

    dbc.Row(cards, justify='center', style={'marginBlock': '10px'}),
    html.Br(),

    dbc.Row([
        dbc.Col([visa_dropdown,  html.Br(),
            dbc.Card(dcc.Graph(id='wait-time-map', figure=wait_time_map, config={'displayModeBar': False}), body=True),
            ])
    ]),
    html.Br(),
    dbc.Row([dbc.Col([country_dropdown, html.Br(), country_wait_time, html.Br(), reset_button])]),
    html.Br(),
    dbc.Row(
        html.Div([
            html.A("References: Deploying Dash Apps",
                href="https://dash.plotly.com/deployment",
                style={"font-family": "Courier", "font-size": "15px"})])
    ),
    html.Br(),
])

if __name__ == '__main__':
    app.run(debug=True)
