from Lab_Equipment.Config import config 
import ipywidgets as widgets
from IPython.display import display, clear_output
import Lab_Equipment.MotorisedStage.LuminosStage as stageLib


def create_LuminosStage_widget(stageObj: stageLib.LuminosStage):
    # --- Absolute position widgets ---
    widget_Xaxis = widgets.IntText(
        value=stageObj.Get_all_stage_Positions()[stageLib.Axes.X],
        description='X',
        step=1,
        layout=widgets.Layout(width='140px'),
        style={'description_width': '30px'}
    )
    widget_Yaxis = widgets.IntText(
        value=stageObj.Get_all_stage_Positions()[stageLib.Axes.Y],
        description='Y',
        step=1,
        layout=widgets.Layout(width='140px'),
        style={'description_width': '30px'}
    )
    widget_Zaxis = widgets.IntText(
        value=stageObj.Get_all_stage_Positions()[stageLib.Axes.Z],
        description='Z',
        step=1,
        layout=widgets.Layout(width='140px'),
        style={'description_width': '30px'}
    )
    widget_ROLLaxis = widgets.IntText(
        value=stageObj.Get_all_stage_Positions()[stageLib.Axes.ROLL],
        description='ROLL',
        step=1,
        layout=widgets.Layout(width='160px'),
        style={'description_width': '50px'}
    )
    widget_PITCHaxis = widgets.IntText(
        value=stageObj.Get_all_stage_Positions()[stageLib.Axes.PITCH],
        description='PITCH',
        step=1,
        layout=widgets.Layout(width='160px'),
        style={'description_width': '50px'}
    )
    widget_YAWaxis = widgets.IntText(
        value=stageObj.Get_all_stage_Positions()[stageLib.Axes.YAW],
        description='YAW',
        step=1,
        layout=widgets.Layout(width='160px'),
        style={'description_width': '50px'}
    )

    # --- Relative step widgets + +/- buttons ---
    step_X = widgets.IntText(value=1, description='step', layout=widgets.Layout(width='120px'),
                             style={'description_width': '40px'})
    step_Y = widgets.IntText(value=1, description='step', layout=widgets.Layout(width='120px'),
                             style={'description_width': '40px'})
    step_Z = widgets.IntText(value=1, description='step', layout=widgets.Layout(width='120px'),
                             style={'description_width': '40px'})
    step_ROLL = widgets.IntText(value=1, description='step', layout=widgets.Layout(width='120px'),
                                style={'description_width': '40px'})
    step_PITCH = widgets.IntText(value=1, description='step', layout=widgets.Layout(width='120px'),
                                 style={'description_width': '40px'})
    step_YAW = widgets.IntText(value=1, description='step', layout=widgets.Layout(width='120px'),
                               style={'description_width': '40px'})

    btn_X_minus = widgets.Button(description='-')
    btn_X_plus = widgets.Button(description='+')
    btn_Y_minus = widgets.Button(description='-')
    btn_Y_plus = widgets.Button(description='+')
    btn_Z_minus = widgets.Button(description='-')
    btn_Z_plus = widgets.Button(description='+')
    btn_ROLL_minus = widgets.Button(description='-')
    btn_ROLL_plus = widgets.Button(description='+')
    btn_PITCH_minus = widgets.Button(description='-')
    btn_PITCH_plus = widgets.Button(description='+')
    btn_YAW_minus = widgets.Button(description='-')
    btn_YAW_plus = widgets.Button(description='+')

    # --- Buttons for bulk actions ---
    SetToMiddlePoints_button = widgets.Button(
        description="Reset X,Y,PITCH,YAW,ROLL",
        layout=widgets.Layout(width='220px'),
        style={'description_width': 'initial'}
    )
    UpdateWidgetValues_button = widgets.Button(
        description="Update Widget Values",
        layout=widgets.Layout(width='220px'),
    )

    # --- Absolute move callbacks (already what you had) ---
    def on_Xaxis_change(change):
        stageObj.Set_Single_Stage_State_abs(stageLib.Axes.X, change['new'])

    def on_Yaxis_change(change):
        stageObj.Set_Single_Stage_State_abs(stageLib.Axes.Y, change['new'])

    def on_Zaxis_change(change):
        stageObj.Set_Single_Stage_State_abs(stageLib.Axes.Z, change['new'])

    def on_PITCHaxis_change(change):
        stageObj.Set_Single_Stage_State_abs(stageLib.Axes.PITCH, change['new'])

    def on_ROLLaxis_change(change):
        stageObj.Set_Single_Stage_State_abs(stageLib.Axes.ROLL, change['new'])

    def on_YAWaxis_change(change):
        stageObj.Set_Single_Stage_State_abs(stageLib.Axes.YAW, change['new'])

    # --- Relative move helpers: update the absolute widget -> triggers above ---
    def make_relative_handlers(pos_widget, step_widget):
        def on_plus(_):
            pos_widget.value = pos_widget.value + step_widget.value

        def on_minus(_):
            pos_widget.value = pos_widget.value - step_widget.value

        return on_minus, on_plus

    x_minus_handler, x_plus_handler = make_relative_handlers(widget_Xaxis, step_X)
    y_minus_handler, y_plus_handler = make_relative_handlers(widget_Yaxis, step_Y)
    z_minus_handler, z_plus_handler = make_relative_handlers(widget_Zaxis, step_Z)
    roll_minus_handler, roll_plus_handler = make_relative_handlers(widget_ROLLaxis, step_ROLL)
    pitch_minus_handler, pitch_plus_handler = make_relative_handlers(widget_PITCHaxis, step_PITCH)
    yaw_minus_handler, yaw_plus_handler = make_relative_handlers(widget_YAWaxis, step_YAW)

    btn_X_minus.on_click(x_minus_handler)
    btn_X_plus.on_click(x_plus_handler)
    btn_Y_minus.on_click(y_minus_handler)
    btn_Y_plus.on_click(y_plus_handler)
    btn_Z_minus.on_click(z_minus_handler)
    btn_Z_plus.on_click(z_plus_handler)
    btn_ROLL_minus.on_click(roll_minus_handler)
    btn_ROLL_plus.on_click(roll_plus_handler)
    btn_PITCH_minus.on_click(pitch_minus_handler)
    btn_PITCH_plus.on_click(pitch_plus_handler)
    btn_YAW_minus.on_click(yaw_minus_handler)
    btn_YAW_plus.on_click(yaw_plus_handler)

    # --- Bulk actions ---
    def on_SetToMiddlePoints_click(_):
        widget_Xaxis.value = stageObj.deviceMaxLimits[stageLib.Axes.X] // 2
        widget_Yaxis.value = stageObj.deviceMaxLimits[stageLib.Axes.Y] // 2
        widget_PITCHaxis.value = stageObj.deviceMaxLimits[stageLib.Axes.PITCH] // 2
        widget_YAWaxis.value = stageObj.deviceMaxLimits[stageLib.Axes.YAW] // 2
        widget_ROLLaxis.value = stageObj.deviceMaxLimits[stageLib.Axes.ROLL] // 2

    def on_UpdateWidgetValues_click(_):
        currentValues = stageObj.Get_all_stage_Positions()
        widget_Xaxis.value = currentValues[stageLib.Axes.X]
        widget_Yaxis.value = currentValues[stageLib.Axes.Y]
        widget_Zaxis.value = currentValues[stageLib.Axes.Z]
        widget_PITCHaxis.value = currentValues[stageLib.Axes.PITCH]
        widget_YAWaxis.value = currentValues[stageLib.Axes.YAW]
        widget_ROLLaxis.value = currentValues[stageLib.Axes.ROLL]

    # --- Wire up observers for absolute moves ---
    widget_Xaxis.observe(on_Xaxis_change, names='value')
    widget_Yaxis.observe(on_Yaxis_change, names='value')
    widget_Zaxis.observe(on_Zaxis_change, names='value')
    widget_PITCHaxis.observe(on_PITCHaxis_change, names='value')
    widget_ROLLaxis.observe(on_ROLLaxis_change, names='value')
    widget_YAWaxis.observe(on_YAWaxis_change, names='value')

    SetToMiddlePoints_button.on_click(on_SetToMiddlePoints_click)
    UpdateWidgetValues_button.on_click(on_UpdateWidgetValues_click)

    # --- Layout: one row per axis: [abs, step, -, +] ---
    row_X = widgets.HBox([widget_Xaxis, step_X, btn_X_minus, btn_X_plus])
    row_Y = widgets.HBox([widget_Yaxis, step_Y, btn_Y_minus, btn_Y_plus])
    row_Z = widgets.HBox([widget_Zaxis, step_Z, btn_Z_minus, btn_Z_plus])
    row_ROLL = widgets.HBox([widget_ROLLaxis, step_ROLL, btn_ROLL_minus, btn_ROLL_plus])
    row_PITCH = widgets.HBox([widget_PITCHaxis, step_PITCH, btn_PITCH_minus, btn_PITCH_plus])
    row_YAW = widgets.HBox([widget_YAWaxis, step_YAW, btn_YAW_minus, btn_YAW_plus])

    grid = widgets.GridBox(
        children=[
            row_X,
            row_Y,
            row_Z,
            row_ROLL,
            row_PITCH,
            row_YAW,
            SetToMiddlePoints_button,
            UpdateWidgetValues_button,
        ],
        layout=widgets.Layout(
            grid_template_columns="repeat(1, 1fr)",
            grid_template_rows="repeat(8, auto)",
            grid_gap="8px"
        )
    )

    return grid

