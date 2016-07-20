#!/usr/bin/env python
'''
Module to perform various time operations.

Documentation convention from https://github.com/numpy/numpy/blob/master/doc/HOWTO_DOCUMENT.rst.txt

07.07.2016
Loris Foresti
'''

from __future__ import division
from __future__ import print_function

import datetime
import numpy as np
import time

def timestring2datetime(timestring):
    '''
    Function to convert a time stamp string YYYYmmDDHHMMSS to a datetime object.
    
    Parameters
    ----------
    timestring : str
        Time string YYYYmmDDHHMMSS
    
    Returns
    -------
    timeDate: datetime
        Datetime object
    '''
    #timeDate = datetime.datetime.strptime(timestring,'%Y%m%d%H%M%S')
    timeDate = datetime.datetime(int(timestring[0:4]), int(timestring[4:6]), int(timestring[6:8]), int(timestring[8:10]),int(timestring[10:12]))
    return(timeDate)
    
def datetime2timestring(timeDate):
    '''
    Function to convert datetime object to a time stamp string YYYYmmDDHHMMSS.
    
    Parameters
    ----------
    timeDate : datetime
        Datetime object
    
    Returns
    -------
    timeString: str
        Time string YYYYmmDDHHMMSS
    '''
    timeString = timeDate.strftime("%Y%m%d%H%M%S")
    return(timeString)
    
def datetime2juliantimestring(timeDate):
    '''
    Function to convert datetime object to a Julian time stamp string YYYYJJJHHMMSS.
    
    Parameters
    ----------
    timeDate : datetime
        Datetime object
    
    Returns
    -------
    timeString: str
        Time string YYYYJJJHHMMSS
    '''
    year, yearStr, julianDay, julianDayStr = parse_datetime(timeDate)
    hour = timeDate.hour
    minute = timeDate.minute
    hourminStr = ('%02i' % hour) + ('%02i' % minute)
    
    timeString = yearStr + julianDayStr + hourminStr
    return(timeString)
 
def get_julianday(timeDate):
    '''
    Get Julian day from datetime object.
    
    Parameters
    ----------
    timeDate : datetime
        Datetime object
    
    Returns
    -------
    julianDay: int
        Julian day
    '''
    julianDay = timeDate.timetuple().tm_yday
    return(julianDay)
    
def parse_datetime(timeDate):
    '''
    Function to parse a datetime object and return the year and Julian day in integer and string formats.
    
    Parameters
    ----------
    timeDate : datetime
        Datetime object
    
    Returns
    -------
    year: int
        Year
    yearStr: str
        Year string in YY
    julianDay: int
        Julian day
    julianDayStr: str 
        Julian day string JJJ
    '''
    year = timeDate.year
    yearStr =  str(year)[2:4]
    julianDay = get_julianday(timeDate)
    julianDayStr = '%03i' % julianDay
    yearJulianStr = yearStr + julianDayStr
    return(year, yearStr, julianDay, julianDayStr)
    
def timestring_array2datetime_array(arrayTimeStampsStr):
    '''
    Function to convert a list array of time strings YYYYmmDDHHMMSS
    into a list of datetime objects
    
    Parameters
    ----------
    arrayTimeStampsStr : list(str)
        List of time strings YYYYmmDDHHMMSS
    
    Returns
    -------
    arrayTimeStampsDt: list(datetime)
        List of datetime objects
    '''
    
    timeStamps = np.array(arrayTimeStampsStr,dtype=int)
    timeStampsStr = np.array(list(map(str,timeStamps)))
    
    arrayTimeStampsDt = []
    for t in range(0,len(arrayTimeStampsStr)):
        timeDate = timestring2datetime(str(timeStampsStr[t]))
        arrayTimeStampsDt.append(timeDate)
    
    return(arrayTimeStampsDt)
    
def get_HHmm_str(hour, minute):
    '''
    Function to concatenate hours and minutes into a 4-digit string.
    
    Parameters
    ----------
    hour : int
    minute: int
    
    Returns
    -------
    hourminStr: str
        4-digit hour and minute string (HHMM)
    '''
    hourminStr = ('%02i' % hour) + ('%02i' % minute)
    return(hourminStr)

def get_subdir(year, julianDay):
    '''
    Function to create the subdirectory string from the year and Julian day.
    
    Parameters
    ----------
    year : int
    julianDay: int
    
    Returns
    -------
    subDir: str
        Sub-directory string YYYY/YYJJJ/
    '''
    yearStr = str(year)[2:4]
    julianDayStr = '%03i' % julianDay
    subDir = str(year) + '/' + yearStr + julianDayStr + '/'
    return(subDir)
    
def datetime2absolutetime(timeDate):
    '''
    Function to convert a datetime object into an epoch (absolute time in seconds since 01/01/1970).
    
    Parameters
    ----------
    timeDate : datetime
    
    Returns
    -------
    absTime: int
        Number of seconds since 01/01/1970
    '''
    absTime = int((timeDate-datetime.datetime(1970,1,1)).total_seconds())
    
    return(absTime)
    