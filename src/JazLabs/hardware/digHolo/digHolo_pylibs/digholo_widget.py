import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
import cv2
from IPython.display import display
import Lab_Equipment.digHolo.digHolo_pylibs.digholoObject as digholoLib

def create_digholo_widget(digdigholoObj:digholoLib.digholoObject):
    """
    Create an interactive widget panel for controlling the digholoProperties
    of a digholoObject. This panel mimics the style of the SLM_widget.py script.
    
    Parameters:
        digholo: An instance of the digholoObject class which contains a 
                 digholoProperties dictionary and a digholo_SetProps() method.
    
    Returns:
        A GridBox widget containing the controls.
    """
    # Widgets for numeric properties
    widget_polIdx = widgets.Dropdown(
        options=[('H',0), ('V', 1)],
        value=0, description='pol',
        layout=widgets.Layout(width='140px')
    )
    widget_polCount = widgets.IntText(
        value=digdigholoObj.digholoProperties.get("polCount", 1),
        description="Pol Count",
        layout=widgets.Layout(width='200px')
    )
    widget_Wavelength = widgets.FloatText(
        value=digdigholoObj.digholoProperties.get("Wavelength", 0.0),
        description="Wavelength (nm)",
        layout=widgets.Layout(width='200px')
    )
    widget_WavelengthCount = widgets.IntText(
        value=digdigholoObj.digholoProperties.get("WavelengthCount", 1),
        description="Wavelength Count",
        layout=widgets.Layout(width='200px')
    )
   
    
    widget_PixelSize = widgets.FloatText(
        value=digdigholoObj.digholoProperties.get("PixelSize", 0.0),
        description="Pixel Size (um)",
        layout=widgets.Layout(width='200px')
    )
    widget_maxMG = widgets.IntText(
        value=digdigholoObj.digholoProperties.get("maxMG", 1),
        description="maxMG",
        layout=widgets.Layout(width='200px')
    )
    widget_fftWindowSizeX = widgets.IntText(
        value=digdigholoObj.digholoProperties.get("fftWindowSizeX", 256),
        description="fftWindowSizeX",
        layout=widgets.Layout(width='200px')
    )
    widget_fftWindowSizeY = widgets.IntText(
        value=digdigholoObj.digholoProperties.get("fftWindowSizeY", 256),
        description="fftWindowSizeY",
        layout=widgets.Layout(width='200px')
    )
    widget_FFTRadius = widgets.FloatText(
        value=digdigholoObj.digholoProperties.get("FFTRadius", 0.0),
        description="FFTRadius",
        layout=widgets.Layout(width='200px')
    )
    
    # Widgets for beam centre positions
    widget_BeamCentreX = widgets.IntText(
        value=digdigholoObj.digholoProperties.get("BeamCentreX", 0),
        description="BeamCentreX",
        layout=widgets.Layout(width='200px')
    )
    widget_BeamCentreY = widgets.IntText(
        value=digdigholoObj.digholoProperties.get("BeamCentreY", 0),
        description="BeamCentreY",
        layout=widgets.Layout(width='200px')
    )
    
    # Widgets for waist, defocus, and tilt parameters
    widget_BasisWaist = widgets.FloatText(
        value=digdigholoObj.digholoProperties.get("BasisWaist", 1.0),
        description="BasisWaist",
        layout=widgets.Layout(width='200px')
    )
    widget_Defocus = widgets.FloatText(
        value=digdigholoObj.digholoProperties.get("Defocus", 0.0),
        description="Defocus",
        layout=widgets.Layout(width='200px')
    )
    widget_XTilt = widgets.FloatText(
        value=digdigholoObj.digholoProperties.get("XTilt", 0.0),
        description="XTilt",
        layout=widgets.Layout(width='200px')
    )
    widget_YTilt = widgets.FloatText(
        value=digdigholoObj.digholoProperties.get("YTilt", 0.0),
        description="YTilt",
        layout=widgets.Layout(width='200px')
    )
    
    # Widgets for Auto-Alignment properties as checkboxes
    widget_AutoAlignBeamCentre = widgets.Checkbox(
        value=bool(digdigholoObj.digholoProperties.get("AutoAlignBeamCentre", 0)),
        description="AutoAlignBeamCentre",
        layout=widgets.Layout(width='200px')
    )
    widget_AutoAlignDefocus = widgets.Checkbox(
        value=bool(digdigholoObj.digholoProperties.get("AutoAlignDefocus", 0)),
        description="AutoAlignDefocus",
        layout=widgets.Layout(width='200px')
    )
    widget_AutoAlignTilt = widgets.Checkbox(
        value=bool(digdigholoObj.digholoProperties.get("AutoAlignTilt", 0)),
        description="AutoAlignTilt",
        layout=widgets.Layout(width='200px')
    )
    widget_AutoAlignBasisWaist = widgets.Checkbox(
        value=bool(digdigholoObj.digholoProperties.get("AutoAlignBasisWaist", 0)),
        description="AutoAlignBasisWaist",
        layout=widgets.Layout(width='200px')
    )
    widget_AutoAlignFourierWindowRadius = widgets.Checkbox(
        value=bool(digdigholoObj.digholoProperties.get("AutoAlignFourierWindowRadius", 0)),
        description="AutoAlignFourierWindowRadius",
        layout=widgets.Layout(width='200px')
    )
    # Widgets for additional parameters
    widget_goalIdx = widgets.Dropdown(
        options=[('IL',digholoLib.digholoMetrics.IL), 
                 ('MDL',digholoLib.digholoMetrics.MDL),
                 ('SNRAVG',digholoLib.digholoMetrics.SNRAVG),
                 ('DIAG',digholoLib.digholoMetrics.DIAG),
                 ('SNRBEST',digholoLib.digholoMetrics.SNRBEST),
                 ('SNRWORST',digholoLib.digholoMetrics.SNRWORST),
                 ('SNRMG',digholoLib.digholoMetrics.SNRMG),
                 ('DIAGWORST',digholoLib.digholoMetrics.DIAGWORST),
                 ('DIAGBEST',digholoLib.digholoMetrics.DIAGWORST)],
        value=digholoLib.digholoMetrics.IL, description='Alignment Goal Metric',
        layout=widgets.Layout(width='140px')
    )
    widget_basisType = widgets.Dropdown(
        options=[('HG',0), 
                 ('LG',1),
                 ('Custom',1)],
        value=0, description='basis type',
        layout=widgets.Layout(width='140px')
    )
    widget_resolutionMode = widgets.Dropdown(
        options=[('Full',0), 
                 ('Low',1)
                ],
        value=0, description='Resolution Mode',
        layout=widgets.Layout(width='140px')
    )
    widget_verbosity = widgets.Dropdown(
        options=[('None',0), 
                 ('Basic',1),
                 ('Debug',2),
                 ('The Mean of Life',3)
                ],
        value=0, description='Output Verbosity',
        layout=widgets.Layout(width='140px')
    )
    
    widget_TransformMatrixFilename = widgets.Text(
        value=digdigholoObj.digholoProperties.get("TransformMatrixFilename", ""),
        description="TransformMatrixFilename",
        layout=widgets.Layout(width='250px')
    )
    update_CustomMatrix_button = widgets.Button(
        description="Update Custom Transform Matrix",
        layout=widgets.Layout(width='200px')
    )
    # Update button to apply changes
    update_Widget_button = widgets.Button(
        description="Update Widget Properties",
        layout=widgets.Layout(width='200px')
    )
     # Update button to apply changes
    update_digholoObj_button = widgets.Button(
        description="Update digholo Object Properties",
        layout=widgets.Layout(width='200px')
    )
    
     # Define event handlers (using closures to capture widget variables)
    def on_value_change(change):
        owner = change['owner']
        # Update numeric properties
        if owner == widget_Wavelength:
            digdigholoObj.digholoProperties["Wavelength"] = owner.value
        elif owner == widget_WavelengthCount:
            digdigholoObj.digholoProperties["WavelengthCount"] = owner.value
        elif owner == widget_polCount:
            digdigholoObj.digholoProperties["polCount"] = owner.value
        elif owner == widget_PixelSize:
            digdigholoObj.digholoProperties["PixelSize"] = owner.value
        elif owner == widget_maxMG:
            digdigholoObj.digholoProperties["maxMG"] = owner.value
        elif owner == widget_fftWindowSizeX:
            digdigholoObj.digholoProperties["fftWindowSizeX"] = owner.value
        elif owner == widget_fftWindowSizeY:
            digdigholoObj.digholoProperties["fftWindowSizeY"] = owner.value
        elif owner == widget_FFTRadius:
            digdigholoObj.digholoProperties["FFTRadius"] = owner.value
            
        # Update beam centre and related properties based on polarization index
        elif owner == widget_BeamCentreX:
            if widget_polIdx.value == 0:
                digdigholoObj.digholoProperties["BeamCentreXPolH"] = owner.value
            else:
                digdigholoObj.digholoProperties["BeamCentreXPolV"] = owner.value
        elif owner == widget_BeamCentreY:
            if widget_polIdx.value == 0:
                digdigholoObj.digholoProperties["BeamCentreYPolH"] = owner.value
            else:
                digdigholoObj.digholoProperties["BeamCentreYPolV"] = owner.value
        elif owner == widget_BasisWaist:
            if widget_polIdx.value == 0:
                digdigholoObj.digholoProperties["BasisWaistPolH"] = owner.value
            else:
                digdigholoObj.digholoProperties["BasisWaistPolV"] = owner.value
        elif owner == widget_Defocus:
            if widget_polIdx.value == 0:
                digdigholoObj.digholoProperties["DefocusPolH"] = owner.value
            else:
                digdigholoObj.digholoProperties["DefocusPolV"] = owner.value
        elif owner == widget_XTilt:
            if widget_polIdx.value == 0:
                digdigholoObj.digholoProperties["XTiltPolH"] = owner.value
            else:
                digdigholoObj.digholoProperties["XTiltPolV"] = owner.value
        elif owner == widget_YTilt:
            if widget_polIdx.value == 0:
                digdigholoObj.digholoProperties["YTiltPolH"] = owner.value
            else:
                digdigholoObj.digholoProperties["YTiltPolV"] = owner.value
            
        # Update auto-alignment properties (convert boolean to integer flag)
        elif owner == widget_AutoAlignBeamCentre:
            digdigholoObj.digholoProperties["AutoAlignBeamCentre"] = 1 if owner.value else 0
        elif owner == widget_AutoAlignDefocus:
            digdigholoObj.digholoProperties["AutoAlignDefocus"] = 1 if owner.value else 0
        elif owner == widget_AutoAlignTilt:
            digdigholoObj.digholoProperties["AutoAlignTilt"] = 1 if owner.value else 0
        elif owner == widget_AutoAlignBasisWaist:
            digdigholoObj.digholoProperties["AutoAlignBasisWaist"] = 1 if owner.value else 0
        elif owner == widget_AutoAlignFourierWindowRadius:
            digdigholoObj.digholoProperties["AutoAlignFourierWindowRadius"] = 1 if owner.value else 0
            
        # Update additional dropdown properties
        elif owner == widget_goalIdx:
            digdigholoObj.digholoProperties["goalIdx"] = owner.value
        elif owner == widget_basisType:
            digdigholoObj.digholoProperties["basisType"] = owner.value
        elif owner == widget_resolutionMode:
            digdigholoObj.digholoProperties["resolutionMode"] = owner.value
        elif owner == widget_verbosity:
            digdigholoObj.digholoProperties["verbosity"] = owner.value
            
        # If the polarization index changes, update all dependent properties
        # elif owner == widget_polIdx:
        #     if widget_polIdx.value == 0:
        #         digdigholoObj.digholoProperties["BeamCentreXPolH"] = widget_BeamCentreX.value
        #         digdigholoObj.digholoProperties["BeamCentreYPolH"] = widget_BeamCentreY.value
        #         digdigholoObj.digholoProperties["BasisWaistPolH"] = widget_BasisWaist.value
        #         digdigholoObj.digholoProperties["DefocusPolH"] = widget_Defocus.value
        #         digdigholoObj.digholoProperties["XTiltPolH"] = widget_XTilt.value
        #         digdigholoObj.digholoProperties["YTiltPolH"] = widget_YTilt.value
        #     else:
        #         digdigholoObj.digholoProperties["BeamCentreXPol"] = widget_BeamCentreX.value
        #         digdigholoObj.digholoProperties["BeamCentreYPol"] = widget_BeamCentreY.value
        #         digdigholoObj.digholoProperties["BasisWaistPol"] = widget_BasisWaist.value
        #         digdigholoObj.digholoProperties["DefocusPol"] = widget_Defocus.value
        #         digdigholoObj.digholoProperties["XTiltPol"] = widget_XTilt.value
        #         digdigholoObj.digholoProperties["YTiltPol"] = widget_YTilt.value
            
        # Apply the updated properties
        digdigholoObj.digholo_SetProps()
        
     
    
    def update_widgets_from_properties(*args):
        # Read numeric properties and update the corresponding widgets.
        widget_Wavelength.value = digdigholoObj.digholoProperties.get("Wavelength", widget_Wavelength.value)
        widget_WavelengthCount.value = digdigholoObj.digholoProperties.get("WavelengthCount", widget_WavelengthCount.value)
        widget_polCount.value = digdigholoObj.digholoProperties.get("polCount", widget_polCount.value)
        widget_PixelSize.value = digdigholoObj.digholoProperties.get("PixelSize", widget_PixelSize.value)
        widget_maxMG.value = digdigholoObj.digholoProperties.get("maxMG", widget_maxMG.value)
        widget_fftWindowSizeX.value = digdigholoObj.digholoProperties.get("fftWindowSizeX", widget_fftWindowSizeX.value)
        widget_fftWindowSizeY.value = digdigholoObj.digholoProperties.get("fftWindowSizeY", widget_fftWindowSizeY.value)
        widget_FFTRadius.value = digdigholoObj.digholoProperties.get("FFTRadius", widget_FFTRadius.value)

        # Determine polarization index
        polIdx = widget_polIdx.value
        if polIdx == 0:
            widget_BeamCentreX.value = digdigholoObj.digholoProperties.get("BeamCentreXPolH", widget_BeamCentreX.value)
            widget_BeamCentreY.value = digdigholoObj.digholoProperties.get("BeamCentreYPolH", widget_BeamCentreY.value)
            widget_BasisWaist.value = digdigholoObj.digholoProperties.get("BasisWaistPolH", widget_BasisWaist.value)
            widget_Defocus.value = digdigholoObj.digholoProperties.get("DefocusPolH", widget_Defocus.value)
            widget_XTilt.value = digdigholoObj.digholoProperties.get("XTiltPolH", widget_XTilt.value)
            widget_YTilt.value = digdigholoObj.digholoProperties.get("YTiltPolH", widget_YTilt.value)
        else:
            widget_BeamCentreX.value = digdigholoObj.digholoProperties.get("BeamCentreXPol", widget_BeamCentreX.value)
            widget_BeamCentreY.value = digdigholoObj.digholoProperties.get("BeamCentreYPol", widget_BeamCentreY.value)
            widget_BasisWaist.value = digdigholoObj.digholoProperties.get("BasisWaistPol", widget_BasisWaist.value)
            widget_Defocus.value = digdigholoObj.digholoProperties.get("DefocusPol", widget_Defocus.value)
            widget_XTilt.value = digdigholoObj.digholoProperties.get("XTiltPol", widget_XTilt.value)
            widget_YTilt.value = digdigholoObj.digholoProperties.get("YTiltPol", widget_YTilt.value)

        # Update auto-alignment properties by converting integer flags back to booleans
        widget_AutoAlignBeamCentre.value = bool(digdigholoObj.digholoProperties.get("AutoAlignBeamCentre", 0))
        widget_AutoAlignDefocus.value = bool(digdigholoObj.digholoProperties.get("AutoAlignDefocus", 0))
        widget_AutoAlignTilt.value = bool(digdigholoObj.digholoProperties.get("AutoAlignTilt", 0))
        widget_AutoAlignBasisWaist.value = bool(digdigholoObj.digholoProperties.get("AutoAlignBasisWaist", 0))
        widget_AutoAlignFourierWindowRadius.value = bool(digdigholoObj.digholoProperties.get("AutoAlignFourierWindowRadius", 0))

        # Update additional dropdown or text properties
        widget_goalIdx.value = digdigholoObj.digholoProperties.get("goalIdx", widget_goalIdx.value)
        widget_basisType.value = digdigholoObj.digholoProperties.get("basisType", widget_basisType.value)
        widget_resolutionMode.value = digdigholoObj.digholoProperties.get("resolutionMode", widget_resolutionMode.value)
        widget_verbosity.value = digdigholoObj.digholoProperties.get("verbosity", widget_verbosity.value)
        widget_TransformMatrixFilename.value = digdigholoObj.digholoProperties.get("TransformMatrixFilename", widget_TransformMatrixFilename.value)
    
    
    def update_DigholoObj_properties(*args):
        
        polIdx=widget_polIdx.value
        # Update numeric properties
        digdigholoObj.digholoProperties["Wavelength"] = widget_Wavelength.value
        digdigholoObj.digholoProperties["WavelengthCount"] = widget_WavelengthCount.value
        digdigholoObj.digholoProperties["polCount"] = widget_polCount.value
        digdigholoObj.digholoProperties["PixelSize"] = widget_PixelSize.value
        digdigholoObj.digholoProperties["maxMG"] = widget_maxMG.value
        digdigholoObj.digholoProperties["fftWindowSizeX"] = widget_fftWindowSizeX.value
        digdigholoObj.digholoProperties["fftWindowSizeY"] = widget_fftWindowSizeY.value
        digdigholoObj.digholoProperties["FFTRadius"] = widget_FFTRadius.value

        # Update beam centre positions
        if polIdx==0:
            digdigholoObj.digholoProperties["BeamCentreXPolH"] = widget_BeamCentreX.value
            digdigholoObj.digholoProperties["BeamCentreYPolH"] = widget_BeamCentreY.value
            digdigholoObj.digholoProperties["BasisWaistPolH"] = widget_BasisWaist.value
            digdigholoObj.digholoProperties["DefocusPolH"] = widget_Defocus.value
            digdigholoObj.digholoProperties["XTiltPolH"] = widget_XTilt.value
            digdigholoObj.digholoProperties["YTiltPolH"] = widget_YTilt.value

        else:
            digdigholoObj.digholoProperties["BeamCentreXPol"] = widget_BeamCentreX.value
            digdigholoObj.digholoProperties["BeamCentreYPol"] = widget_BeamCentreY.value
            digdigholoObj.digholoProperties["BasisWaistPol"] = widget_BasisWaist.value
            digdigholoObj.digholoProperties["DefocusPol"] = widget_Defocus.value
            digdigholoObj.digholoProperties["XTiltPol"] = widget_XTilt.value
            digdigholoObj.digholoProperties["YTiltPol"] = widget_YTilt.value
            
          
        # Update auto-alignment (convert boolean to integer flag)
        digdigholoObj.digholoProperties["AutoAlignBeamCentre"] = 1 if widget_AutoAlignBeamCentre.value else 0
        digdigholoObj.digholoProperties["AutoAlignDefocus"] = 1 if widget_AutoAlignDefocus.value else 0
        digdigholoObj.digholoProperties["AutoAlignTilt"] = 1 if widget_AutoAlignTilt.value else 0
        digdigholoObj.digholoProperties["AutoAlignBasisWaist"] = 1 if widget_AutoAlignBasisWaist.value else 0
        digdigholoObj.digholoProperties["AutoAlignFourierWindowRadius"] = 1 if widget_AutoAlignFourierWindowRadius.value else 0

        # Update additional parameters
        digdigholoObj.digholoProperties["goalIdx"] = widget_goalIdx.value
        digdigholoObj.digholoProperties["basisType"] = widget_basisType.value
        digdigholoObj.digholoProperties["resolutionMode"] = widget_resolutionMode.value
        digdigholoObj.digholoProperties["verbosity"] = widget_verbosity.value
        digdigholoObj.digholoProperties["TransformMatrixFilename"] = widget_TransformMatrixFilename.value

        # Apply changes by calling the digholo_SetProps() method
        digdigholoObj.digholo_SetProps()
        
    def on_pol_change(change):
        new_polIdx = change['new']
        
        if new_polIdx==0:
            digdigholoObj.digholoProperties["BeamCentreXPolH"] = widget_BeamCentreX.value
            digdigholoObj.digholoProperties["BeamCentreYPolH"] = widget_BeamCentreY.value
            digdigholoObj.digholoProperties["BasisWaistPolH"] = widget_BasisWaist.value
            digdigholoObj.digholoProperties["DefocusPolH"] = widget_Defocus.value
            digdigholoObj.digholoProperties["XTiltPolH"] = widget_XTilt.value
            digdigholoObj.digholoProperties["YTiltPolH"] = widget_YTilt.value

        else:
            digdigholoObj.digholoProperties["BeamCentreXPol"] = widget_BeamCentreX.value
            digdigholoObj.digholoProperties["BeamCentreYPol"] = widget_BeamCentreY.value
            digdigholoObj.digholoProperties["BasisWaistPol"] = widget_BasisWaist.value
            digdigholoObj.digholoProperties["DefocusPol"] = widget_Defocus.value
            digdigholoObj.digholoProperties["XTiltPol"] = widget_XTilt.value
            digdigholoObj.digholoProperties["YTiltPol"] = widget_YTilt.value
    
    def UpdateCustomTransformMatrix():
        digdigholoObj.loadTransformMatrix(widget_TransformMatrixFilename.value)
    
    update_CustomMatrix_button.on_click(UpdateCustomTransformMatrix)
    update_Widget_button.on_click(lambda b: update_widgets_from_properties())
    update_digholoObj_button.on_click(lambda b: update_DigholoObj_properties())
    
    widget_polIdx.observe(on_pol_change, names='value')
    
    # Register observers for the widgets
    for w in [widget_polIdx, widget_polCount, widget_Wavelength, widget_WavelengthCount,
              widget_PixelSize, widget_maxMG, widget_fftWindowSizeX, widget_fftWindowSizeY,
              widget_FFTRadius, widget_BeamCentreX, widget_BeamCentreY,
              widget_BasisWaist, widget_Defocus, widget_XTilt, widget_YTilt,
              widget_AutoAlignBeamCentre, widget_AutoAlignDefocus, widget_AutoAlignTilt,
              widget_AutoAlignBasisWaist, widget_AutoAlignFourierWindowRadius,
              widget_goalIdx, widget_basisType, widget_resolutionMode,
              widget_verbosity]:
        w.observe(on_value_change, names='value')
    
    # Arrange all widgets in a grid layout
    grid = widgets.GridBox(
        children=[widget_polIdx,widget_polCount,
            widget_Wavelength, widget_WavelengthCount, 
            widget_PixelSize, widget_maxMG, widget_fftWindowSizeX, widget_fftWindowSizeY,
            widget_FFTRadius,
            widget_maxMG,
            widget_BeamCentreX,widget_BeamCentreY,widget_BasisWaist,widget_Defocus,
           widget_XTilt,widget_YTilt, 
           widget_AutoAlignBeamCentre,widget_AutoAlignDefocus, widget_AutoAlignTilt, widget_AutoAlignBasisWaist,
            widget_AutoAlignFourierWindowRadius, 
            widget_goalIdx, widget_basisType,widget_resolutionMode, widget_verbosity, 
            widget_TransformMatrixFilename,update_CustomMatrix_button,
            update_Widget_button, update_digholoObj_button
        ],
        layout=widgets.Layout(
            grid_template_columns="repeat(4, 1fr)",
            grid_gap="10px"
        )
    )
    
    return grid