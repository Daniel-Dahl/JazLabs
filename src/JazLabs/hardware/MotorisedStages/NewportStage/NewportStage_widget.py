from Lab_Equipment.Config import config 
import ipywidgets as widgets
from IPython.display import display, clear_output
import Lab_Equipment.MotorisedStage.NewportMounts as stageLib


def create_NewportStage_widget(stageObj: stageLib.NewportM100D_VISA):
    # --- Absolute position widgets (float, since step is 0.001) ---
    widget_PITCHaxis = widgets.FloatText(
        value=stageObj.get_position("U"),
        description='PITCH',
        step=0.001,
        layout=widgets.Layout(width='160px'),
        style={'description_width': '60px'}
    )
    widget_YAWaxis = widgets.FloatText(
        value=stageObj.get_position("V"),
        description='YAW',
        step=0.001,
        layout=widgets.Layout(width='160px'),
        style={'description_width': '60px'}
    )

    # --- Relative step widgets + +/- buttons ---
    step_PITCH = widgets.FloatText(
        value=0.001,
        description='step',
        step=0.001,
        layout=widgets.Layout(width='140px'),
        style={'description_width': '45px'}
    )
    step_YAW = widgets.FloatText(
        value=0.001,
        description='step',
        step=0.001,
        layout=widgets.Layout(width='140px'),
        style={'description_width': '45px'}
    )

    btn_PITCH_minus = widgets.Button(description='-')
    btn_PITCH_plus = widgets.Button(description='+')
    btn_YAW_minus = widgets.Button(description='-')
    btn_YAW_plus = widgets.Button(description='+')

    # --- Buttons for bulk actions ---
    SetToMiddlePoints_button = widgets.Button(
        description="Reset PITCH, YAW",
        layout=widgets.Layout(width='200px'),
        style={'description_width': 'initial'}
    )
    UpdateWidgetValues_button = widgets.Button(
        description="Update Widget Values",
        layout=widgets.Layout(width='200px'),
    )

    # --- Absolute move callbacks ---
    def on_PITCHaxis_change(change):
        # absolute move on U axis
        stageObj.move_abs(change['new'], "U")

    def on_YAWaxis_change(change):
        # absolute move on V axis
        stageObj.move_abs(change['new'], "V")

    # --- Relative move helpers: update the absolute widget -> triggers above ---
    def make_relative_handlers(pos_widget, step_widget):
        def on_plus(_):
            pos_widget.value = pos_widget.value + step_widget.value

        def on_minus(_):
            pos_widget.value = pos_widget.value - step_widget.value

        return on_minus, on_plus

    pitch_minus_handler, pitch_plus_handler = make_relative_handlers(
        widget_PITCHaxis, step_PITCH
    )
    yaw_minus_handler, yaw_plus_handler = make_relative_handlers(
        widget_YAWaxis, step_YAW
    )

    btn_PITCH_minus.on_click(pitch_minus_handler)
    btn_PITCH_plus.on_click(pitch_plus_handler)
    btn_YAW_minus.on_click(yaw_minus_handler)
    btn_YAW_plus.on_click(yaw_plus_handler)

    # --- Bulk actions ---
    def on_SetToMiddlePoints_click(_):
        # centre at 0 for both axes (this will trigger move_abs via observers)
        widget_PITCHaxis.value = 0.0
        widget_YAWaxis.value = 0.0

    def on_UpdateWidgetValues_click(_):
        widget_PITCHaxis.value = stageObj.get_position("U")
        widget_YAWaxis.value = stageObj.get_position("V")

    # --- Wire up observers for absolute moves ---
    widget_PITCHaxis.observe(on_PITCHaxis_change, names='value')
    widget_YAWaxis.observe(on_YAWaxis_change, names='value')

    SetToMiddlePoints_button.on_click(on_SetToMiddlePoints_click)
    UpdateWidgetValues_button.on_click(on_UpdateWidgetValues_click)

    # --- Layout: one row per axis: [abs, step, -, +] ---
    row_PITCH = widgets.HBox([widget_PITCHaxis, step_PITCH, btn_PITCH_minus, btn_PITCH_plus])
    row_YAW = widgets.HBox([widget_YAWaxis, step_YAW, btn_YAW_minus, btn_YAW_plus])

    grid = widgets.GridBox(
        children=[
            row_PITCH,
            row_YAW,
            SetToMiddlePoints_button,
            UpdateWidgetValues_button,
        ],
        layout=widgets.Layout(
            grid_template_columns="repeat(1, 1fr)",
            grid_template_rows="repeat(4, auto)",
            grid_gap="10px"
        )
    )

    return grid

