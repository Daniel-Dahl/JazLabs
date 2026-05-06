# SLM_PhaseMask_Window.py

import numpy as np
from PySide6.QtWidgets import (
    QApplication, QWidget, QGridLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QLineEdit
)
from PySide6.QtCore import Qt
import sys


class SLMPhaseMaskWindow(QWidget):
    def __init__(self, slm, pol="V", imask=0, channel="Red"):
        super().__init__()

        self.slm = slm
        self.channel = channel
        self.pol = pol
        self.imask = int(imask)

        self.setWindowTitle("SLM Phase Mask Control")

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.channelBox = QComboBox()
        self.channelBox.addItems(["Red", "Green", "Blue"])
        self.channelBox.setCurrentText(channel)

        self.polBox = QComboBox()
        self.polBox.addItems(["H", "V"])
        self.polBox.setCurrentText(pol)

        self.polEnabledBox = QCheckBox("Enable Pol")
        self.maskEnabledBox = QCheckBox("Enable Mask")

        self.planeBox = QSpinBox()
        self.planeBox.setMinimum(0)
        self.planeBox.setMaximum(9999)
        self.planeBox.setValue(imask)

        self.modeHBox = QSpinBox()
        self.modeHBox.setMinimum(0)
        self.modeHBox.setMaximum(9999)

        self.modeVBox = QSpinBox()
        self.modeVBox.setMinimum(0)
        self.modeVBox.setMaximum(9999)

        self.xCenterBox = QSpinBox()
        self.xCenterBox.setRange(-100000, 100000)

        self.yCenterBox = QSpinBox()
        self.yCenterBox.setRange(-100000, 100000)

        self.xTiltBox = QDoubleSpinBox()
        self.xTiltBox.setRange(-1e6, 1e6)
        self.xTiltBox.setDecimals(6)
        self.xTiltBox.setSingleStep(0.001)

        self.yTiltBox = QDoubleSpinBox()
        self.yTiltBox.setRange(-1e6, 1e6)
        self.yTiltBox.setDecimals(6)
        self.yTiltBox.setSingleStep(0.001)

        self.pistonBox = QDoubleSpinBox()
        self.pistonBox.setRange(-1e6, 1e6)
        self.pistonBox.setDecimals(6)
        self.pistonBox.setSingleStep(2 * np.pi / 256)

        self.defocusBox = QDoubleSpinBox()
        self.defocusBox.setRange(-1e6, 1e6)
        self.defocusBox.setDecimals(6)
        self.defocusBox.setSingleStep(1.0)

        self.refreshBox = QDoubleSpinBox()
        self.refreshBox.setRange(0, 1e6)
        self.refreshBox.setDecimals(3)
        self.refreshBox.setSuffix(" ms")

        self.sweepStepBox = QSpinBox()
        self.sweepStepBox.setRange(1, 100000)
        self.sweepStepBox.setValue(30)

        self.maskFileBox = QLineEdit()
        self.maskFileBox.setText(getattr(self.slm, "MasksFilename", ""))

        self.updateCurrentButton = QPushButton("Update Current SLM")
        self.updateAllButton = QPushButton("Update All SLM")
        self.clearButton = QPushButton("Clear SLM")
        self.zeroZernikeButton = QPushButton("Set All Zernike To Zero")
        self.equalSpacingButton = QPushButton("Set Plane To Equal Spacing")
        self.reverseOrderButton = QPushButton("Reverse Plane Order")
        self.sweepButton = QPushButton("Start Sweep")
        self.saveButton = QPushButton("Save Mask Props")
        self.loadPiButton = QPushButton("Load PI Flip Masks")
        self.loadMaskButton = QPushButton("Load Mask Files")

        row = 0
        self.layout.addWidget(QLabel("Channel"), row, 0)
        self.layout.addWidget(self.channelBox, row, 1)
        self.layout.addWidget(QLabel("Pol"), row, 2)
        self.layout.addWidget(self.polBox, row, 3)
        self.layout.addWidget(self.polEnabledBox, row, 4)

        row += 1
        self.layout.addWidget(QLabel("Plane"), row, 0)
        self.layout.addWidget(self.planeBox, row, 1)
        self.layout.addWidget(self.maskEnabledBox, row, 2)

        row += 1
        self.layout.addWidget(QLabel("Mode H"), row, 0)
        self.layout.addWidget(self.modeHBox, row, 1)
        self.layout.addWidget(QLabel("Mode V"), row, 2)
        self.layout.addWidget(self.modeVBox, row, 3)

        row += 1
        self.layout.addWidget(QLabel("X Center"), row, 0)
        self.layout.addWidget(self.xCenterBox, row, 1)
        self.layout.addWidget(QLabel("Y Center"), row, 2)
        self.layout.addWidget(self.yCenterBox, row, 3)

        row += 1
        self.layout.addWidget(QLabel("X Tilt"), row, 0)
        self.layout.addWidget(self.xTiltBox, row, 1)
        self.layout.addWidget(QLabel("Y Tilt"), row, 2)
        self.layout.addWidget(self.yTiltBox, row, 3)

        row += 1
        self.layout.addWidget(QLabel("Piston"), row, 0)
        self.layout.addWidget(self.pistonBox, row, 1)
        self.layout.addWidget(QLabel("Defocus"), row, 2)
        self.layout.addWidget(self.defocusBox, row, 3)

        row += 1
        self.layout.addWidget(QLabel("Refresh"), row, 0)
        self.layout.addWidget(self.refreshBox, row, 1)

        row += 1
        self.layout.addWidget(self.updateCurrentButton, row, 0)
        self.layout.addWidget(self.updateAllButton, row, 1)
        self.layout.addWidget(self.clearButton, row, 2)

        row += 1
        self.layout.addWidget(self.zeroZernikeButton, row, 0)
        self.layout.addWidget(self.equalSpacingButton, row, 1)
        self.layout.addWidget(self.reverseOrderButton, row, 2)

        row += 1
        self.layout.addWidget(QLabel("Sweep Step"), row, 0)
        self.layout.addWidget(self.sweepStepBox, row, 1)
        self.layout.addWidget(self.sweepButton, row, 2)

        row += 1
        self.layout.addWidget(QLabel("Mask File"), row, 0)
        self.layout.addWidget(self.maskFileBox, row, 1, 1, 2)
        self.layout.addWidget(self.loadMaskButton, row, 3)

        row += 1
        self.layout.addWidget(self.saveButton, row, 0)
        self.layout.addWidget(self.loadPiButton, row, 1)

        self.channelBox.currentTextChanged.connect(self.on_channel_or_pol_change)
        self.polBox.currentTextChanged.connect(self.on_channel_or_pol_change)
        self.planeBox.valueChanged.connect(self.on_plane_change)

        self.polEnabledBox.stateChanged.connect(self.on_pol_enable_change)
        self.maskEnabledBox.stateChanged.connect(self.on_mask_enable_change)

        self.modeHBox.valueChanged.connect(self.update_mask)
        self.modeVBox.valueChanged.connect(self.update_mask)

        self.xCenterBox.valueChanged.connect(self.on_value_change)
        self.yCenterBox.valueChanged.connect(self.on_value_change)
        self.xTiltBox.valueChanged.connect(self.on_value_change)
        self.yTiltBox.valueChanged.connect(self.on_value_change)
        self.pistonBox.valueChanged.connect(self.on_value_change)
        self.defocusBox.valueChanged.connect(self.on_value_change)
        self.refreshBox.valueChanged.connect(self.on_value_change)

        self.updateCurrentButton.clicked.connect(self.update_current_slm)
        self.updateAllButton.clicked.connect(self.update_all_slm)
        self.clearButton.clicked.connect(self.clear_slm)
        self.zeroZernikeButton.clicked.connect(self.zero_zernikes)
        self.equalSpacingButton.clicked.connect(self.equal_spacing)
        self.reverseOrderButton.clicked.connect(self.reverse_order)
        self.sweepButton.clicked.connect(self.start_sweep)
        self.saveButton.clicked.connect(self.save_mask_props)
        self.loadPiButton.clicked.connect(self.load_pi_flip_masks)
        self.loadMaskButton.clicked.connect(self.load_mask_files)

        self.refresh_from_slm()

    def current_channel(self):
        return self.channelBox.currentText()

    def current_pol(self):
        return self.polBox.currentText()

    def current_plane(self):
        return int(self.planeBox.value())

    def refresh_from_slm(self):
        ch = self.current_channel()
        pol = self.current_pol()
        imask = self.current_plane()

        max_plane = self.slm.polProps[ch][pol].MaskCount - 1
        if imask > max_plane:
            self.planeBox.setValue(0)
            imask = 0

        props = self.slm.AllMaskProperties[ch][pol][imask]

        self.xCenterBox.blockSignals(True)
        self.yCenterBox.blockSignals(True)
        self.xTiltBox.blockSignals(True)
        self.yTiltBox.blockSignals(True)
        self.pistonBox.blockSignals(True)
        self.defocusBox.blockSignals(True)
        self.polEnabledBox.blockSignals(True)
        self.maskEnabledBox.blockSignals(True)
        self.refreshBox.blockSignals(True)

        self.xCenterBox.setValue(int(props.center[1]))
        self.yCenterBox.setValue(int(props.center[0]))
        self.pistonBox.setValue(float(props.zernike.zern_coefs[0]))
        self.xTiltBox.setValue(float(props.zernike.zern_coefs[1]))
        self.yTiltBox.setValue(float(props.zernike.zern_coefs[2]))
        self.defocusBox.setValue(float(props.zernike.zern_coefs[4]))

        self.polEnabledBox.setChecked(bool(self.slm.polProps[ch][pol].polEnabled))
        self.maskEnabledBox.setChecked(bool(props.maskEnabled))
        self.refreshBox.setValue(float(self.slm.GLobProps[ch].RefreshTime * 1e3))

        self.xCenterBox.blockSignals(False)
        self.yCenterBox.blockSignals(False)
        self.xTiltBox.blockSignals(False)
        self.yTiltBox.blockSignals(False)
        self.pistonBox.blockSignals(False)
        self.defocusBox.blockSignals(False)
        self.polEnabledBox.blockSignals(False)
        self.maskEnabledBox.blockSignals(False)
        self.refreshBox.blockSignals(False)

        self.update_mask()

    def on_channel_or_pol_change(self):
        self.refresh_from_slm()

    def on_plane_change(self):
        ch = self.current_channel()
        pol = self.current_pol()

        if self.planeBox.value() > self.slm.polProps[ch][pol].MaskCount - 1:
            self.planeBox.setValue(0)
            return

        self.refresh_from_slm()

    def on_value_change(self):
        ch = self.current_channel()
        pol = self.current_pol()
        imask = self.current_plane()

        props = self.slm.AllMaskProperties[ch][pol][imask]

        props.center[1] = self.xCenterBox.value()
        props.center[0] = self.yCenterBox.value()
        props.zernike.zern_coefs[1] = self.xTiltBox.value()
        props.zernike.zern_coefs[2] = self.yTiltBox.value()
        props.zernike.zern_coefs[0] = self.pistonBox.value()
        props.zernike.zern_coefs[4] = self.defocusBox.value()

        self.slm.GLobProps[ch].RefreshTime = self.refreshBox.value() * 1e-3

        self.update_mask()

    def on_pol_enable_change(self):
        ch = self.current_channel()
        pol = self.current_pol()
        self.slm.polProps[ch][pol].polEnabled = self.polEnabledBox.isChecked()
        self.update_mask()

    def on_mask_enable_change(self):
        ch = self.current_channel()
        pol = self.current_pol()
        imask = self.current_plane()
        self.slm.AllMaskProperties[ch][pol][imask].maskEnabled = self.maskEnabledBox.isChecked()
        self.update_mask()

    def update_mask(self):
        ch = self.current_channel()

        max_h = self.slm.polProps[ch]["H"].modeCount - 1
        max_v = self.slm.polProps[ch]["V"].modeCount - 1

        if self.modeHBox.value() > max_h:
            self.modeHBox.setValue(0)
            return

        if self.modeVBox.value() > max_v:
            self.modeVBox.setValue(0)
            return

        self.slm.setmask(
            ch,
            imode_H=self.modeHBox.value(),
            imode_V=self.modeVBox.value(),
        )

    def update_current_slm(self):
        ch = self.current_channel()
        pol = self.current_pol()
        imask = self.current_plane()
        self.update_slm_properties(ch, pol, imask)

    def update_all_slm(self):
        for ch in self.slm.ActiveRGBChannels:
            for pol in ["H", "V"]:
                self.update_slm_properties(ch, pol, self.current_plane())

    def update_slm_properties(self, ch, pol, imask):
        self.refresh_from_slm()
        self.slm.setmask(
            ch,
            imode_H=self.modeHBox.value(),
            imode_V=self.modeVBox.value(),
        )

    def clear_slm(self):
        for ch in self.slm.ActiveRGBChannels:
            self.slm.LCOS_Clean(ch)

    def zero_zernikes(self):
        self.slm.ResetAllZernikesToZero(self.current_channel())
        self.refresh_from_slm()

    def equal_spacing(self):
        self.slm.setCentersToEqualSpacing(self.current_channel())
        self.refresh_from_slm()

    def reverse_order(self):
        self.slm.mplc_reverse_order_mask_x_centers(
            channel=self.current_channel(),
            pol=self.current_pol(),
        )
        self.refresh_from_slm()

    def start_sweep(self):
        self.slm.CourseSweepAcrossSLM(
            self.current_channel(),
            self.sweepStepBox.value(),
        )

    def save_mask_props(self):
        self.slm.saveMaskProperties(channel=self.current_channel())

    def load_pi_flip_masks(self):
        self.slm.LoadPiFlipMasks(channel=self.current_channel())

    def load_mask_files(self):
        self.slm.LoadMasksFromFile(
            Filename=self.maskFileBox.text(),
            channel=self.current_channel(),
        )
        self.refresh_from_slm()


