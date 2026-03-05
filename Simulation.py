'''
Adapted from @nicseo code 11/20/14

Last Modified: 1/5/2026

@author: cindiewu
'''

import csv
import os
import math
import copy
from types import SimpleNamespace

import pandas

from Schedule import *
from ShiftSchedule import *
from Utilities import *
from DataProcessor import *
from Params import *
from TimePeriod import *


#set directory
#os.chdir("/home/matrix/")
os.chdir("/content/test-epcath/")



######################################################################################################
######################################################################################################
##################################### READING/PROCESSING METHODS #####################################
######################################################################################################
######################################################################################################    

def readShiftData(fileName):
    '''
    '''
    shifts = []
    with open(fileName, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            row = [float(i) for i in row[:numShiftEntries+1]]
            shifts.append(row)
    return shifts

def readProcData(fileName, numEntries):
    '''
    Input: fileName (string name of the file you want to process procedural data from

    Returns: a list of lists, each one being one procedure's information stored as floats
    '''
    procedures = []
    with open(fileName, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            row = [float(i) for i in row[:numEntries+1]]
            procedures.append(row)
    return procedures

def cleanProcTimes(allProcs, iProcTime, turnover, totalTimeRoom):
    '''
    Input: allProcs (list of all procedures as processed from csv)
    
    Returns: list of all procedures modified so that no procedure is
                of length zero, and procedures of length greater than
                totalTimeRoom are truncated
    '''
    newProcs = allProcs[:]

    for i in range (len(newProcs)):
        procTime = newProcs[i][iProcTime]
        procTime += turnover
        if procTime > totalTimeRoom:
            procTime = totalTimeRoom
        newProcs[i][iProcTime] = procTime
    return newProcs

def saveSchedulingResults(timePeriod,workbook,readable):

    out = open(workbook,'wb')
    writer = csv.writer(out)

    days = timePeriod.numDays
    roomDays = timePeriod.bins[0]
    roomShifts = timePeriod.bins[3]
    allTimes = roomDays[(0,0.0,0)].timeSlots.keys()
    times = [x for x in allTimes if isLater(x,(6,45))]
    times.sort(key=lambda x: (x[0],x[1]))
    
    # initialize column names
    maxShifts = getMaxShifts(timePeriod)
    columns = ['Day','Lab','Room']
    if readable:
        columns.append('Shifts')
    else:
        columns = ['Day','Lab','Room']
        for i in range(1,maxShifts+1):
            shift = 'Shift '+str(i)
            columns += [shift+' Start', shift+' ProviderKey', shift+' Type', shift+' Original Lab', shift+' Original Start', shift+' Original AM/PM']
    for time in times:
        columns.append(time)
    writer.writerow(columns)

    # write row data: each row represents a room day schedule
    data = []
    ###################################################################################################################
    def generateRowData(day,numRooms,labName,labID):
        for room in range(numRooms):
            dayInfo = [str(d),labName,room]
            # extract shift info
            shifts = roomShifts[day-1].rooms[(labID,room)]
            if readable:
                dayInfo.append(["Start: "+str(x[3])+", Prov: "+str(int(x[0]))+", Shift: "+str(x[1]) for x in shifts])
            else:
                for i in range(maxShifts):
                    try:
                        shift = shifts[i]
                        dayInfo += [minutesFromTimeFormatted(shift[3])/60.0,int(shift[0]),shift[1],shift[4],'-','-']
                    except IndexError:
                        dayInfo += ['','','','','','']
            # extract schedule info
            s = roomDays[(day-1,labID,room)]
            seen = set()
            for t in times:
                procs = s.timeSlots[t]
                if len(procs) != 0:
                    proc = s.timeSlots[t][0]
                    procID = proc[ID]
                    if procID not in seen:
                        seen.add(procID)
                        dayInfo.append("Proc "+str(proc[ID])+": "+
                                   str(int(proc[iProcTime]))+
                                   " min, Prov: "+str(int(proc[iProvider]))) if readable else dayInfo.append(proc[ID])
                    else:
                        dayInfo.append(proc[ID])
            data.append(dayInfo)
    ###################################################################################################################
    for d in range(1,days+1):
        # Cath room schedules
        generateRowData(d,numCathRooms,'Cath',cathID)
        # EP room schedules
        generateRowData(d,numEPRooms,'EP',epID)
    writer.writerows(data)
    
    
def getMaxShifts(timePeriod):
    allShifts = timePeriod.bins[3]
    days = timePeriod.numDays
    maximum = 0
    for d in range(0,days):
        for cath in range(numCathRooms):
            shifts = allShifts[d].rooms[(cathID,cath)]
            if len(shifts) > maximum:
                maximum = len(shifts)
        for ep in range(numEPRooms):
            shifts = allShifts[d].rooms[(epID,ep)]
            if len(shifts) > maximum:
                maximum = len(shifts)
    return maximum
    

def saveHoldingBayResults(timePeriod,workbook, params):

    #out = open(workbook,'wb') #orig
    out = open(workbook,'w', encoding='utf-8') #Cindie Edit/Check
    writer = csv.writer(out)

    multiple = 60.0/params.resolution
    times = [i for i in range(int(params.HBCloseTime*multiple))]
    columns = ["Day"]
    for time in times:
        #hours = math.floor(time)
        #minutes = (time - math.floor(time))*60
        #columns.append(str(int(hours))+":"+str(int(minutes)))
        hours = math.floor(time/multiple)
        minutes = (time - hours*multiple)*params.resolution
        columns.append(str(int(hours))+":"+str(format(int(minutes), '02d'))) #orig
        #columns.append((str(int(hours))+":"+str(format(int(minutes), '02d'))).encode(encoding='UTF-8'))
    writer.writerow(columns)
    
    data = []
    for d in range(timePeriod.numDays):
        holdingBays = timePeriod.bins[2]
        day = [holdingBays[(d,time)] for time in times]
        day.insert(0,str(d+1))
        data.append(day)

    writer.writerows(data)

def printOutputStatistics(timePeriod, procedures, params):
    print ("\n...Done!")
    
    print ("\n*********PARAMETERS*********")
    print ("Procedure Sorting Priority: " + str(params.wSortPriority.value))
    print ("\tsortProcs: " + str(params.sortProcs))
    print ("\tsortIndex: " + str(params.sortIndex))
    print ("\tsortDescend: " + str(params.sortDescend))
    print ("Scenario: " + str(params.wFiles.value))
    print ("\tprocDataFile: " + str(params.procDataFile))
    print ("\tshiftDataFile: " + str(params.shiftDataFile))
    print ("Mean HB Cleaning Time (hours): " + str(params.desiredPreCleanMean))
    print ("Resolution (minutes): " + str(params.resolution))
    
    print ("Cath rooms: "+str(params.numCathRooms))
    print ("EP rooms: "+str(params.numEPRooms))
##    print "Cath rooms used for non-emergencies: "+str(numRestrictedCath)
##    print "EP rooms used for non-emergencies: "+str(numRestrictedEP)
##    print "Crossover policy: "+str(crossoverType)
##    print "Pair weeks for scheduling? "+str(weekPairs)
##    print "Pair days for scheduling? "+str(dayPairs)
##    print "Schedule all procedures on same day as historically? "+str(sameDaysOnly)
##    print "Placement priority: "+str(priority)
    print ("Post procedure determination random? "+str(params.postProcRandom))
    print ("Pre procedure time converted to hours? "+str(params.ConvertPreProcToHours))
    print ("Change provider days? "+str(params.ChangeProviderDays))
    print ("Swap provider days? "+str(params.SwapProviderDays))
    print ("Pre procedure cap implemented? "+str(params.CapHBPreProc))

    print ("\n*********PROCEDURE DATA*********")
    print ("Total procedures: "+str(timePeriod.numTotalProcs))
    print ("Same days: "+str(timePeriod.numSameDays))
    print ("Same weeks: "+str(timePeriod.numSameWeeks))
    print ("Emergencies: "+str(timePeriod.numEmergencies))
    minutes = timePeriod.getProcsByMinuteVolume(procedures, params)
    for x in range(6):
        minutes[x] = round(minutes[x],2)
    print ("\tBREAKDOWN BY MINUTES")
    print ("\tSame week flex: "+str(minutes[4])+" minutes")
    print ("\tSame week inflex: "+str(minutes[5])+" minutes")
    print ("\tSame day flex: "+str(minutes[2])+" minutes")
    print ("\tSame day inflex: "+str(minutes[3])+" minutes")
    print ("\tEmergency flex: "+str(minutes[0])+" minutes")
    print ("\tEmergency inflex: "+str(minutes[1])+" minutes")

    
    print ("\n*********OVERFLOW STATS*********")
    print ("Total of "+str(timePeriod.procsPlaced)+" procedures placed")
    print ("Total procedures scheduled past closing time: "+str(timePeriod.overflowCath+timePeriod.overflowEP))
    print ("\tCath overflow: "+str(timePeriod.overflowCath))
    print ("\tEP overflow: "+str(timePeriod.overflowEP))
    print ("\t---")
    print ("\tQuarter day shift overflows: "+str(timePeriod.overflowQuarter))
    print ("\tHalf day shift overflows: "+str(timePeriod.overflowHalf))
    print ("\tFull day shift overflows: "+str(timePeriod.overflowFull))
    print ("Same day/emergencies overflow during days (0 index): "+str(sorted(timePeriod.overflowDays)))
    minutesPlaced = timePeriod.getProcsByMinuteVolume(timePeriod.procsPlacedData, params)
##    print ("\tBREAKDOWN BY MINUTES PLACED")
##    modifiedMinutes = [0]*6
##    for x in range(6):
##        minutesPlaced[x] = round(minutesPlaced[x],2)
##        modifiedMinutes[x] = 100 if minutes[x]==0 else minutes[x]
##    print ("\tSame week flex: "+str(minutesPlaced[4])+" out of "+str(minutes[4])+" minutes placed ("+str(round((minutesPlaced[4]/(modifiedMinutes[4])*100),2))+"%)")
##    print ("\tSame week inflex: "+str(minutesPlaced[5])+" out of "+str(minutes[5])+" minutes placed ("+str(round((minutesPlaced[5]/(modifiedMinutes[5])*100),2))+"%)")
##    print ("\tSame day flex: "+str(minutesPlaced[2])+" out of "+str(minutes[2])+" minutes placed ("+str(round((minutesPlaced[2]/(modifiedMinutes[2])*100),2))+"%)")
##    print ("\tSame day inflex: "+str(minutesPlaced[3])+" out of "+str(minutes[3])+" minutes placed ("+str(round((minutesPlaced[3]/(modifiedMinutes[3])*100),2))+"%)")
##    print ("\tEmergency flex: "+str(minutesPlaced[0])+" out of "+str(minutes[0])+" minutes placed ("+str(round((minutesPlaced[0]/(modifiedMinutes[0])*100),2))+"%)")
##    print ("\tEmergency inflex: "+str(minutesPlaced[1])+" out of "+str(minutes[1])+" minutes placed ("+str(round((minutesPlaced[1]/(modifiedMinutes[1])*100),2))+"%)"+"\n")
    
    print ("\n*********CROSSOVER STATS*********")
    print ("Total number of crossover procedures: "+str(timePeriod.crossOverProcs))
    print ("Total number of Cath procedures in EP: "+str(timePeriod.cathToEP))
    print ("Total number of EP procedures in Cath: "+str(timePeriod.epToCath))
    
    print ("\n*********UTILIZATION STATS*********")
    cath, ep, avgUtilDay, avgUtilWeek, util = timePeriod.getUtilizationStatistics(params)
    print ("Average utilization in Cath over time period: "+str(cath))
    print ("Average utilization in EP over time period: "+str(ep))
    print ("\nType: 'avgUtilDay[_day_]' to view average utilization in Cath and EP on a given day (indexed from 0)")
    print ("Type: 'avgUtilWeek[_week_]' to view average utilization in Cath and EP during a given week (indexed from 0)")
    print ("Type: 'printSchedule(_day_,_labID_,_room_)' to see a specific room day schedule (indexed from 0)")

    return avgUtilDay,avgUtilWeek

def printSchedule(day,lab,room):
    rooms = timePeriod.bins[0]
    print ("Day: "+str(day)+" Lab: "+str(lab)+" Room: "+str(room))
    if lab != middleID:
        shifts = timePeriod.bins[3]
        daysShifts = shifts[day].rooms[(lab,room)]
        print ("Day's Shifts: "+str(daysShifts))
    s = rooms[(day,lab,room)]
    times = s.timeSlots.keys()
    times.sort(key=lambda x:(x[0],x[1]))
    seen = set()
    for t in times:
        if t[1]%30 == 0:
            procs = s.timeSlots[t]
            if len(procs) != 0:
                procID = s.timeSlots[t][0][10]
                if procID not in seen:
                    seen.add(procID)
                    print (str(t)+": "+str(s.timeSlots[t][0]))
                else:
                    print (str(t)+": *")                     
            else:
                print (str(t)+": ")



##############################################################################
############# RUNNING OF THE SCRIPT: not necessary to modify #################
##############################################################################
    
def RunSimulation(myP):

    ###### STEP 0: READ DATA / CREATE MODEL ######

    # read/process input data
    shifts = readProcData(myP.shiftDataFile, myP.numEntries)
    procedures = readProcData(myP.procDataFile, myP.numEntries)
    procedures = cleanProcTimes(procedures, myP.iProcTime, myP.turnover, myP.totalTimeRoom)

    # create time period model
    #timePeriod = TimePeriod(resolution,daysInPeriod,numCathRooms,numEPRooms,numMiddleRooms,numRestrictedCath,numRestrictedEP,labStartTime, labEndTime, secondShiftStart, HBCloseTime, roomValueChanges)

    timePeriod = TimePeriod(myP)
    
    ###### STEP 1: SCHEDULE SHIFTS ######
    timePeriod.packShifts(shifts, myP)  

    ###### STEP 2: PACK PROCEDURES INTO SHIFTS ######
    timePeriod.packProcedures(procedures, myP)

    ###### STEP 3: CALCULATE OUTPUT STATISTICS ######
    avgUtilDay, avgUtilWeek = printOutputStatistics(timePeriod, procedures, myP)

    ###### STEP 4: SAVE RESULTS ######
    saveHoldingBayResults(timePeriod,myP.holdingBayWorkbook, myP)
#    saveSchedulingResults(timePeriod,readWorkbook,readable=True)
#    saveSchedulingResults(timePeriod,processWorkbook,readable=False)

    ###### STEP 5: PROCESS DATA FILE FOR VISUALIZATION #####
    formatDataFileForVisualization(myP.resolution, myP.holdingBayWorkbook)    
    
def Start():
    
    print("Starting...")

    #create Params instance
    p = Params()

    #set random seed
    random.seed(30)

    # call Widgets to set Params using GUI
    p.setParams()
      
