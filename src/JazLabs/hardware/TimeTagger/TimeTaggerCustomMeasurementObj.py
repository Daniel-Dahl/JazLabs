import numpy as np
import time
import multiprocessing
from multiprocessing import shared_memory
import TimeTagger
import cv2
import copy
import numba
import matplotlib.pyplot as plt
class CustomCorrelationMeasurement(TimeTagger.CustomMeasurement):
    """
    Example for a single start - multiple stop measurement.
        The class shows how to access the raw time-tag stream.
    """

    def __init__(self, tagger, start_channels=[], stop_channels=[], binwidth=1, n_bins=1,MeasurementType=1):
        TimeTagger.CustomMeasurement.__init__(self, tagger)
        self.start_channels=start_channels
        self.stop_channels=stop_channels
    
        self.binwidth = binwidth
        self.n_bins = n_bins
        
        # this is to decide whether you should save the time tags
        self.saveData=True
        self.saveDataFile=True
        self.saveDataArray=False
        self.FileName="Data\\RawTimeTags"
        self.FileIdx=0
        self.MeasurementType=MeasurementType
        
        # The method register_channel(channel) activates
        # that data from the respective channels is transferred
        # from the Time Tagger to the PC.
        for ichan in range(len(self.start_channels)):
            self.register_channel(channel=self.start_channels[ichan])
        for ichan in range(len(self.stop_channels)):
            self.register_channel(channel=self.stop_channels[ichan])

        self.clear_impl() # this is where the data array
        
        # At the end of a CustomMeasurement construction,
        # we must indicate that we have finished.
        self.finalize_init()

    def __del__(self):
        # The measurement must be stopped before deconstruction to avoid
        # concurrent process() calls.
        self.stop()

    def getData(self):
        # Acquire a lock this instance to guarantee that process() is not running in parallel
        # This ensures to return a consistent data.
        with self.mutex:
            self.FileIdx=0
            return self.data.copy()
        
    def getDataNormalized(self):
         # Acquire a lock this instance to guarantee that process() is not running in parallel
        # This ensures to return a consistent data.
        with self.mutex:
            self.FileIdx=0
            dataNorm =  self.data.copy()
            # dataNorm = dataNorm*(self.max_bins*self.binwidth)/(self.binwidth*(self.Ch1Counts*self.Ch2Counts))
            # dataNorm = dataNorm*(self.max_bins*self.binwidth)/(self.binwidth*np.sum(dataNorm))
            # dataNorm = dataNorm*(1e12)/(self.binwidth*self.Ch1Counts*self.Ch2Counts)
            # dataNorm = dataNorm*(1e12)/(self.binwidth*np.sum(dataNorm)*2)
            dataNorm = dataNorm/(self.binwidth*np.sum(dataNorm)*1e12)
            
            # dataNorm = dataNorm*(1e12)/(self.binwidth*self.max_bins)
            
            
            
            
            # dataNorm = (dataNorm*self.max_bins*self.binwidth)/(self.binwidth*(self.Ch1Counts*self.Ch2Counts))
            # dataNorm = dataNorm/(np.sum(dataNorm)/self.max_bins)
            # *self.binwidth)/(self.binwidth*(self.Ch1Counts*self.Ch2Counts))
            
            
            print(self.Ch1Counts,self.Ch2Counts)
            # dataNorm = dataNorm / (dataNorm.size * self.binwidth)
            return dataNorm
        
    def getIndex(self):
        # This method does not depend on the internal state, so there is no
        # need for a lock.
        # arr = np.arange(0, self.max_bins) * self.binwidth
        arr = np.arange(-self.n_bins//2, self.n_bins//2) * self.binwidth
        
        return arr

    def clear_impl(self):
        # The lock is already acquired within the backend.
        self.last_start_timestamp = 0
        self.data = np.zeros((self.n_bins,), dtype=np.uint64)

    def on_start(self):
        self.fileObj_TT_type = open(self.FileName+'_type.bin', 'wb')
        self.fileObj_TT_missed_events = open(self.FileName+'_missed_events.bin', 'wb')
        self.fileObj_TT_channel = open(self.FileName+'_channel.bin', 'wb')
        self.fileObj_TT_time = open(self.FileName+'_time.bin', 'wb')
        self.Ch1Counts=0
        self.Ch2Counts=0
        
        # The lock is already acquired within the backend.
        pass

    def on_stop(self):
        self.fileObj_TT_type.close()
        self.fileObj_TT_missed_events.close()
        self.fileObj_TT_channel.close()
        self.fileObj_TT_time.close()
        
        # The lock is already acquired within the backend.
        pass

   
    
    
  

    def process(self, incoming_tags, begin_time, end_time):
        """
        Main processing method for the incoming raw time-tags.

        The lock is already acquired within the backend.
        self.data is provided as reference, so it must not be accessed
        anywhere else without locking the mutex.

        Parameters
        ----------
        incoming_tags
            The incoming raw time tag stream provided as a read-only reference.
            The storage will be deallocated after this call, so you must not store a reference to
            this object. Make a copy instead.
            Please note that the time tag stream of all channels is passed to the process method,
            not only the ones from register_channel(...).
        begin_time
            Begin timestamp of the of the current data block.
        end_time
            End timestamp of the of the current data block.
        """
        if self.saveData==True:
            if self.saveDataFile==True:
                self.FileIdx=self.FileIdx+1
                # np.save(self.FileName+str(self.FileIdx)+'.npy',incoming_tags)
                self.fileObj_TT_type.write(incoming_tags['type'].tobytes())#uint8
                self.fileObj_TT_missed_events.write(incoming_tags['missed_events'].tobytes())#uint16
                self.fileObj_TT_channel.write(incoming_tags['channel'].tobytes())#int32
                self.fileObj_TT_time.write(incoming_tags['time'].tobytes())#int64
            if self.saveDataArray==True:
                self.rawTimeTags=copy.deepcopy(incoming_tags)
                
        if (self.MeasurementType==0):#'1DHistogram'
            self.last_start_timestamp,Ch1Counts,Ch2Counts = fast_process_1Dhistogram(
                incoming_tags,
                self.data,
                self.stop_channels[0],          
                self.start_channels[0],
                self.n_bins,
                self.binwidth,
                self.last_start_timestamp)
            self.Ch1Counts=self.Ch1Counts+Ch1Counts
            self.Ch2Counts=self.Ch2Counts+Ch2Counts
            
        elif(self.MeasurementType==1):#'Correlation'
            Ch1Counts,Ch2Counts = fast_process_Correlations(
                incoming_tags,
                self.data,
                self.stop_channels[0],          
                self.start_channels[0],
                self.n_bins,
                self.binwidth,)
            self.Ch1Counts=self.Ch1Counts+Ch1Counts
            self.Ch2Counts=self.Ch2Counts+Ch2Counts
            
        # elif(self.MeasurementType==2):#'Correlation_post'
        #     self.last_start_timestamp,Ch1Counts,Ch2Counts = fast_process_Correlations_PostSelective(
        #         incoming_tags,
        #         self.data,
        #         self.stop_channels[0],          
        #         self.start_channels[0],
        #         self.start_channels[1],
        #         self.start_channels[2],
        #         self.n_bins,
        #         self.binwidth,
        #         self.last_start_timestamp)
        #     self.Ch1Counts=self.Ch1Counts+Ch1Counts
        #     self.Ch2Counts=self.Ch2Counts+Ch2Counts
            
        else:# If invalid measurement type was selected then just do nothing
            return






# @staticmethod
# @numba.jit(nopython=True, nogil=True)
# def fast_process_Correlations(
#         tags,
#         data,
#         click_channel,
#         start_channel,
#         binCount,
#         binwidth,
#         last_start_timestamp):
#     """
#     A precompiled version of the histogram algorithm for better performance
#     """
#     magTime = (binCount * binwidth) // 2  # Half range for the histogram
#     # last_start_timestamp = 0 # This is not needed and will reset to 0 each time
#     tagCount = tags.size
#     Ch1Count = 0
#     Ch2Count = 0
    
#     for itag in range(tagCount - 1):
#         if tags[itag]['type'] != TimeTagger.TagType.TimeTag:
#             continue  # Skip non-time tag types
        
#         if tags[itag]['channel'] == start_channel:
#             # Found a start event, look for the next click event
#             for jtag in range(itag + 1, tagCount):
#                 if tags[jtag]['type'] != TimeTagger.TagType.TimeTag:
#                     continue  # Skip non-time tag types
                
#                 if tags[jtag]['channel'] == click_channel:
#                     # Found a click event after the start
#                     diff = tags[jtag]['time'] - tags[itag]['time']
                    
#                     if np.abs(diff) <= magTime:
#                         index = ((diff + magTime) // binwidth)
#                         if 0 <= index < binCount:
#                             data[index] += 1
#                             Ch2Count +=1 
#                     break  # Move to the next start tag
            
#             Ch1Count+=1
    
#     return last_start_timestamp, Ch1Count, Ch2Count





@staticmethod
@numba.jit(nopython=True, nogil=True)
def fast_process_Correlations(tags, data, click_channel, start_channel, binCount, binwidth):
    """
    Correlation function without uint64 issues, simplified logic.
    """
    magTime = binCount * binwidth // 2
    Ch1Count = 0
    Ch2Count = 0

    start_idx = 0
    click_idx = 0
    tagCount = len(tags)

    while start_idx < tagCount and click_idx < tagCount:
        # Find the next start event
        while start_idx < tagCount and (
            tags[start_idx]['type'] != TimeTagger.TagType.TimeTag or
            tags[start_idx]['channel'] != start_channel
        ):
            start_idx += 1

        # Find the next click event
        while click_idx < tagCount and (
            tags[click_idx]['type'] != TimeTagger.TagType.TimeTag or
            tags[click_idx]['channel'] != click_channel
        ):
            click_idx += 1

        # Stop if no more relevant tags
        if start_idx >= tagCount or click_idx >= tagCount:
            break

        # Extract timestamps
        start_time = tags[start_idx]['time']
        click_time = tags[click_idx]['time']

        # Compute the time difference
        diff = click_time - start_time

        # Bin the time difference
        if -magTime <= diff <= magTime:
            index = int((diff + magTime) / binwidth)
            if 0 <= index < binCount:
                data[index] += 1

        # Advance only one index depending on the difference
        if diff >= 0:
            start_idx += 1
        else:
            click_idx += 1

        # Update counts for debugging
        # Ch1Count += 1
        # Ch2Count += 1

    return Ch1Count, Ch2Count


# @staticmethod
# @numba.jit(nopython=True, nogil=True)
# def fast_process_Correlations(tags, data, click_channel, start_channel, binCount, binwidth,last_start_timestamp):
#     """
#     Optimized correlation measurement with no extra arrays.
#     """
#     magTime = binCount * binwidth // 2  # Half range for the histogram
#     Ch1Count = 0
#     Ch2Count = 0

#     # Start processing using two moving pointers
#     start_idx = 0
#     click_idx = 0
#     tagCount = len(tags)

#     while start_idx < tagCount and click_idx < tagCount:
#         # Find the next relevant start tag
#         while start_idx < tagCount and (
#             tags[start_idx]['type'] != TimeTagger.TagType.TimeTag or
#             tags[start_idx]['channel'] != start_channel
#         ):
#             start_idx += 1

#         # Find the next relevant click tag
#         while click_idx < tagCount and (
#             tags[click_idx]['type'] != TimeTagger.TagType.TimeTag or
#             tags[click_idx]['channel'] != click_channel
#         ):
#             click_idx += 1

#         # Stop if no more relevant tags
#         if start_idx >= tagCount or click_idx >= tagCount:
#             break

#         # Extract timestamps
#         start_time = tags[start_idx]['time']
#         click_time = tags[click_idx]['time']

#         # Compute time difference
#         diff = click_time - start_time

#         # Bin the difference if within range
#         if abs(diff) < (magTime + binwidth / 2):
#             index = (diff + magTime) // binwidth
#             if 0 <= index < binCount:
#                 data[index] += 1

#             # Advance the appropriate pointer
#             if diff >= 0:
#                 start_idx += 1
#             else:
#                 click_idx += 1
#         else:
#             # Remove outdated events
#             if diff > magTime:
#                 start_idx += 1
#             else:
#                 click_idx += 1

#         # Update counts
#         Ch1Count += 1
#         Ch2Count += 1

#     return last_start_timestamp,Ch1Count, Ch2Count

# @staticmethod
# @numba.jit(nopython=True, nogil=True)
# def fast_process_Correlations(
#         tags,
#         data,
#         click_channel,
#         start_channel,
#         binCount,
#         binwidth,
#         last_start_timestamp):
#     """
#     A precompiled version of the histogram algorithm for better performance
#     """
#     magTime = (binCount ) * binwidth // 2  # Half range for the histogram
#     last_start_timestamp = 0
#     tagCount = tags.size
#     Ch1Count = 0
#     Ch2Count = 0
#     # Really need to look at the diagram for the correlation example to understand how to 
#     # code this one. 
#     for itag in range(tagCount-1):
#         # Check for valid TimeTag type
#         if tags[itag]['type'] == TimeTagger.TagType.TimeTag:
#             NextChanneltagNotFonud=True
#             idx=1
#             while NextChanneltagNotFonud:
#                 if(tags[itag]['channel'] != tags[itag+idx]['channel']):
#                     NextChanneltagNotFonud = False
#                     # diff = (tags[itag]['time'] - tags[itag+idx]['time'])
#                     # diff = (tags[itag+idx]['time'] - tags[itag]['time'])
                    
#                     if (tags[itag]['channel'] == click_channel ):
#                             # diff = (tags[itag]['time'] - tags[itag+idx]['time'])
#                             diff = (tags[itag+idx]['time'] - tags[itag]['time'])
                            
#                     elif(tags[itag]['channel'] == start_channel):
#                             # diff = (tags[itag+idx]['time'] - tags[itag]['time'])
#                             diff = (tags[itag]['time'] - tags[itag+idx]['time'])
                        
#                             # diff = -(tags[itag]['time'] - tags[itag+idx]['time'])
#                     else:
#                         idx+=1
#                 else:
#                     idx+=1
#                     if (tags[itag+idx]['channel']==click_channel):
#                         Ch2Count += 1
#                     if (tags[itag+idx]['channel']==start_channel):
#                         Ch1Count += 1

#             # Check if diff is within valid range
#             if np.abs(diff) <= magTime:
#                 index = ((((diff) + magTime)) // binwidth )# Map to bin index
#                 # Print index for debugging
#                 # print("Index:", index)

#                 if 0 <= index < binCount:
#                     data[index] += 1  # Increment histogram count
#                     # Ch2Count += 1


#     return last_start_timestamp, Ch1Count, Ch2Count

@staticmethod
@numba.jit(nopython=True, nogil=True)
def fast_process_1Dhistogram(
            tags,
            data,
            click_channel1,
            click_channel2,
            click_channel3,
            start_channel,
            binwidth,
            last_start_timestamp):
        """
        A precompiled version of the histogram algorithm for better performance
        nopython=True: Only a subset of the python syntax is supported.
                       Avoid everything but primitives and numpy arrays.
                       All slow operation will yield an exception
        nogil=True:    This method will release the global interpreter lock. So
                       this method can run in parallel with other python code
        """
        for tag in tags:
            # tag.type can be: 0 - TimeTag, 1- Error, 2 - OverflowBegin, 3 -
            # OverflowEnd, 4 - MissedEvents (you can use the TimeTagger.TagType IntEnum)
            if tag['type'] != TimeTagger.TagType.TimeTag:
                # tag is not a TimeTag, so we are in an error state, e.g. overflow
                last_start_timestamp = 0
            elif tag['channel'] == click_channel1 and last_start_timestamp != 0:
                # valid event
                index = (tag['time'] - last_start_timestamp) // binwidth
                if index < data.shape[0]:
                    data[index] += 1
            if tag['channel'] == start_channel:
                last_start_timestamp = tag['time']
        return last_start_timestamp




@numba.jit(nopython=True, nogil=True)
def fast_process(tags, counter, chan_offset, g_bitmap, g_mask, ring_buf, ring_head, ring_tail, coincidenceWindow):
    
    ring_size = ring_buf.size
    n_groups = g_bitmap.size

    for tag in tags:
        if tag["type"] != 0:  
            # Skip any tags that are not normal time tag.
            continue

        if tag['channel'] < -18 or tag['channel'] > 18:
            # Ignore non-physical channels
            continue

        ring_buf[ring_head] = tag

        # 1. Check if we have complete window and then evaluate coincidences within
        if ring_buf[ring_head]['time'] - ring_buf[ring_tail]['time'] > coincidenceWindow:
            # 1.1 Make channel bitmap within the complete window
            window_bitmap = 0
            # Number of elements in the ring
            ring_used = (ring_head-ring_tail) & (ring_size-1)
            for i in range(ring_used):
                buf_pos = (ring_tail + i) % ring_size
                chan = ring_buf[buf_pos]['channel']
                window_bitmap = window_bitmap | (1<< (chan + chan_offset))

            # 1.2 Compare window bitmap with the group bitmap and increment counter.
            for group_i in range(n_groups):
                if (window_bitmap & g_mask[group_i]) == g_bitmap[group_i]:
                    counter[group_i] += 1
            
            # 1.3. Shift the window
            while ring_buf[ring_head]['time'] - ring_buf[ring_tail]['time'] > coincidenceWindow:
                ring_tail = (ring_tail + 1) % ring_size

        # 2. Increment ring buffer head index.
        ring_head = (ring_head + 1) % ring_size

    return ring_head, ring_tail
