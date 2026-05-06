from Lab_Equipment.Config import config 
import ipywidgets as widgets
from IPython.display import display, clear_output
import Lab_Equipment.OpticalSwitch.JDSUniphaseOpticalSwitch as OpticalSwitchLib


def create_OpticalSwitch_widget(
    switchObj:OpticalSwitchLib.JDSSCSwitch,
    min_channel: int = 1,
    max_channel: int | None = None,
    title: str = "Optical Switch"
):
    """
    Widget to control an optical switch.

    Assumes:
        - switchObj.set_channel(ch: int)
        - switchObj.get_channel() -> int

    Parameters
    ----------
    switchObj : object
        Optical switch object with set_channel() and get_channel().
    min_channel : int
        Minimum allowed channel number (default: 1).
    max_channel : int | None
        Maximum allowed channel number. If None, no upper clamp is applied.
    title : str
        Title shown at the top of the widget.
    """

    # --- Helper to safely fetch current channel from hardware ---
    def _get_current_channel():
        try:
            return int(switchObj.get_channel())
        except AttributeError:
            # Fallback if get_channel() doesn't exist; assume channel 1
            return 1

    # Initial channel from device (or fallback)
    current_channel = _get_current_channel()

    # --- Main channel widget ---
    widget_channel = widgets.IntText(
        value=current_channel,
        description='Ch',
        step=1,
        layout=widgets.Layout(width='140px'),
        style={'description_width': '30px'}
    )

    # --- Step size widget ---
    step_channel = widgets.IntText(
        value=1,
        description='step',
        layout=widgets.Layout(width='120px'),
        style={'description_width': '40px'}
    )

    # --- Plus / minus buttons ---
    btn_minus = widgets.Button(description='-')
    btn_plus = widgets.Button(description='+')

    # --- Update-from-device button ---
    UpdateWidgetValues_button = widgets.Button(
        description="Update Channel",
        layout=widgets.Layout(width='160px'),
    )

    # --- Absolute move callback ---
    def on_channel_change(change):
        new_ch = int(change['new'])

        # Clamp to valid range if given
        if new_ch < min_channel:
            new_ch = min_channel
        if max_channel is not None and new_ch > max_channel:
            new_ch = max_channel

        # If clamped, push corrected value back to widget
        if new_ch != change['new']:
            widget_channel.value = new_ch
            return

        # Send to hardware
        switchObj.set_channel(new_ch)

    widget_channel.observe(on_channel_change, names='value')

    # --- Relative move callbacks (use step box) ---
    def on_plus(_):
        widget_channel.value = widget_channel.value + step_channel.value

    def on_minus(_):
        widget_channel.value = widget_channel.value - step_channel.value

    btn_plus.on_click(on_plus)
    btn_minus.on_click(on_minus)

    # --- Update-from-device callback ---
    def on_UpdateWidgetValues_click(_):
        ch = _get_current_channel()
        widget_channel.value = ch  # Triggers on_channel_change but with same value

    UpdateWidgetValues_button.on_click(on_UpdateWidgetValues_click)

    # --- Layout (similar style to your stage widget) ---
    row_channel = widgets.HBox([widget_channel, step_channel, btn_minus, btn_plus])

    title_widget = widgets.HTML(f"<b>{title}</b>")

    grid = widgets.GridBox(
        children=[
            title_widget,
            row_channel,
            UpdateWidgetValues_button,
        ],
        layout=widgets.Layout(
            grid_template_columns="repeat(1, 1fr)",
            grid_template_rows="repeat(3, auto)",
            grid_gap="8px"
        )
    )

    return grid