def create_NewportAgilisStage_widget(stageObj: stageLib.NewportAgilisAxis):
    # --- Absolute position widgets (float, since step is 0.001) ---
    widget_POS = widgets.FloatText(
        value=stageObj.get_position(),
        description='Postion',
        step=0.001,
        layout=widgets.Layout(width='160px'),
        style={'description_width': '60px'}
    )
    # --- Relative step widgets + +/- buttons ---
    step_POS = widgets.FloatText(
        value=0.001,
        description='step',
        step=0.001,
        layout=widgets.Layout(width='140px'),
        style={'description_width': '45px'}
    )
    

    btn_POS_minus = widgets.Button(description='-')
    btn_POS_plus = widgets.Button(description='+')
    # --- Buttons for bulk actions ---
    SetToMiddlePoints_button = widgets.Button(
        description="Reset POS",
        layout=widgets.Layout(width='200px'),
        style={'description_width': 'initial'}
    )
    UpdateWidgetValues_button = widgets.Button(
        description="Update Widget Values",
        layout=widgets.Layout(width='200px'),
    )

    # --- Absolute move callbacks ---
    def on_POS_change(change):
        # absolute move on U axis
        stageObj.move_absolute(change['new'])


    # --- Relative move helpers: update the absolute widget -> triggers above ---
    def make_relative_handlers(pos_widget, step_widget):
        def on_plus(_):
            pos_widget.value = pos_widget.value + step_widget.value

        def on_minus(_):
            pos_widget.value = pos_widget.value - step_widget.value

        return on_minus, on_plus

    pitch_minus_handler, pitch_plus_handler = make_relative_handlers(
        widget_POS, step_POS
    )

    btn_POS_minus.on_click(pitch_minus_handler)
    btn_POS_plus.on_click(pitch_plus_handler)

    # --- Bulk actions ---
    def on_SetToMiddlePoints_click(_):
        # centre at 0 for both axes (this will trigger move_abs via observers)
        widget_POS.value = 0.0

    def on_UpdateWidgetValues_click(_):
        widget_POS.value = stageObj.get_position()

    # --- Wire up observers for absolute moves ---
    widget_POS.observe(on_POS_change, names='value')

    SetToMiddlePoints_button.on_click(on_SetToMiddlePoints_click)
    UpdateWidgetValues_button.on_click(on_UpdateWidgetValues_click)

    # --- Layout: one row per axis: [abs, step, -, +] ---
    row_PITCH = widgets.HBox([widget_POS, step_POS, btn_POS_minus, btn_POS_plus])

    grid = widgets.GridBox(
        children=[
            row_PITCH,
            SetToMiddlePoints_button,
            UpdateWidgetValues_button,
        ],
        layout=widgets.Layout(
            grid_template_columns="repeat(1, 1fr)",
            grid_template_rows="repeat(4, auto)",
            grid_gap="10px"
        )
    )

    return grid


# from Lab_Equipment.Config import config 
# import ipywidgets as widgets
# from IPython.display import display, clear_output
# import Lab_Equipment.MotorisedStage.NewportMounts as stageLib


# def create_NewportStage_widget(stageObj: stageLib.NewportM100D_VISA):
#     # Create widgets
#     widget_PITCHaxis = widgets.IntText(
#         value=stageObj.get_position("U"),
#         description='PITCH-axis', 
#         step=0.001,
#         layout=widgets.Layout(width='160px')
#     )
#     widget_YAWaxis = widgets.IntText(
#         value=stageObj.get_position("V"),
#         description='YAW-axis', 
#         step=0.001,
#         layout=widgets.Layout(width='160px')
#     )
#     SetToMiddlePoints_button = widgets.Button(description="Reset PITCH,YAW",
#         layout=widgets.Layout(width='200px'),
                                              
#                                               style={'description_width': 'initial'})
#     UpdateWidgetValues_button = widgets.Button(description="Update Widget Values",
#         layout=widgets.Layout(width='200px'),)
    
    
#     # Function to update exposure
#     def on_PITCHaxis_change(change):
#         stageObj.move_abs(change['new'],"U")
        
#     def on_YAWaxis_change(change):
#         stageObj.move_abs(change['new'],"V")
        
#     def on_SetToMiddlePoints_click(change):
#         widget_PITCHaxis.value=0
#         widget_YAWaxis.value=0
        
     
    
#     def on_UpdateWidgetValues_click(change):
#         widget_PITCHaxis.value=stageObj.get_position("U")
#         widget_YAWaxis.value=stageObj.get_position("V")
    
        
#     widget_PITCHaxis.observe(on_PITCHaxis_change, names='value')
#     widget_YAWaxis.observe(on_YAWaxis_change, names='value')
    
#     SetToMiddlePoints_button.on_click(on_SetToMiddlePoints_click)
#     UpdateWidgetValues_button.on_click(on_UpdateWidgetValues_click)
    
    
    
#     # Organize layout using a vertical box for controls
#     grid = widgets.GridBox(
#         children=[widget_YAWaxis,widget_PITCHaxis,
#         SetToMiddlePoints_button,
#         UpdateWidgetValues_button
#         ],
#          layout=widgets.Layout(
#         grid_template_columns="repeat(1, 1fr)",
#         grid_template_rows="repeat(8, auto)",
#         grid_gap="10px")
#     )

#     return grid
