import sys
import Lab_Equipment.Config.config as config
import numpy as np
import matplotlib.pyplot as plt
import time

from Lab_Equipment.DeformableMirror.lib.asdk import DM as DeformableMirrorLib

class DeformanbleMirror_Obj:

    def __init__(self,serialName=None,RefreshRate=10e-3):
        super().__init__()
        if serialName is None:
            # List of all the resources)
            print("You need to pass the serialName into DeformanbleMirror_Obj. Look at back of Deformable mirror for serial name")
            return
        self.serialName=serialName
        self.DM_obj = DeformableMirrorLib(self.serialName )
        self.NumAct=self.Get_property("NBOfActuator")
        print(f"Number of actuators: {self.NumAct}")
        self.ActArr=np.zeros(self.NumAct)
        self.RefreshRate=RefreshRate
        
    def __del__(self):
      print("Deformable mirror has been destoryed")
      self.Set_MirrorToZero()

    def Get_property(self,PropertyString):
        property= self.DM_obj.Get(PropertyString)
        if (PropertyString=="NBOfActuator"):
            property=int(property)
        return property
    
    def Set_MirrorSurface(self,ActArr=None):
        if ActArr is not None:
            self.ActArr=ActArr  
            if (len(self.ActArr) != self.NumAct):
                print(f"Actuator array must be of length {self.NumAct}.")
                return
            self.ActArr=ActArr  
        clippingOn=np.all((self.ActArr >= -1) & (self.ActArr <= 1))    
        if clippingOn==False:
            np.clip(self.ActArr, -1, 1)
            print("Actuator values where greater then 1 or less then -1 so clipping has been activated")

        self.DM_obj.Send(self.ActArr)
        time.sleep(self.RefreshRate)

    def Set_MirrorToZero(self):
        self.DM_obj.Reset()
        time.sleep(self.RefreshRate) 
    def saveActuatorValuesFromFile(self,filenamePrefix=''):
        FolderPath = config.PATH_TO_DEFROMABLEMIRROR_FOLDER+'ActuatorValues'+config.SLASH+"ActuatorValues_"
        FullPath = FolderPath + filenamePrefix+'.npz'
        np.savez(FullPath, ActArr=self.ActArr)   
    def loadActuatorValuesFromFile(self,filenamePrefix=''):
        """
        Loads actuator values from a file and sets the mirror surface.

        Parameters:
        - filename (str): Path to the file containing actuator values.
        """
        try:
            FolderPath = config.PATH_TO_DEFROMABLEMIRROR_FOLDER+'ActuatorValues'+config.SLASH+"ActuatorValues_"
            FullPath = FolderPath + filenamePrefix+'.npz'
            data = np.load(FullPath)
            # Access arrays
            self.ActArr = data["ActArr"]
        except Exception as e:
            print(f"Error loading actuator values: {e}")
            
        self.Set_MirrorSurface()
    
    # This is hard coded to the 9x9 grid
    # This is the 69 actuator layout
    # 5,7,9,9,9,9,9,7,5
    def Plot_MirrorSurface(self,actuator_values=None):
        """
        Visualises the deformable mirror actuator heights using imshow.

        Parameters:
        - actuator_values (np.ndarray): 1D array of length 69.
        """
        if actuator_values is None:
            actuator_values=self.ActArr
            
        if len(actuator_values) != 69:
            raise ValueError("Input array must be of length 69.")
        
        column_heights = [5, 7, 9, 9, 9, 9, 9, 7, 5]
        max_height = max(column_heights)
        grid = np.full((max_height, 9), np.nan)

        idx = 0
        for col, height in enumerate(column_heights):
            start_row = (max_height - height) // 2
            grid[start_row:start_row + height, col] = actuator_values[idx:idx + height]
            idx += height

        plt.figure(figsize=(6, 6))
        im = plt.imshow(grid, cmap='viridis', origin='lower')
        plt.title("Deformable Mirror Actuator Heights")
        plt.colorbar(im, label="Height")
        plt.xlabel("Column Index")
        plt.ylabel("Row Index")
        plt.tight_layout()
        plt.show()
    
    # This is hard coded to the 9x9 grid
    # This is the 69 actuator layout
    # 5,7,9,9,9,9,9,7,5
    def actuator2DGridTo1DArray(self,full_grid):
        """
        Takes a 9x9 full grid and extracts only the actuator values
        according to the known 69-actuator layout.

        Parameters:
        - full_grid (np.ndarray): 9x9 numpy array representing a pattern.

        Returns:
        - actuator_values (np.ndarray): 1D array of length 69.
        """
        if full_grid.shape != (9, 9):
            raise ValueError("Input grid must be 9x9.")
        
        column_heights = [5, 7, 9, 9, 9, 9, 9, 7, 5]
        max_height = 9
        actuator_values = []

        for col, height in enumerate(column_heights):
            start_row = (max_height - height) // 2
            end_row = start_row + height
            actuator_values.extend(full_grid[start_row:end_row, col])

        return np.array(actuator_values)
        
    