def show_slm_phase_mask_window(slm, pol="V", imask=0, channel="Red"):
    app = QApplication.instance()

    if app is None:
        app = QApplication(sys.argv)

    win = SLMPhaseMaskWindow(
        slm=slm,
        pol=pol,
        imask=imask,
        channel=channel,
    )

    win.show()
    return win


# import matplotlib.pyplot as plt
# import ipywidgets as widgets
# from IPython.display import display
# import cv2
# import numpy as np
# import pwi_inst.hardware.SLM.PhaseMaskClass as PhaseMaskClass


# def create_slm_widget(slm:PhaseMaskClass.PhaseMaskObject, pol="V", imask=0, channel="Red"):
#     # Create widgets
#     #####################################
#     # Drop down  boxes
#     ####################################
#     widget_channel = widgets.Dropdown(
#         options=[('Red SLM', "Red"), ('Green SLM', "Green"),('Blue SLM', "Blue")],
#         value=channel, description='Channel',
#         layout=widgets.Layout(width='200px')
#     )
#     widget_pol = widgets.Dropdown(
#         options=[('H', "H"), ('V', "V")],
#         value=pol, description='pol',
#         layout=widgets.Layout(width='140px')
#     )
#     #####################################
#     # Check boxes
#     ####################################
#     widget_PolEnableChecBox = widgets.Checkbox(
#     value=True,
#     description='Enable Pol',
#     disabled=False,indent=False,
#     layout=widgets.Layout(width='150px')
    
    
# )
#     widget_MaskEnableChecBox = widgets.Checkbox(
#     value=True,
#     description='Enable Mask',
#     disabled=False,indent=False,
#     layout=widgets.Layout(width='150px'))

