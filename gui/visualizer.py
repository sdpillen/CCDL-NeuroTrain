#!/usr/bin/env python

import wx
import os
import wx.lib.agw.peakmeter as pm
import numpy as np
import scipy as sp
import scipy.signal as sig
import core.ccdl as ccdl
import core.variables 
import gui
import threading
import time
import NFT
import fixation #probably not needed anymore;

NFT.SPTruVal =  0
SPTruFreq = 0

#This is for the control loading function
wildcard = "All files (*.*)|*.*"    \
           "Subject output(*.csv)|*.csv|"

class SingleChannelVisualizer( gui.ManagerPanel ):
    def __init__(self, parent, manager, size=(50, 25)):
        # Parameters for periodogram.
        self.length = 8       # Length of the time series to analyze
        self.window = 1       # Moving window for periodogram
        self.overlap = 0.5    # Overlap between moving windows in periodogram
        self.sampling = 128   # Internal sampling rate (fixed, for now)
        
        self.sensor_data =  np.zeros((0, len(core.variables.CHANNELS)),
                                      order="C", dtype=np.double)
        
        self._visualizing = False    # Whether the peakmeter is being updated
        #self.connected = False      # Whether the headset is connected
        self.update = 0.25           # Interval at which the PeakMeter is updated
        
        gui.ManagerPanel.__init__(self, parent, manager,
                                  manager_state=True,
                                  monitored_events=(ccdl.HEADSET_FOUND_EVENT,))
        self.manager.add_listener(ccdl.SAMPLING_EVENT, self.save_sensor_data)
        
        self.channel = 1  # Starts with first real channel
        
    @property
    def visualizing(self):
        return self._visualizing
    
    @visualizing.setter
    def visualizing(self, value):
        self._visualizing = value
        self.update_interface()
        
        
    def create_objects(self):
        """Creates the GUI objects"""
        meter = pm.PeakMeterCtrl(self, wx.ID_ANY, style=wx.SIMPLE_BORDER,
                                      agwStyle=pm.PM_VERTICAL) #, size=(400, 100))
        meter.SetMeterBands(32, 20)  # Visualize from 1 to 32 Hz
        meter.SetRangeValue(3.0, 6.0, 9.0)
        meter.ShowGrid(True)
        meter.SetBandsColour(wx.Colour(255,0,0), wx.Colour(255, 153, 0), wx.Colour(255,255,0))
        
        meter.SetData([0]*32, offset=0, size=32)
        self.meter = meter
        
        sensors = [core.variables.SENSOR_NAMES[i] for i in core.variables.SENSORS]
        sensors.append("F3+F4")
        #print(sensors) #debug
        selector = wx.RadioBox(self, wx.ID_ANY, "Select Channel", wx.DefaultPosition,
                               wx.DefaultSize, sensors, 8)
        self.selector = selector
        self.Bind(wx.EVT_RADIOBOX, self.on_select_channel, self.selector)
        
        self.start_btn = wx.Button(self, wx.ID_ANY, "Start", size=(100, 25))
        self.stop_btn = wx.Button(self, wx.ID_ANY, "Stop", size=(100, 25))
        self.Next_btn = wx.Button(self, wx.ID_ANY, "Next Round", size=(100, 25))
        self.LoadControl_btn = wx.Button(self, wx.ID_ANY, "Control (unset)", size=(100, 25))
        self.Bind(wx.EVT_BUTTON, self.on_start, self.start_btn)
        self.Bind(wx.EVT_BUTTON, self.on_stop, self.stop_btn)
        self.Bind(wx.EVT_BUTTON, self.on_Next, self.Next_btn)
        self.Bind(wx.EVT_BUTTON, self.on_LoadControl, self.LoadControl_btn)
        
    def on_start(self, evt):
        """Starts the visualizing thread""" 
        self.LoadControl_btn.Disable()
        self.visualizing = True
        visThread = threading.Thread(group=None, target=self.update_meter)
        visThread.start()
        self.update_interface() 
        NFT.main()

		
    def on_Next(self, evt):
        """Moves between stages of the program"""
        #if NFT.pausetime == True and NFT.stage != 0: 
        NFT.NEXT = True
        
    def on_stop(self, evt):
        """Stops the thread"""
        self.visualizing = False
        
    def on_LoadControl(self, evt):
        """Moves between stages of the program"""
        #if NFT.pausetime == True and NFT.stage != 0: 
        dlg = wx.FileDialog(self, message="Select previous CSV ...",
                            defaultDir=os.getcwd(), defaultFile="",
                            wildcard=wildcard, style=wx.FD_OPEN)

        dlg.SetFilterIndex(1)

        # Show the dialog and retrieve the user response. If it is the OK response, 
        # process the data.
        if dlg.ShowModal() == wx.ID_OK:
            fname = dlg.GetPath()
        dlg.Destroy()
        
        # If the filename exists, ask for confirmation
   
        self.filename = fname
        self.LoadControl_btn.SetLabel('Control (SET)')
        NFT.ControlFile = fname
        NFT.ControlRecording = True
        
    def update_meter(self):
        """Updates the PeakMeter data every UPDATE secs"""
        while self.visualizing:
            self.analyze_data()
            time.sleep(self.update)
    
    def refresh(self, args):
        """Just a shortcut for update_interface"""
        self.update_interface()
    
    def update_interface(self):
        """Updates the interface"""
        if self.manager.has_user :  # 'or True' for testing purposes
            self.selector.Enable()
            NFT.DISCONNECT = False #This reassures NFT that the user is connected.
            if self.visualizing:
                self.start_btn.Disable()
                self.Next_btn.Enable()
                self.stop_btn.Enable()
                self.meter.Enable()
                self.meter.SetBandsColour(wx.Colour(255,0,0),
                                          wx.Colour(255, 153, 0),
                                          wx.Colour(255,255,0))
            else:
                self.meter.SetBandsColour(wx.Colour(100,100,100),
                                          wx.Colour(100,100,100),
                                          wx.Colour(100,100,100))


                self.start_btn.Enable()
                self.LoadControl_btn.Enable()
                self.Next_btn.Disable() #this is off for now; change to ENABLE if I have use in the future.
                self.stop_btn.Disable()
                self.meter.Disable()
        else:
            NFT.DISCONNECT = True  #This tells NFT to pause things
            self.selector.Disable()
            self.start_btn.Disable()
            self.stop_btn.Disable()
            self.Next_btn.Disable()
            self.meter.Disable()
            self.meter.SetBandsColour(wx.Colour(100,100,100),
                                      wx.Colour(100,100,100),
                                      wx.Colour(100,100,100))

    
        
    def do_layout(self):
        """Lays out the components"""
        box1 = wx.BoxSizer(wx.HORIZONTAL)
        box1.Add(self.start_btn, 0, wx.ALIGN_LEFT | wx.ALL, 5)
        box1.Add(self.stop_btn, 0, wx.ALIGN_LEFT | wx.ALL, 5)
        box1.Add(self.Next_btn, 0, wx.ALIGN_LEFT | wx.ALL, 5)
        box1.Add(self.LoadControl_btn, 0, wx.ALIGN_LEFT | wx.ALL, 5)
        box2 = wx.BoxSizer( wx.VERTICAL )
        box2.Add(self.selector, 0, wx.EXPAND | wx.HORIZONTAL)
        box2.Add(box1)
        box2.Add(self.meter, 1, wx.EXPAND | wx.HORIZONTAL)
        self.SetSizerAndFit(box2)
        self.update_interface()


    def save_sensor_data(self, data):
        """
        Accumulates recorded data into an array. If the array exceeds
        the specified self.length, only the last (length * sampling)
        samples are kept.
        """
        self.sensor_data = np.vstack( (self.sensor_data, data) )
        n_samples, n_channels = self.sensor_data.shape
        max_length = self.length * self.sampling
        
        if n_samples > max_length:
            self.sensor_data = self.sensor_data[n_samples - max_length:,]
                
    
    def on_select_channel(self, evt):
        """Updates the selected channel"""
        box_id = self.selector.GetSelection()
        #print(box_id) #debug
        if box_id == 14:
            self.channel = 15
        else:
            sensor_id = core.variables.SENSORS[box_id]
            #print(core.variables.SENSORS[box_id]) #debug
           
            channel_id = core.variables.CHANNELS.index(sensor_id) #VITAL; seems to just say which channel name in the list?  Bizarre.  I must be missing osmething
            #print(channel_id) #debug
            self.channel = channel_id
    #NB: 3/6, 10/13;   4 and 11 are the channel ids for what I want.
    
    def analyze_data(self):
        """Creates the periodogram of a series"""
        sr = self.sampling
        if self.sensor_data.shape[0] >= sr * self.length:
            nperseg = self.window * sr
            noverlap = int(self.overlap * float(sr))
            if self.channel == 15: #This is for when the ratio of channels is selected.
            
                freq, density = sig.welch(self.sensor_data[:, 3], fs=sr, nperseg = nperseg,
                                          noverlap = noverlap, scaling='density')
      
                freqb, densityb = sig.welch(self.sensor_data[:, 12], fs=sr, nperseg = nperseg,
                                          noverlap = noverlap, scaling='density')
                #All these values are extracted                           
                NFT.VoltMax = np.amax([np.amax(self.sensor_data[:, 3]), np.amax(self.sensor_data[:, 12])])
                NFT.VoltMedian = (np.median(self.sensor_data[:, 3]) + np.median(self.sensor_data[:, 12]))/2
                NFT.VoltMin = np.amin([np.amin(self.sensor_data[:, 3]), np.amin(self.sensor_data[:, 12])])
                densityF3 = sp.log(density)[1:]  
                densityF4 = sp.log(densityb)[1:]
                SPValsF3 = np.average(densityF3[2:7])/np.average(densityF3[10:19]) # 4-8 Hz, 12-20 Hz (You add 2 to the first  value, and +1 to the second value in these arrays)
                SPValsF4 = np.average(densityF4[2:7])/np.average(densityF4[10:19]) # 4-8 Hz, 12-20 Hz
                NFT.SPTruVal = np.average(SPValsF3 + SPValsF4)  
                
                freq = freq[1:] #not really needed anymore
                self.meter.SetData((densityF3[0:32] + densityF4[0:32])/2, offset=0, size=32)
                SPFreqs = freq #this was just used for testing purposes
                # print("TESTING")
                # print SPFreqs[4] #this gives 5


                NFT.LoNoise = (densityF3[0] + densityF4[0])/2 #1 Hz
                NFT.HiNoise = (np.average(densityF3[38:58]) + np.average(densityF4[38-58]))/2 #40-59 Hz

            else: #This is for all single channels
                freq, density = sig.welch(self.sensor_data[:, self.channel], fs=sr, nperseg = nperseg,
                                          noverlap = noverlap, scaling='density')
                                          
                NFT.VoltMax = np.amax(self.sensor_data[:, self.channel])
                NFT.VoltMedian = np.median(self.sensor_data[:, self.channel])
                NFT.VoltMin = np.amin(self.sensor_data[:, self.channel])
                density = sp.log(density)[1:]
                freq = freq[1:]
                self.meter.SetData(density[0:32], offset=0, size=32)
                SPFreqs = freq
                # print("TESTING")
                # print SPFreqs[4] #this gives 5
                SPVals = density
                NFT.SPTruVal = (np.average(SPVals[2:7])/np.average(SPVals[10:19])) #4-8 and 12-20 (You add 2 to the first  value, and +1 to the second value in these arrays)
                NFT.LoNoise = SPVals[0] #1 Hz
                NFT.HiNoise = np.average(SPVals[38:58]) #40-59 Hz

            # print(np.amax(self.sensor_data[:,15])) #This is GyroX, 16 is GyroY.
            # print(np.amin(self.sensor_data[:,15]))
            #print(NFT.HiNoise, NFT.LoNoise, NFT.SPTruVal)
            #print(SPTruVal)
            #print(SPTruFreq)
