from functools import lru_cache
from operator import itemgetter
import pandas as pd
import numpy as np

import bokeh
from bokeh.palettes import viridis, inferno, Set3
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import (
    ColumnDataSource,
    PreText,
    Select,
    ColorBar,
    RangeSlider,
    Div,
    RadioButtonGroup,
    TextInput,
    Button,
    Panel,
)
from bokeh.plotting import figure
from bokeh.transform import linear_cmap, factor_cmap

CELL_IMAGE_METRICS = (["mean", "sd", "min", "max"], [np.mean, np.std, np.min, np.max])


def prepare_server(doc, input_data, cell_stack, cell_markers=None):
    @lru_cache()
    def get_data(m=None):
        d = input_data.copy()
        if m is not None:
            m_v = d[m]
            if np.issubdtype(m_v.dtype, np.number):
                d["marker_val_num"] = m_v
            else:
                d["marker_val_cat"] = m_v
        if "marker_val_num" not in d:
            d["marker_val_num"] = np.arange(d.shape[0])
        if "marker_val_cat" not in d:
            d["marker_val_cat"] = np.full(d.shape[0], "a")
        return d

    @lru_cache()
    def get_cat_colors(n):
        return Set3[max(3, n)][:n]

    # @lru_cache()
    # def make_colormapper(levels):
    #     mapper = factor_cmap("", Set3[max(3, len(levels))][:len(levels)], levels)
    #     # colorbar = ColorBar(color_mapper=mapper["transform"], width=12, location=(0, 0))
    #     return mapper["transform"]

    def get_markers():
        return tuple(sorted(input_data.columns))

    cell_markers = (
        cell_markers
        if cell_markers is not None
        else [f"Marker {i + 1}" for i in range(cell_stack.shape[1])]
    )
    cell_markers = list(
        (str(j), y)
        for j, y in sorted(
            ((i, x) for i, x in enumerate(cell_markers)), key=itemgetter(1)
        )
    )

    # set up widgets

    marker_cols = get_markers()

    stats = PreText(text="", width=100)
    marker_select = Select(
        value=marker_cols[0], options=list(marker_cols), title="Color UMAP by"
    )

    cell_markers_select = Select(
        value=cell_markers[0][0], options=cell_markers, title="Marker cell image"
    )
    marker_slider = RangeSlider(start=0, end=1, value=(0, 1), step=0.1)
    cell_slider = RangeSlider(start=0, end=1, value=(0, 1))
    metric_select = RadioButtonGroup(active=0, labels=CELL_IMAGE_METRICS[0])

    # set up plots

    source = ColumnDataSource(data=get_data(None))
    image_source = ColumnDataSource(data=dict(image=[], dw=[], dh=[]))

    marker_mapper = linear_cmap(
        field_name="marker_val_num",
        palette=inferno(10)[:-1],
        low=0,
        high=500,
        high_color=None,
    )

    umap_figure = figure(
        plot_width=800,
        plot_height=500,
        tools="pan,wheel_zoom,lasso_select,box_select,tap,reset",
        active_scroll="wheel_zoom",
        active_drag="box_select",
        active_tap="tap",
    )
    umap_figure.circle(
        "d1",
        "d2",
        size=5,
        source=source,
        line_color=marker_mapper,
        color=marker_mapper,
        selection_color="orange",
        alpha=0.6,
        nonselection_alpha=0.4,
        selection_alpha=0.8,
    )
    umap_color_bar = ColorBar(
        color_mapper=marker_mapper["transform"], width=12, location=(0, 0)
    )
    umap_figure.add_layout(umap_color_bar, "right")

    umap_figure_cat = figure(
        plot_width=800,
        plot_height=500,
        tools="pan,wheel_zoom,lasso_select,box_select,tap,reset",
        active_scroll="wheel_zoom",
        active_drag="box_select",
        active_tap="tap",
        # x_range=umap_figure.x_range,
        # y_range=umap_figure.y_range,
    )
    marker_mapper_cat = factor_cmap(
        field_name="marker_val_cat", palette=["#000000"], factors=["a"]
    )
    umap_figure_cat.circle(
        "d1",
        "d2",
        size=5,
        source=source,
        line_color=marker_mapper_cat,
        color=marker_mapper_cat,
        legend_field="marker_val_cat",
        selection_color="orange",
        alpha=0.6,
        nonselection_alpha=0.4,
        selection_alpha=0.8,
    )
    umap_figure_cat.legend.location = "center_right"
    umap_figure_cat.legend.orientation = "vertical"

    cell_mapper = bokeh.models.mappers.LinearColorMapper(
        viridis(20), low=0, high=1000, high_color=None
    )
    cell_color_bar = ColorBar(color_mapper=cell_mapper, width=12, location=(0, 0))
    cell_figure = figure(plot_width=450, plot_height=350, tools="pan,wheel_zoom,reset")
    cell_image = cell_figure.image(
        image="image",
        color_mapper=cell_mapper,
        x=0,
        y=0,
        dw="dw",
        dh="dh",
        source=image_source,
    )
    cell_figure.add_layout(cell_color_bar, "right")

    edit_selection_col = TextInput(title="Column")
    edit_selection_val = TextInput(title="Value")
    edit_selection_submit = Button(label="Submit", button_type="primary")

    # set up callbacks

    def marker_change(attrname, old, new):
        # marker_select.options = nix(new, marker_cols)
        update()

    def cell_slider_change(attrname, old, new):
        cell_mapper.low = new[0]
        cell_mapper.high = new[1]

    def marker_slider_change(attrname, old, new):
        marker_mapper["transform"].low = new[0]
        marker_mapper["transform"].high = new[1]

    def update(update_range=True):
        m = marker_select.value
        d = get_data(m)
        source.data = d
        numeric_marker = np.issubdtype(d[m].dtype, np.number)
        if not numeric_marker:
            levels = list(sorted(set(d["marker_val_cat"])))
            # Remove old colorbar
            # if len(umap_figure_cat.right) > 0:
            # umap_figure_cat.right.pop()
            # mapper = make_colormapper(levels)
            # umap_figure_cat.add_layout(colorbar, "right")
            marker_mapper_cat["transform"].palette = get_cat_colors(len(levels))
            marker_mapper_cat["transform"].factors = levels
        umap_figure.visible = numeric_marker
        umap_figure_cat.visible = not numeric_marker
        if update_range and numeric_marker:
            marker_max = d["marker_val_num"].max()
            marker_min = d["marker_val_num"].min()
            marker_slider.start = marker_min
            marker_slider.end = marker_max
            marker_slider.value = tuple(np.percentile(d["marker_val_num"], [5, 95]))

    def selection_change(attrname, old, new):
        m = marker_select.value
        data = get_data(m)
        selected = source.selected.indices
        if not selected:
            return
        data = data.iloc[selected, :]
        mean_image = CELL_IMAGE_METRICS[1][metric_select.active](
            cell_stack[selected, int(cell_markers_select.value), :, :], axis=0
        )
        image_source.data = {
            "image": [mean_image],
            "dw": [cell_stack.shape[1]],
            "dh": [cell_stack.shape[2]],
        }
        image_extr = mean_image.min(), mean_image.max()
        cell_slider.start = image_extr[0]
        cell_slider.end = image_extr[1]
        cell_slider.value = image_extr
        stats.text = "n cells: " + str(len(selected))

    def mark_selection():
        get_data.cache_clear()
        col = edit_selection_col.value
        if col not in input_data:
            input_data[col] = np.full(input_data.shape[0], "")
        input_data.loc[
            input_data.index[source.selected.indices], col
        ] = edit_selection_val.value
        update(update_range=False)
        new_marker_cols = tuple(sorted(input_data.columns))
        nonlocal marker_cols
        if new_marker_cols != marker_cols:
            marker_cols = new_marker_cols
            marker_select.options = list(marker_cols)

    source.selected.on_change("indices", selection_change)
    marker_select.on_change("value", marker_change)
    marker_slider.on_change("value", marker_slider_change)
    cell_slider.on_change("value", cell_slider_change)
    metric_select.on_change("active", selection_change)
    cell_markers_select.on_change("value", selection_change)
    edit_selection_submit.on_click(mark_selection)

    # set up layout
    layout = row(
        column(
            marker_select,
            # row(umap_figure, umap_figure_cat),
            umap_figure,
            umap_figure_cat,
            marker_slider,
            row(edit_selection_col, edit_selection_val),
            edit_selection_submit,
        ),
        column(cell_markers_select, metric_select, cell_figure, stats, cell_slider),
    )

    # initialize
    update()

    doc.add_root(layout)
    doc.title = "UMAP projection"