#     #####################################
#     # Value boxes
#     ####################################
#     widget_Plane = widgets.IntText(value=0, 
#         description='Plane', 
#         layout=widgets.Layout(width='140px'))
#     widget_Mode_H = widgets.IntText(value=0, 
#         description='Mode_H', 
#         layout=widgets.Layout(width='140px'))
#     widget_Mode_V = widgets.IntText(value=0, 
#         description='Mode_V', 
#         layout=widgets.Layout(width='140px'))
    
#     widget_XCenter = widgets.IntText(
#         value=slm.AllMaskProperties[channel][pol][imask].center[1],
#         description='X Center', layout=widgets.Layout(width='160px')
#     )
#     widget_YCenter = widgets.IntText(
#         value=slm.AllMaskProperties[channel][pol][imask].center[0],
#         description='Y Center', layout=widgets.Layout(width='160px')
#     )
#     widget_XTilt = widgets.FloatText(
#         value=slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[1],
#         step=0.001,
#         description='X Tilt', layout=widgets.Layout(width='160px')
#     )
#     widget_YTilt = widgets.FloatText(
#         value=slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[2],
#         step=0.001,
#         description='Y Tilt', layout=widgets.Layout(width='160px')
#     )
#     widget_Piston = widgets.FloatText(
#         value=slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[0],
#         step=2*np.pi/256,
#         description='Piston', layout=widgets.Layout(width='160px')
#     )
#     widget_Defocus = widgets.FloatText(
#         value=slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[4],
#         step=1,
#         description='Defocus', layout=widgets.Layout(width='160px')
#     )
#     widget_RefreshTime = widgets.FloatText(
#         value=slm.GLobProps[channel].RefreshTime*1e3,
#         description='Refresh Rate (ms)', layout=widgets.Layout(width='180px')
#     )
    
