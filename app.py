"""
Shiny dashboard application for analytics data.
Migrated from R Shiny to Python Shiny.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from shiny import App, ui, reactive, render, module
from shiny.types import FileInfo
from htmltools import HTML as HTMLToolsHTML

# ---------------------------------------------------------------------------
# UI definition
# ---------------------------------------------------------------------------

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.style(
            """
            .value-box-purple {
                background: linear-gradient(135deg, #9b59b6, #8e44ad);
                color: white;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
                margin: 10px 0;
            }
            .value-box-purple .value {
                font-size: 2em;
                font-weight: bold;
            }
            .value-box-purple .label {
                font-size: 1em;
                opacity: 0.9;
            }
        """
        )
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_file(
                "file1",
                "Выберите Excel",
                accept=[".xlsx", ".xls"],
            ),
            ui.input_selectize(
                "selPatgroup",
                "Группа пациентов",
                choices=["."],
                selected=".",
                multiple=False,
            ),
            ui.input_selectize(
                "selCity",
                "Город",
                choices=["."],
                selected=["."],
                multiple=True,
            ),
            ui.input_action_button(
                "selAllCities",
                "Выбрать все города",
                icon=ui.tags.span("☑"),
            ),
            ui.input_date_range(
                "selDateRange",
                "Дата взятия образца",
                start=None,
                end=None,
            ),
            ui.input_slider(
                "selAge",
                "Возраст",
                min=0,
                max=100,
                value=[0, 100],
                step=1,
            ),
            ui.output_ui("data_count"),
            title="Мой первый дашборд",
            width=350,
        ),
        ui.navset_tab(
            ui.nav_panel(
                "Дашборд",
                ui.layout_column_wrap(
                    ui.card(
                        ui.card_header("Распределение по городам"),
                        ui.navset_tab(
                            ui.nav_panel("Карта", ui.output_ui("map")),
                            ui.nav_panel("Города", ui.output_ui("table_cities")),
                            ui.nav_panel("Диагнозы", ui.output_ui("table_diags")),
                            ui.nav_panel("Организмы", ui.output_ui("table_orgs")),
                        ),
                        full_screen=True,
                    ),
                    ui.layout_column_wrap(
                        ui.card(
                            ui.card_header("Структура диагнозов"),
                            ui.output_ui("diag"),
                            full_screen=True,
                        ),
                        ui.card(
                            ui.card_header("Структура организмов"),
                            ui.output_ui("org"),
                            full_screen=True,
                        ),
                        width=1 / 2,
                    ),
                    width=1,
                ),
            ),
            ui.nav_panel(
                "Набор данных",
                ui.output_data_frame("table_data"),
            ),
            id="main_tabset",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Server logic
# ---------------------------------------------------------------------------


def server(input, output, session):
    # ---- reactive data holder ----
    dataset = reactive.Value(None)

    # ---- file loading ----
    @reactive.effect
    @reactive.event(input.file1)
    def load_file():
        file: list[FileInfo] | None = input.file1()
        if file is None:
            return
        filepath = file[0]["datapath"]
        df = pd.read_excel(filepath, sheet_name="Пациенты")
        for col in ["DATESTRAIN", "DATEBIRTH", "DATEFILL"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        dataset.set(df)

    # ---- select all cities button ----
    @reactive.effect
    @reactive.event(input.selAllCities)
    def select_all_cities():
        df = dataset.get()
        if df is None:
            return
        all_cities = sorted(df["CITYNAME"].dropna().unique().tolist())
        ui.update_selectize(
            "selCity",
            selected=all_cities,
        )

    # ---- update controls ----
    @reactive.effect
    @reactive.event(dataset)
    def update_controls():
        df = dataset.get()
        if df is None:
            return

        ui.update_selectize(
            "selPatgroup",
            choices=["."] + sorted(df["PAT_GROUP"].dropna().unique().tolist()),
            selected=".",
        )
        ui.update_selectize(
            "selCity",
            choices=["."] + sorted(df["CITYNAME"].dropna().unique().tolist()),
            selected=["."],
        )

        if "DATESTRAIN" in df.columns:
            min_date = df["DATESTRAIN"].min()
            max_date = df["DATESTRAIN"].max()
            if pd.notna(min_date) and pd.notna(max_date):
                ui.update_date_range(
                    "selDateRange",
                    start=min_date.date(),
                    end=max_date.date(),
                    min=min_date.date(),
                    max=max_date.date(),
                )

        if "AGE" in df.columns:
            min_age = int(df["AGE"].min())
            max_age = int(df["AGE"].max())
            ui.update_slider(
                "selAge",
                min=min_age,
                max=max_age,
                value=[min_age, max_age],
            )

    # ---- filtered data ----
    @reactive.calc
    def filtered_data():
        df = dataset.get()
        if df is None:
            return pd.DataFrame()

        d = df.copy()

        # filter by PAT_GROUP
        if input.selPatgroup() != ".":
            d = d[d["PAT_GROUP"] == input.selPatgroup()]

        # filter by CITY
        cities = input.selCity()
        if cities is not None and "." not in cities:
            # если выбраны все города, фильтр не применяется
            all_cities = sorted(df["CITYNAME"].dropna().unique().tolist())
            if set(cities) != set(all_cities):
                d = d[d["CITYNAME"].isin(cities)]

        # filter by date range
        date_range = input.selDateRange()
        if date_range is not None and len(date_range) == 2:
            if date_range[0] is not None and date_range[1] is not None:
                d = d[
                    (d["DATESTRAIN"] >= pd.Timestamp(date_range[0]))
                    & (d["DATESTRAIN"] <= pd.Timestamp(date_range[1]))
                ]

        # filter by age
        age_range = input.selAge()
        if age_range is not None and len(age_range) == 2:
            d = d[(d["AGE"] >= age_range[0]) & (d["AGE"] <= age_range[1])]

        return d

    # ---- value box ----
    @render.ui
    def data_count():
        df = filtered_data()
        value = len(df) if df is not None and not df.empty else 0
        return HTMLToolsHTML(
            f"""
            <div class="value-box-purple">
                <div class="value">{value}</div>
                <div class="label">Образцов</div>
            </div>
        """
        )

    # ---- map ----
    @render.ui
    def map():
        import folium

        df = filtered_data()
        if df is None or df.empty or "LATITUDE" not in df.columns:
            return HTMLToolsHTML("<p>Нет данных для отображения карты</p>")

        # aggregate by city
        map_data = (
            df.groupby(["CITYNAME", "LATITUDE", "LONGITUDE"])
            .size()
            .reset_index(name="Count")
        )

        # center of map
        center_lat = map_data["LATITUDE"].mean()
        center_lon = map_data["LONGITUDE"].mean()

        m = folium.Map(location=[center_lat, center_lon], zoom_start=4, tiles=None)
        folium.TileLayer(
            "http://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Light Gray Base",
        ).add_to(m)

        for _, row in map_data.iterrows():
            radius = max(3, min(int(np.sqrt(row["Count"]) * 3), 30))
            folium.CircleMarker(
                location=[row["LATITUDE"], row["LONGITUDE"]],
                radius=radius,
                popup=f"<strong>{row['CITYNAME']}: {row['Count']}</strong>",
                fill=True,
                fill_opacity=0.5,
                color="blue",
            ).add_to(m)

        return HTMLToolsHTML(m._repr_html_())

    # ---- cities table ----
    @render.ui
    def table_cities():
        from great_tables import GT

        df = filtered_data()
        if df is None or df.empty:
            return HTMLToolsHTML("<p>Нет данных</p>")

        cities_df = (
            df.groupby("CITYNAME")
            .size()
            .reset_index(name="Образцов")
            .rename(columns={"CITYNAME": "Город"})
        )

        gt_table = (
            GT(cities_df, rowname_col="Город")
            .tab_header(
                title="Распределение пациентов",
                subtitle=f"Среди {len(cities_df)} городов",
            )
            .grand_summary_rows(
                fns={"Всего": lambda x: x.sum()},
            )
            .opt_row_striping()
        )
        return HTMLToolsHTML(gt_table.as_raw_html())

    # ---- diagnoses table ----
    @render.ui
    def table_diags():
        from great_tables import GT

        df = filtered_data()
        if df is None or df.empty:
            return HTMLToolsHTML("<p>Нет данных</p>")

        diags_df = (
            df.groupby(["CITYNAME", "mkb_name"])
            .size()
            .reset_index(name="Count")
            .pivot(index="mkb_name", columns="CITYNAME", values="Count")
            .fillna(0)
            .reset_index()
        )
        diags_df.columns.name = None
        # reorder columns: first mkb_name, then sorted city names
        city_cols = sorted([c for c in diags_df.columns if c != "mkb_name"])
        diags_df = diags_df[["mkb_name"] + city_cols]
        diags_df["Всего"] = diags_df[city_cols].sum(axis=1)

        gt_table = (
            GT(diags_df, rowname_col="mkb_name")
            .tab_header(
                title="Распределение диагнозов",
                subtitle=f"Среди {len(city_cols)} городов",
            )
            .grand_summary_rows(
                fns={"Всего": lambda x: x.sum()},
            )
            .opt_row_striping()
        )
        return HTMLToolsHTML(gt_table.as_raw_html())

    # ---- organisms table ----
    @render.ui
    def table_orgs():
        from great_tables import GT

        df = filtered_data()
        if df is None or df.empty:
            return HTMLToolsHTML("<p>Нет данных</p>")

        orgs_df = (
            df.groupby(["CITYNAME", "STRAIN"])
            .size()
            .reset_index(name="Count")
            .pivot(index="STRAIN", columns="CITYNAME", values="Count")
            .fillna(0)
            .reset_index()
        )
        orgs_df.columns.name = None
        city_cols = sorted([c for c in orgs_df.columns if c != "STRAIN"])
        orgs_df = orgs_df[["STRAIN"] + city_cols]
        orgs_df["Всего"] = orgs_df[city_cols].sum(axis=1)

        gt_table = (
            GT(orgs_df, rowname_col="STRAIN")
            .tab_header(
                title="Распределение организмов",
                subtitle=f"Среди {len(city_cols)} городов",
            )
            .grand_summary_rows(
                fns={"Всего": lambda x: x.sum()},
            )
            .opt_row_striping()
        )
        return HTMLToolsHTML(gt_table.as_raw_html())

    # ---- diagnoses pie chart ----
    @render.ui
    def diag():
        import plotly.express as px
        import plotly.io as pio

        df = filtered_data()
        if df is None or df.empty:
            return HTMLToolsHTML("<p>Нет данных</p>")

        diag_data = df.groupby("mkb_name").size().reset_index(name="count")
        fig = px.pie(
            diag_data,
            names="mkb_name",
            values="count",
            title="Структура диагнозов",
            hole=0.6,
        )
        fig.update_layout(
            legend=dict(orientation="h", xanchor="center", x=0.5),
            xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            margin=dict(l=20, r=20, t=40, b=20),
            height=400,
        )
        return HTMLToolsHTML(pio.to_html(fig, full_html=False))

    # ---- organisms pie chart ----
    @render.ui
    def org():
        import plotly.express as px
        import plotly.io as pio

        df = filtered_data()
        if df is None or df.empty:
            return HTMLToolsHTML("<p>Нет данных</p>")

        org_data = df.groupby("STRAIN").size().reset_index(name="Count")
        org_data["Percent"] = (100 * org_data["Count"] / org_data["Count"].sum()).round(
            1
        )
        org_data = org_data.sort_values("Percent", ascending=False)

        fig = px.pie(
            org_data,
            names="STRAIN",
            values="Count",
            title="Структура организмов",
            hole=0,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(
            legend=dict(title="Организм", orientation="h", xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=40, b=20),
            height=400,
        )
        return HTMLToolsHTML(pio.to_html(fig, full_html=False))

    # ---- data table ----
    @render.data_frame
    def table_data():
        df = filtered_data()
        if df is None or df.empty:
            return pd.DataFrame()

        display_cols = [
            "study_subject_id",
            "PAT_GROUP",
            "SEX",
            "AGE",
            "DATEBIRTH",
            "STRAIN",
            "DATESTRAIN",
            "CENTER",
            "CITYNAME",
            "COUNTRY",
            "DATEFILL",
            "DIAG_ICD",
            "mkb_name",
            "COMPL",
        ]
        available_cols = [c for c in display_cols if c in df.columns]
        display_df = df[available_cols].copy()

        # rename columns to Russian
        rename_map = {
            "study_subject_id": "Id",
            "PAT_GROUP": "Группа",
            "SEX": "Пол",
            "AGE": "Возраст",
            "DATEBIRTH": "Дата рождения",
            "STRAIN": "Образец",
            "DATESTRAIN": "Дата выделения",
            "CENTER": "№ центра",
            "CITYNAME": "Город",
            "COUNTRY": "Страна",
            "DATEFILL": "Дата заполнения",
            "DIAG_ICD": "Диагноз МКБ",
            "mkb_name": "Диагноз",
            "COMPL": "Осложнения",
        }
        display_df = display_df.rename(
            columns={k: v for k, v in rename_map.items() if k in display_df.columns}
        )

        # convert dates to string for display
        for col in [
            "Дата рождения",
            "Дата выделения",
            "Дата заполнения",
            "Диагноз МКБ",
        ]:
            if col in display_df.columns:
                if pd.api.types.is_datetime64_any_dtype(display_df[col]):
                    display_df[col] = display_df[col].dt.strftime("%Y-%m-%d")

        return display_df


# ---------------------------------------------------------------------------
# Create app
# ---------------------------------------------------------------------------

app = App(app_ui, server)
