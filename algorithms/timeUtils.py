class SpaceTime:

    @staticmethod
    def getLST(LR_Longitude, LR_GST):
        LR_Longitude_hours = LR_Longitude/15
        LR_LST = (LR_GST+LR_Longitude_hours)%24
        if LR_LST < 0:
            LR_LST = LR_LST + 24
        return LR_LST

    @staticmethod
    def getGST(LR_julianDate, LI_hour, LI_minute, LR_second):
        
        # Finding Greenwich siderial time (GST)
        LR_S = LR_julianDate - 2451545.0
        LR_T = LR_S / 36525.0
        LR_T0 = 6.697374558 + (2400.051336*LR_T) + (0.000025862*LR_T**2)
        LR_T0 = LR_T0%24

        # Finding the UT in decimal hours
        LR_UTdecimalHoursSeconds = LR_second/60
        LR_UTdecimalHoursMinutes = (LR_UTdecimalHoursSeconds + LI_minute)/60
        LR_UTdecimalHours = LR_UTdecimalHoursMinutes + LI_hour

        LR_UTdecimalHours = LR_UTdecimalHours*1.002737909

        LR_GST = (LR_T0 + LR_UTdecimalHours)%24

        return LR_GST

    @staticmethod
    def getJD(LI_yearA, LI_monthA, LI_day):

        # This gets the Julian date
        LI_yearB = 0
        LI_monthB = 0
        if LI_monthA == 1 or LI_monthA == 2:
            LI_yearB = LI_yearA - 1
            LI_monthB = LI_monthA + 12
        else:
            LI_yearB = LI_yearA
            LI_monthB = LI_monthA

        if [LI_yearA, LI_monthA, LI_day] > [1582, 10, 15]: # October 15th 1582 was the day the gregorian calander was implemented
            LI_A = int(LI_yearB/100)
            LI_B = 2 - LI_A + int(LI_A/4)
        else:
            LI_B = 0

        if LI_yearB < 0:
            LI_C = int((365.25*LI_yearB) - 0.75)
        else:
            LI_C = int(365.25*LI_yearB)

        LI_D = int(30.6001*(LI_monthB+1))

        LR_julianDate = LI_B + LI_C + LI_D + LI_day + 1720994.5

        return LR_julianDate