#     widget_SweepStep = widgets.IntText(
#         value=30,
#         description='Sweep Step', layout=widgets.Layout(width='160px')
#     )
#     #######################################
#     # text box
#     ####################################
#     widget_MaskFilename = widgets.Text(
#         value=slm.MasksFilename,
#         description="Mask File Name",
#         layout=widgets.Layout(width='250px')
#     )


#     #####################################
#     # Buttons
#     ####################################
#     update_button_currentSLM = widgets.Button(description='Update Current SLM', layout=widgets.Layout(width='150px'))
#     update_button_AllSLM = widgets.Button(description='Update All SLM', layout=widgets.Layout(width='150px'))
#     update_button_ClearSLM = widgets.Button(description='Clear SLM', layout=widgets.Layout(width='150px'))
#     update_button_SetZernikeToZero = widgets.Button(description='Set All Zernike To Zero', layout=widgets.Layout(width='170px'))
#     update_button_SetPlanesToEqualSpacing = widgets.Button(description='Set PlaneTo Equal Spacing', layout=widgets.Layout(width='170px'))
#     update_button_ReversePlaneOrder = widgets.Button(description='Reverse Plane Order', layout=widgets.Layout(width='170px'))
#     update_button_ViewDisplay = widgets.Button(description='View SLM Image', layout=widgets.Layout(width='170px'))
#     Init_button_PiSweep = widgets.Button(description='Start Sweep', layout=widgets.Layout(width='170px'))
    
