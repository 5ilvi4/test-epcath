def timeFormattedFromMinutes(totalMinutes):
    '''
    Given a total number of minutes, returns the number of hours
    and minutes.
    Input: total minutes (integer, not float)
    Returns: a tuple containing the hours and minutes equivalent (hours,minutes)
    '''
    minutes = totalMinutes%60
    hours = (totalMinutes/60)%60
    return (hours,minutes)

def timeFormattedFromHours(totalHours):
    '''
    Given a total number of hours, returns the number of hours
    and minutes. Will round to the nearest minute if needed.
    Input: total hours (integer or float)
    Returns: a tuple containing the hours and minutes equivalent (hours,minutes)
    '''
    totalMinutes = totalHours*60
    return timeFormattedFromMinutes(int(totalMinutes))

def minutesFromTimeFormatted(timeFormatted):
    '''
    Given a formatted time (hours,minutes) tuple, gets the total number of minutes
    this time represents. For example, (8,0) represents 240 minutes.
    '''
    return timeFormatted[0]*60 + timeFormatted[1]
def maxTime(time1,time2):
    '''
    Determines the later time.
    Input: time1 and time2 to compare, in the form (hours,minutes)
    Returns: the later time. If they are the same time, returns it.
    '''
    hour1,min1 = time1
    hour2,min2 = time2

    if hour1 < hour2:
        return time2
    elif hour1 > hour2:
        return time1
    else:
        if min1 < min2:
            return time2
        else:
            return time1

def minTime(time1,time2):
    later = maxTime(time1,time2)
    if later == time1:
        return time2
    else:
        return time1

def isEarlier(time1,time2):
    earlier = minTime(time1,time2)
    if earlier == time1:
        return True
    return False

def isLater(time1,time2):
    return not isEarlier(time1,time2)


def add(time1,time2):
    total1 = minutesFromTimeFormatted(time1)
    total2 = minutesFromTimeFormatted(time2)
    return timeFormattedFromMinutes(total1+total2)
