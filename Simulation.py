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

def readShiftData(fileName, numEntries):
    '''
    Reads shift data from csv.

    Input:
        fileName: path to shift csv
        numEntries: last column index to read (inclusive style used in old code)

    Returns:
        list of shift rows as floats
    '''
    shifts = []
    with open(fileName, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            row = [float(i) for i in row[:numEntries+1]]
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

PRIORITY_OPTIONS = [
    'historical',
    'longest procedures first',
    'shortest procedures first',
    'longest recovery time first',
    'shortest recovery time first'
]


def cloneParams(baseParams):
    '''
    Make a lightweight copy of Params without copying widget objects.
    '''
    p = SimpleNamespace()
    skip_keys = {
        'wLbl1', 'wLbl2', 'wLblOptional',
        'wSortPriority', 'wFiles', 'wMeanHBCleanTime', 'wRes', 'wNumCathRooms',
        'button', 'output', 'wAllWidgets'
    }

    for k, v in baseParams.__dict__.items():
        if k in skip_keys:
            continue
        try:
            setattr(p, k, copy.deepcopy(v))
        except Exception:
            setattr(p, k, v)
    return p


def applyPriorityRule(params, priorityName):
    '''
    Set sorting parameters without needing the GUI widgets.
    '''
    if priorityName == 'longest procedures first':
        params.sortProcs = True
        params.sortIndex = params.iProcTime
        params.sortDescend = True
    elif priorityName == 'shortest procedures first':
        params.sortProcs = True
        params.sortIndex = params.iProcTime
        params.sortDescend = False
    elif priorityName == 'longest recovery time first':
        params.sortProcs = True
        params.sortIndex = params.iPostTime
        params.sortDescend = True
    elif priorityName == 'shortest recovery time first':
        params.sortProcs = True
        params.sortIndex = params.iPostTime
        params.sortDescend = False
    else:  # historical
        params.sortProcs = True
        params.sortIndex = params.iHistoricalOrder
        params.sortDescend = False


def percentile(values, pct):
    '''
    Simple percentile helper.
    pct should be in [0, 100].
    '''
    if len(values) == 0:
        return 0
    vals = sorted(values)
    rank = int(math.ceil((pct / 100.0) * len(vals))) - 1
    rank = max(0, min(rank, len(vals) - 1))
    return vals[rank]


def hoursToHHMM(hoursFloat):
    '''
    Convert decimal hours to HH:MM string.
    Example: 18.5 -> "18:30"
    '''
    totalMinutes = int(round(hoursFloat * 60))
    hh = totalMinutes // 60
    mm = totalMinutes % 60
    return str(hh) + ":" + format(mm, '02d')


def getHoldingBayOccupancyMatrix(timePeriod, params):
    '''
    Returns a list of daily occupancy lists.
    Each inner list is occupancy across all holding-bay time buckets for one day.
    '''
    holdingBays = timePeriod.bins[2]
    numSlots = int(params.HBCloseTime * (60.0 / params.resolution))

    allDays = []
    for d in range(timePeriod.numDays):
        occ = [holdingBays[(d, 1.0 * i)] for i in range(numSlots)]
        allDays.append(occ)
    return allDays


def analyzeHoldingBayDemand(timePeriod, params, bayPercentile=95, closePercentile=95):
    '''
    Analyze holding-bay demand profile from simulated occupancy.

    Returns metrics useful for:
    - recommended number of bays
    - recommended close time
    '''
    allDays = getHoldingBayOccupancyMatrix(timePeriod, params)

    dailyPeaks = []
    dailyLastOccupiedHours = []

    for occ in allDays:
        peak = max(occ) if len(occ) > 0 else 0
        dailyPeaks.append(peak)

        occupiedIdx = [i for i, x in enumerate(occ) if x > 0]
        if len(occupiedIdx) == 0:
            dailyLastOccupiedHours.append(0.0)
        else:
            lastIdx = occupiedIdx[-1]
            lastHour = (lastIdx * params.resolution) / 60.0
            dailyLastOccupiedHours.append(lastHour)

    overallPeak = max(dailyPeaks) if len(dailyPeaks) > 0 else 0
    peakP90 = percentile(dailyPeaks, 90)
    peakP95 = percentile(dailyPeaks, bayPercentile)

    lastOccP90 = percentile(dailyLastOccupiedHours, 90)
    lastOccP95 = percentile(dailyLastOccupiedHours, closePercentile)
    overallLast = max(dailyLastOccupiedHours) if len(dailyLastOccupiedHours) > 0 else 0.0

    return {
        "daily_peak_bays": dailyPeaks,
        "daily_last_occupied_hours": dailyLastOccupiedHours,
        "overall_peak_bays": overallPeak,
        "peak_bays_p90": peakP90,
        "peak_bays_p95": peakP95,
        "recommended_bays_p95": int(math.ceil(peakP95)),
        "last_occupied_p90_hours": lastOccP90,
        "last_occupied_p95_hours": lastOccP95,
        "overall_last_occupied_hours": overallLast,
        "recommended_close_p95": hoursToHHMM(lastOccP95),
    }


def evaluateCloseTimeCandidates(timePeriod, params, candidateHours=(17, 18, 19, 20, 21, 22, 23, 24)):
    '''
    Evaluate how much holding-bay demand remains after candidate close times.

    IMPORTANT:
    This measures occupancy remaining after close as a proxy.
    It does NOT yet count exact patient admissions to hospital after close,
    because the current model does not explicitly store patient-level recovery-end events.
    '''
    allDays = getHoldingBayOccupancyMatrix(timePeriod, params)
    slotPerHour = 60.0 / params.resolution

    results = []

    for closeHour in candidateHours:
        closeIdx = int(closeHour * slotPerHour)

        totalSlotsAfterClose = 0
        totalBayHoursAfterClose = 0.0
        daysWithDemandAfterClose = 0

        for occ in allDays:
            after = occ[closeIdx:]
            afterSum = sum(after)
            totalSlotsAfterClose += afterSum

            bayHours = afterSum * (params.resolution / 60.0)
            totalBayHoursAfterClose += bayHours

            if any(x > 0 for x in after):
                daysWithDemandAfterClose += 1

        results.append({
            "close_hour": closeHour,
            "close_time": hoursToHHMM(closeHour),
            "days_with_any_demand_after_close": daysWithDemandAfterClose,
            "total_bay_hours_after_close": totalBayHoursAfterClose,
            "average_bay_hours_after_close_per_day": totalBayHoursAfterClose / float(timePeriod.numDays)
        })

    return results


def buildScenarioSummary(timePeriod, procedures, params, priorityName="unknown"):
    '''
    Collect all metrics needed for planning recommendations.
    '''
    cathUtil, epUtil, avgUtilDay, avgUtilWeek, utilByRoom = timePeriod.getUtilizationStatistics(params)
    hb = analyzeHoldingBayDemand(timePeriod, params)
    closeEval = evaluateCloseTimeCandidates(timePeriod, params)

    summary = {
        "priority_rule": priorityName,
        "total_procs": timePeriod.numTotalProcs,
        "procs_placed": timePeriod.procsPlaced,
        "overflow_total": timePeriod.overflowCath + timePeriod.overflowEP + timePeriod.overflowMiddle,
        "overflow_cath": timePeriod.overflowCath,
        "overflow_ep": timePeriod.overflowEP,
        "overflow_middle": timePeriod.overflowMiddle,
        "crossover_total": timePeriod.crossOverProcs,
        "cath_utilization_avg": cathUtil,
        "ep_utilization_avg": epUtil,
        "mean_room_utilization": (cathUtil + epUtil) / 2.0,
        "holding_bay": hb,
        "close_time_eval": closeEval,
        "avgUtilDay": avgUtilDay,
        "avgUtilWeek": avgUtilWeek,
        "utilByRoom": utilByRoom,
        "timePeriod": timePeriod
    }
    return summary


def printRecommendationReport(summary):
    '''
    Print a concise recommendation report for one scenario.
    '''
    hb = summary["holding_bay"]

    print("\n*********PLANNING RECOMMENDATIONS*********")
    print("Scheduling priority rule tested: " + str(summary["priority_rule"]))
    print("Recommended holding bays to build (95th percentile daily peak): " + str(hb["recommended_bays_p95"]))
    print("Conservative worst-case peak bays observed: " + str(hb["overall_peak_bays"]))
    print("Recommended holding bay close time (95th percentile last occupied time): " + str(hb["recommended_close_p95"]))
    print("Latest observed holding-bay occupancy in simulation: " + str(hoursToHHMM(hb["overall_last_occupied_hours"])))
    print("Average room utilization across Cath and EP: " + str(round(summary["mean_room_utilization"], 4)))
    print("Total procedures placed: " + str(summary["procs_placed"]))
    print("Total procedures scheduled past room closing time: " + str(summary["overflow_total"]))

    print("\nClose-time sensitivity (proxy using bay-hours after close):")
    for row in summary["close_time_eval"]:
        print(
            "  Close @ {0}: days with demand after close = {1}, "
            "total bay-hours after close = {2:.2f}, avg/day = {3:.4f}".format(
                row["close_time"],
                row["days_with_any_demand_after_close"],
                row["total_bay_hours_after_close"],
                row["average_bay_hours_after_close_per_day"]
            )
        )


def comparePriorityRules(baseParams, priorities=None, saveResults=False):
    '''
    Run multiple scheduling policies and rank them.

    Ranking logic:
    1. Fewer overflow procedures
    2. Lower 95th percentile holding-bay peak
    3. Earlier 95th percentile last occupied time
    4. Higher average room utilization
    '''
    if priorities is None:
        priorities = PRIORITY_OPTIONS

    results = []

    for priorityName in priorities:
        p = cloneParams(baseParams)
        applyPriorityRule(p, priorityName)

        timePeriod, summary = RunSimulation(
            p,
            saveOutputs=saveResults,
            printStats=False,
            printRecommendations=False
        )

        summary["priority_rule"] = priorityName
        results.append(summary)

    ranked = sorted(
        results,
        key=lambda x: (
            x["overflow_total"],
            x["holding_bay"]["peak_bays_p95"],
            x["holding_bay"]["last_occupied_p95_hours"],
            -x["mean_room_utilization"]
        )
    )

    best = ranked[0]

    print("\n============================================================")
    print("COMPARISON OF SCHEDULING PRIORITY RULES")
    print("============================================================")
    for r in ranked:
        print(
            "{0}: overflow={1}, bays_p95={2}, close_p95={3}, mean_util={4:.4f}".format(
                r["priority_rule"],
                r["overflow_total"],
                r["holding_bay"]["recommended_bays_p95"],
                r["holding_bay"]["recommended_close_p95"],
                r["mean_room_utilization"]
            )
        )

    print("\nRecommended scheduling priority rule: " + str(best["priority_rule"]))
    print("Recommended holding bays: " + str(best["holding_bay"]["recommended_bays_p95"]))
    print("Recommended holding bay close time: " + str(best["holding_bay"]["recommended_close_p95"]))

    return {
        "best": best,
        "ranked": ranked
    }

def RunSimulation(myP):

    def RunSimulation(myP, saveOutputs=True, printStats=True, printRecommendations=True):

    ###### STEP 0: READ DATA / CREATE MODEL ######

    # read/process input data
    shifts = readShiftData(myP.shiftDataFile, myP.numShiftEntries)
    procedures = readProcData(myP.procDataFile, myP.numEntries)
    procedures = cleanProcTimes(procedures, myP.iProcTime, myP.turnover, myP.totalTimeRoom)

    # create time period model
    timePeriod = TimePeriod(myP)

    ###### STEP 1: SCHEDULE SHIFTS ######
    timePeriod.packShifts(shifts, myP)

    ###### STEP 2: PACK PROCEDURES INTO SHIFTS ######
    timePeriod.packProcedures(procedures, myP)

    ###### STEP 3: CALCULATE OUTPUT STATISTICS ######
    if printStats:
        avgUtilDay, avgUtilWeek = printOutputStatistics(timePeriod, procedures, myP)

    ###### STEP 4: SAVE RESULTS ######
    if saveOutputs:
        saveHoldingBayResults(timePeriod, myP.holdingBayWorkbook, myP)
        formatDataFileForVisualization(myP.resolution, myP.holdingBayWorkbook)

    ###### STEP 5: BUILD SUMMARY ######
    priorityName = "custom"
    try:
        if myP.sortIndex == myP.iHistoricalOrder:
            priorityName = "historical"
        elif myP.sortIndex == myP.iProcTime and myP.sortDescend:
            priorityName = "longest procedures first"
        elif myP.sortIndex == myP.iProcTime and not myP.sortDescend:
            priorityName = "shortest procedures first"
        elif myP.sortIndex == myP.iPostTime and myP.sortDescend:
            priorityName = "longest recovery time first"
        elif myP.sortIndex == myP.iPostTime and not myP.sortDescend:
            priorityName = "shortest recovery time first"
    except Exception:
        pass

    summary = buildScenarioSummary(timePeriod, procedures, myP, priorityName=priorityName)

    if printRecommendations:
        printRecommendationReport(summary)

    return timePeriod, summary
    
def Start():

    print("Starting...")

    # create Params instance
    p = Params()

    # set random seed
    random.seed(30)

    # call Widgets to set Params using GUI
    p.setParams()
      