#     Save_MaskProp_button = widgets.Button(description='Save Mask Props', layout=widgets.Layout(width='170px'))
#     LoadPiFlipMasks_button =  widgets.Button(description='Load PI flip masks', layout=widgets.Layout(width='170px'))
#     LoadMaskFile_button =  widgets.Button(description='Load mask files', layout=widgets.Layout(width='170px'))
   

#     # Define event handlers (using closures to capture widget variables)
#     def on_value_change(change):
#         # Determine which widget changed and update accordingly.
        
#         desc = change['owner'].description
#         if desc == 'Mode_H':
#             if widget_Mode_H.value > slm.polProps[widget_channel.value]['H'].modeCount - 1:
#                 widget_Mode_H.value = 0
#             if widget_Mode_H.value < 0:
#                 widget_Mode_H.value = slm.polProps[widget_channel.value]['H'].modeCount - 1
#         elif desc == 'Mode_V':
#             if widget_Mode_V.value > slm.polProps[widget_channel.value]['V'].modeCount - 1:
#                 widget_Mode_V.value = 0
#             if widget_Mode_V.value < 0:
#                 widget_Mode_V.value = slm.polProps[widget_channel.value]['V'].modeCount - 1
#             # slm.setmask(widget_channel.value, widget_Mode.value)
#         elif desc == 'X Center':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].center[1] = change['new']
#         elif desc == 'Y Center':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].center[0] = change['new']
#         elif desc == 'X Tilt':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].zernike.zern_coefs[1] = change['new']
#         elif desc == 'Y Tilt':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].zernike.zern_coefs[2] = change['new']
#         elif desc == 'Piston':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].zernike.zern_coefs[0] = change['new']
#         elif desc == 'Defocus':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].zernike.zern_coefs[4] = change['new']
#         elif desc == 'Refresh Rate (ms)':
#            slm.GLobProps[widget_channel.value].RefreshTime = change['new']*1e-3
        
#         slm.setmask(widget_channel.value,imode_H=widget_Mode_H.value,imode_V=widget_Mode_V.value)

