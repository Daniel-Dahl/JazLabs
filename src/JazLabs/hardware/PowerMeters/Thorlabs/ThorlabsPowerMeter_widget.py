from Lab_Equipment.Config import config 
import ipywidgets as widgets
from IPython.display import display, clear_output
import Lab_Equipment.PowerMeter.PowerMeter_Thorlabs_lib as PMlib

def create_ThorlabsPowerMeter_widget(PwrMeterObj: PMlib.PowerMeterObj):
    # Create widgets
    widget_wavelength = widgets.FloatText(
        value=PwrMeterObj.wavelength,
        description='wavelength (nm)', 
        step=1,
        layout=widgets.Layout(width='200px'),
        style={'description_width': 'initial'}
    )
    widget_AverageCount = widgets.IntText(
        value=PwrMeterObj.AvgCount,
        description='Measure Count', 
        step=1,
        layout=widgets.Layout(width='200px'),
        style={'description_width': 'initial'}
    )
    SetZeroPoint_button = widgets.Button(description="Reset Zero Point")
    
    
    
    # Function to update exposure
    def on_Wavelength_change(change):
        PwrMeterObj.SetWaveLength(change['new'])
        
    def on_AverageCount_change(change):
        PwrMeterObj.SetAverageMeasure(change['new'])
    def on_SetZeroPoint_click(change):
        PwrMeterObj.StartDarkMeasurement()
        
    # Attach the observer to widget_Exposure and button
    widget_AverageCount.observe(on_AverageCount_change, names='value')
    widget_wavelength.observe(on_Wavelength_change, names='value')
    SetZeroPoint_button.on_click(on_SetZeroPoint_click)
    
    
    grid = widgets.GridBox(
        children=[
            widget_wavelength,widget_AverageCount,SetZeroPoint_button
        ],
         layout=widgets.Layout(
        grid_template_columns="repeat(1, 1fr)",
        grid_template_rows="repeat(3, auto)",
        grid_gap="10px")
    )

    return grid