#     def on_button_click(event, update_all=False):
#         if update_all:
#             for ch in slm.ActiveRGBChannels:
#                 for ipol in ["H","V"]:

#                     update_slm_properties(ch, ipol, widget_Plane.value)
#         else:
#             update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)

#     def on_button_click_clearSLM(event):
#         for ch in slm.ActiveRGBChannels:
#             slm.LCOS_Clean(ch)

#     def on_button_click_SetAllZernikeToZero(event):
#         slm.ResetAllZernikesToZero(widget_channel.value)
#         update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)
    
#     def on_button_click_SetPlanesToEqualSpacing(event):
#         slm.setCentersToEqualSpacing(widget_channel.value)
#         update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)

#     def on_button_click_ReversePlaneOrder(event):
#         # slm.setCentersToEqualSpacing(widget_channel.value)
#         slm.mplc_reverse_order_mask_x_centers(channel=widget_channel.value,pol=widget_pol.value)
#         update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)
        
#     fig, ax = plt.subplots()
#     fig.canvas.header_visible = False
#     rgbimage=np.zeros((slm.slmHeigth, slm.slmWidth, 3), dtype=np.uint8)
#     channelIdx=slm.GLobProps[widget_channel.value].rgbChannelIdx
#     np.copyto(rgbimage[:,:,channelIdx],slm.FullScreenBuffer_int)
#     rgb_image = cv2.cvtColor(rgbimage, cv2.COLOR_BGR2RGB)
#     image_display = ax.imshow(rgb_image,aspect='auto')
#     plt.axis("off")  # Hide axes
#     fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
#     # Function to update the plot when button is clicked
#     def update_displayWidget(_):
#         # rgb_image = cv2.cvtColor(slm.FullScreenBuffer_int, cv2.COLOR_BGR2RGB)
#         channelIdx=slm.GLobProps[widget_channel.value].rgbChannelIdx
#         np.copyto(rgbimage[:,:,channelIdx],slm.FullScreenBuffer_int)
#         rgb_image = cv2.cvtColor(rgbimage, cv2.COLOR_BGR2RGB)
#         image_display.set_data(rgb_image)
#         fig.canvas.draw_idle()  # Redraw figure without clearing widgets

#     # Observer callback for widget_Plane changes.
#     def on_plane_change(change):
#         # change['new'] is the new value of widget_Plane
#         new_plane = change['new']
#         # Sanity check for plane value
        
#         if new_plane > slm.polProps[widget_channel.value][widget_pol.value].MaskCount - 1:
#             widget_Plane.value = 0
#         elif new_plane < 0:
#             widget_Plane.value =  slm.polProps[widget_channel.value][widget_pol.value].MaskCount - 1
#         # Now update the center widgets based on the new plane value.
#         update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)

#     def on_channel_change(change):  
#          Channel = change['new']
#          update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)
    
#     def on_pol_change(change):
#         pol = change['new']
#         update_slm_properties( widget_channel.value, widget_pol.value, widget_Plane.value)

#     def on_pol_Enable_change(change):
#         if change['new']:
#             if(widget_pol.value=="H"):# Turn the Vertical pol side of SLM off
#                 slm.polProps[widget_channel.value]['H'].polEnabled=True
#             else:# Turn the Horizontial pol side of SLM off
#                 slm.polProps[widget_channel.value]['V'].polEnabled=True
#         else:
#             if(widget_pol.value=="H"):# Turn the Vertical pol side of SLM off
#                 slm.polProps[widget_channel.value]['H'].polEnabled=False
#             else:# Turn the Horizontial pol side of SLM off
#                 slm.polProps[widget_channel.value]['V'].polEnabled=False

#         update_slm_properties( widget_channel.value, widget_pol.value, widget_Plane.value)
    
#     def on_Mask_Enable_change(change):
#         slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].maskEnabled=widget_MaskEnableChecBox.value
#         slm.setmask(widget_channel.value, imode_H=widget_Mode_H.value,imode_V=widget_Mode_V.value)


#     def update_slm_properties(Channel, pol="V", imask=0):
#         widget_XCenter.value = slm.AllMaskProperties[Channel][pol][imask].center[1]
#         widget_YCenter.value = slm.AllMaskProperties[Channel][pol][imask].center[0]
#         widget_Piston.value = slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[0]
#         widget_XTilt.value = slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[1]
#         widget_YTilt.value = slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[2]
#         widget_Defocus.value = slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[4]
#         if(pol=="H"):# Turn the Vertical pol side of SLM off
#                 widget_PolEnableChecBox.value=slm.polProps[Channel]['H'].polEnabled
#         else:# Turn the Horizontial pol side of SLM off
#                 widget_PolEnableChecBox.value=slm.polProps[Channel]['V'].polEnabled
#         widget_MaskEnableChecBox.value= slm.AllMaskProperties[Channel][pol][imask].maskEnabled
#         slm.setmask(widget_channel.value, imode_H=widget_Mode_H.value,imode_V=widget_Mode_V.value)
    
#     def InitialPiSweep(_):
#         slm.CourseSweepAcrossSLM(widget_channel.value,widget_SweepStep.value)

#     def SaveMaskProps(_):
#         slm.saveMaskProperties(channel=widget_channel.value)

#     def LoadPiFlipAlignmentMasks(_):
#         slm.LoadPiFlipMasks(channel=widget_channel.value) 
#     def LoadMaskFiles(_):
#         slm.LoadMasksFromFile(Filename=widget_MaskFilename.value,channel=widget_channel.value,)


        
#     # Attach the observer to widget_Plane.
#     widget_Plane.observe(on_plane_change, names='value')
#     widget_channel.observe(on_channel_change, names='value')
#     widget_pol.observe(on_pol_change, names='value')
#     widget_PolEnableChecBox.observe(on_pol_Enable_change, names='value')
#     widget_MaskEnableChecBox.observe(on_Mask_Enable_change, names='value')
    
    
    

#     # Register observers for the widgets
#     for w in [widget_Mode_H,widget_Mode_V, widget_XCenter, widget_YCenter, widget_XTilt,
#               widget_YTilt, widget_Piston, widget_Defocus,widget_RefreshTime]:
#         w.observe(on_value_change, names='value')

#     update_button_currentSLM.on_click(lambda event: on_button_click(event, update_all=False))
#     update_button_AllSLM.on_click(lambda event: on_button_click(event, update_all=True))
#     update_button_ClearSLM.on_click(on_button_click_clearSLM)
#     update_button_SetZernikeToZero.on_click(on_button_click_SetAllZernikeToZero)
#     update_button_SetPlanesToEqualSpacing.on_click(on_button_click_SetPlanesToEqualSpacing)
#     update_button_ReversePlaneOrder.on_click(on_button_click_ReversePlaneOrder)
#     update_button_ViewDisplay.on_click(update_displayWidget)
#     Init_button_PiSweep.on_click(InitialPiSweep)
#     Save_MaskProp_button.on_click(SaveMaskProps)
#     LoadPiFlipMasks_button.on_click(LoadPiFlipAlignmentMasks)
#     LoadMaskFile_button.on_click(LoadMaskFiles)
    
#     # Organize the widgets using layout containers
#     grid = widgets.GridBox(
#         children=[
#             widget_channel, widget_pol,widget_PolEnableChecBox,widget_Plane,widget_MaskEnableChecBox,
#             widget_Mode_H, widget_Mode_V,
#             widget_XCenter, widget_YCenter, widget_XTilt,
#             widget_YTilt, widget_Piston, widget_Defocus,widget_RefreshTime,
#             update_button_currentSLM, update_button_AllSLM, 
#             LoadPiFlipMasks_button,
#             update_button_ClearSLM,update_button_SetZernikeToZero,
#             update_button_SetPlanesToEqualSpacing,update_button_ReversePlaneOrder,update_button_ViewDisplay,
#             Save_MaskProp_button,
#             widget_SweepStep,Init_button_PiSweep,
#             widget_MaskFilename,LoadMaskFile_button],
#          layout=widgets.Layout(
#         grid_template_columns="repeat(5, 1fr)",
#         grid_template_rows="repeat(5, auto)",
#         grid_gap="10px"
#     )
#         # layout=widgets.Layout(
#         #     grid_template_columns="repeat(5, 1fr)",
#         #     grid_gap="10px"
#         # )
#     )
#     return grid
