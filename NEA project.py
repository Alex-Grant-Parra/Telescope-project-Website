from math import sin, cos, tan, asin, acos, atan, atan2, degrees, radians, pi, floor, sqrt


# Explaining values:
# Azimuth = degrees round from north
# Elevation = Degrees from horizon to zenith
# Right ascention = Longitude in the sky
# Declination = Latitude in the sky
  
def convertHorizonToEquatorial(LL_AZ, LL_ELV, LR_latitude, LR_LST):

    

    LR_latitudeRAD = radians(LR_latitude)
    LR_LSTRAD = radians(LR_LST)

    LR_AZ = radians(convertToDecimalDegrees(LL_AZ[0], LL_AZ[1], LL_AZ[2])) # Input Azimith
    LR_ELV = radians(convertToDecimalDegrees(LL_ELV[0], LL_ELV[1], LL_ELV[2])) # Input Elevation

    # Finds the declination
    LR_DEC = asin(sin(LR_ELV)*sin(LR_latitudeRAD) + cos(LR_ELV)*cos(LR_latitudeRAD)*cos(LR_AZ))

    # Finds the hour angle
    LR_H = acos((sin(LR_ELV)-sin(LR_latitudeRAD)*sin(LR_DEC)) / (cos(LR_latitudeRAD)*cos(LR_DEC)))/15

    if degrees(sin(LR_AZ)) > 0:
        LR_H = 360 - LR_H

    # Finds right ascension
    LR_RA = (LR_LSTRAD - LR_H)%radians(24) # Calculates the right ascention
    return(convertToHrMinSec(degrees(LR_RA)), convertToHrMinSec(degrees(LR_DEC))) # Returns a tuple of (Right Ascention, Declination)

def convertEquatorialToHorizon(LL_RA, LL_DEC, LR_latitude, LR_LST):

    def getHourAngle(LL_RA, LR_LST): # Getting hour angle, all units in degrees
        LR_RA = convertToDecimalDegrees(LL_RA[0], LL_RA[1], LL_RA[2])
        LR_H = LR_LST - LR_RA

        if LR_H < 0:
            LR_H = LR_H + 24
        return LR_H
    
    
    LR_latitude_RAD = radians(LR_latitude)
    LR_H_RAD = radians(getHourAngle(LL_RA, LR_LST)*15)
    LR_DEC_RAD = radians(convertToDecimalDegrees(LL_DEC[0], LL_DEC[1], LL_DEC[2]))
    # print(getHourAngle(LL_RA, LR_LST))
    # print(degrees(LR_H_RAD))
    LR_ELV_RAD = asin(sin(LR_DEC_RAD) * sin(LR_latitude_RAD) + cos(LR_DEC_RAD) * cos(LR_latitude_RAD) * cos(LR_H_RAD))

    LR_AZ_RAD = acos((sin(LR_DEC_RAD) - sin(LR_latitude_RAD)*sin(LR_ELV_RAD)) / (cos(LR_latitude_RAD)*cos(LR_ELV_RAD)))

    if sin(LR_H_RAD) > 0:
        LR_AZ_DEG = 360 - degrees(LR_AZ_RAD)
    else:
        LR_AZ_DEG = degrees(LR_AZ_RAD)

    LR_ELV_DEG = degrees(LR_ELV_RAD)

    return(convertToHrMinSec(LR_AZ_DEG), convertToHrMinSec(LR_ELV_DEG)) # Returns a tuple of (Azimuth, Elevation)

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

def getLST(LR_Longitude, LR_GST):
    LR_Longitude_hours = LR_Longitude/15
    LR_LST = (LR_GST+LR_Longitude_hours)%24
    if LR_LST < 0:
        LR_LST = LR_LST + 24
    

    return LR_LST

def convertToHrMinSec(LR_hoursSigned):
    if LR_hoursSigned < 0:
        sign = "negative"
    else:
        sign = "positive"
    LR_hours = abs(LR_hoursSigned)
    LI_hours = int(LR_hours)
    LR_minutes = (LR_hours-int(LR_hours)) * 60
    LR_seconds = (LR_minutes-int(LR_minutes))*60
    LI_minutes = int(LR_minutes)
    result = [LI_hours, LI_minutes, round(LR_seconds, 2)]
    if sign == "negative":
        result[0] = result[0]*-1
    return result

def convertToDecimalDegrees(LI_hour, LI_minute, LR_second):
    return LI_hour + LI_minute / 60 + LR_second / 3600

def findAxialTilt(LR_julianDate):
    LR_JD = LR_julianDate-2451545.0 # The constant is the JD for J2000 1.5
    LR_T = LR_JD/36525.0 # Days in a centuary
    LR_ChangeInTilt = ((46.815*LR_T)+(0.0006*LR_T**2)-(0.00181*LR_T**3))/3600
    LR_Tilt = 23.439292-LR_ChangeInTilt
    return LR_Tilt

GD_SUNDATA = {
    "Ecliptic longitude (epoch)": 279.403303,
    "Ecliptic longitude (perigee)":282.768422,
    "Eccentricity":0.016713,
    "Semi-major axis":1.495985*10**8,
    "Angular diameter": 0.533128
}

def convertEclipticToEquatorial(LL_EclLat, LL_EclLong, LR_AxialTiltDeg):

    # print(f"\nLL_EclLat = {LL_EclLat}")
    # print(f"LL_EclLong = {LL_EclLong}")
    # print(f"LR_LR_AxialTiltN = {LR_AxialTiltDeg}")


    LR_AxialTiltRad = radians(LR_AxialTiltDeg)
    LR_EclLong = radians(convertToDecimalDegrees(LL_EclLong[0], LL_EclLong[1], LL_EclLong[2]))
    LR_EclLat = radians(convertToDecimalDegrees(LL_EclLat[0], LL_EclLat[1], LL_EclLat[2]))

    LR_DEC = asin(sin(LR_EclLat)*cos(LR_AxialTiltRad)+cos(LR_EclLat)*sin(LR_AxialTiltRad)*sin(LR_EclLong))

    LR_Y = sin(LR_EclLong)*cos(LR_AxialTiltRad)-tan(LR_EclLat)*sin(LR_AxialTiltRad)
    LR_X = cos(LR_EclLong)

    LR_RA = atan2(LR_Y, LR_X)

    LR_RA = (degrees(LR_RA)/15)%24
    LR_DEC = degrees(LR_DEC)%360
    # print(f"LR_DEC = {LR_DEC}")

    LR_RA = convertToHrMinSec(LR_RA%24)

    # print(LR_DEC)
    LR_DEC = LR_DEC%360
    if LR_DEC > 180:
        LR_DEC = LR_DEC - 360
    elif LR_DEC > 90:
        LR_DEC = 180 - LR_DEC

    LR_DEC = convertToHrMinSec(LR_DEC)

    return(LR_RA, LR_DEC)

def convertEquatorialToEcliptic(LL_RA, LL_DEC, LR_AxialTilt):
        LR_AxialTiltRad = radians(LR_AxialTilt)

        LR_RA = convertToDecimalDegrees(LL_RA[0], LL_RA[1], LL_RA[2])
        LR_DEC = convertToDecimalDegrees(LL_DEC[0], LL_DEC[1], LL_DEC[2])

        LR_RA = radians(LR_RA*15)
        LR_DEC = radians(LR_DEC)

        LR_EclLat = asin(sin(LR_DEC)*cos(LR_AxialTiltRad) - cos(LR_DEC)*sin(LR_AxialTiltRad)*sin(LR_RA))

        LR_Y = sin(LR_RA)*cos(LR_AxialTiltRad) + tan(LR_DEC)*sin(LR_AxialTiltRad)
        LR_X = cos(LR_RA)

        LR_EclLong = atan2(LR_Y, LR_X)

        LR_EclLong = convertToHrMinSec(degrees(LR_EclLong))
        LR_EclLat = convertToHrMinSec(degrees(LR_EclLat))

        return (LR_EclLat, LR_EclLong)

def solveKepler(LR_M, LR_e):
    if LR_e < 0.1:

        LR_E0 = LR_M
        LR_tolerance = 10**-6
        while True:
            LR_E1 = LR_E0 - (LR_E0 - LR_e*sin(LR_E0)-LR_M) / (1 - LR_e*cos(LR_E0))
            if abs(LR_E0 - LR_E1) < LR_tolerance:
                break
            LR_E0 = LR_E1
        return LR_E1
    else:
        print("Eccentricity of orbit must be between 0 and 0.1")
        return -1
    
def calculateSolarPos(LR_julianDate):
    
    LR_e = GD_SUNDATA.get("Eccentricity")
    LR_daysBetween = LR_julianDate - getJD(1990, 1, 0)
    # print(f"LR_daysBetween = {LR_daysBetween}")
    LR_N = ((360/365.242191)*LR_daysBetween)%360
    # print(f"LR_N = {LR_N}")
    LR_MeanAnomaly = LR_N + GD_SUNDATA.get("Ecliptic longitude (epoch)") -GD_SUNDATA.get("Ecliptic longitude (perigee)")
    # print(f"LR_MeanAnomaly = {LR_MeanAnomaly}")
    LR_MeanAnomaly = radians(LR_MeanAnomaly)
    # print(f"LR_MeanAnomaly = {LR_MeanAnomaly}")
    LR_E = solveKepler(LR_MeanAnomaly, GD_SUNDATA.get("Eccentricity"))
    # print(f"LR_E = {LR_E}")  
    LR_V = degrees(atan(((1+LR_e)/(1-LR_e))**(1/2)*tan(LR_E/2))*2)
    # print(f"LR_V = {LR_V}")  
    LR_EclLong = (LR_V + GD_SUNDATA.get("Ecliptic longitude (perigee)"))%360 # correct upto here
    # print(f"LR_EclLong = {LR_EclLong}") 
    return convertEclipticToEquatorial(convertToHrMinSec(0), convertToHrMinSec(LR_EclLong), findAxialTilt(LR_julianDate))

# These four function below are used to refine coordinates for an object
# They remove precession, nutation, aberation and refraction
# def removePrecession(LR_RA, LR_DEC, LR_julianDate):
#     LR_DeciRA = convertToDecimalDegrees(LR_RA[0], LR_RA[1], LR_RA[2])
#     LR_HrsRA = LR_DeciRA*15
#     LR_DeciDEC = convertToDecimalDegrees(LR_DEC[0], LR_DEC[1], LR_DEC[2])
#     LR_N = (LR_julianDate - getJD(2000, 1, 0))/365.2425

#     # Used the estimated value for the J2000 0.0 epoch.
#     LR_S1 = (3.07420 + 1.33589*sin(radians(LR_HrsRA))*tan(radians(LR_DeciDEC))) * LR_N
#     LR_S1h = LR_S1 / 3600

#     LR_FinalRA = convertToHrMinSec((LR_S1h + LR_DeciRA)) # To return - This is the final Right ascention

#     LR_S2 = ((20.0383*cos(radians(LR_HrsRA))) * LR_N)/3600

#     LR_FinalDEC = convertToHrMinSec((LR_S2 + LR_DeciDEC))

#     return (LR_FinalRA, LR_FinalDEC)

# def findNutation(LR_julianDate):

#     # at some point, make sure to:
#     # Correct the ecliptic longitude by adding LR_P
#     # Adjust the obliquity of the ecliptic by adding LR_O

#     LR_T = (LR_julianDate - 2415020)/36525
#     LR_A = 100.002136 * LR_T
#     LR_L = (279.6967 + 360*(LR_A-int(LR_A)))%360
#     LR_B = 5.372617 * LR_T
#     LR_UnHealthySquid = (259.1833 - 360*(LR_B-int(LR_B)))%360
#     # All above this point is correct, there is an error somewhere in the two lines below
#     LR_P = -17.2*sin(radians(LR_UnHealthySquid)) - 1.3*sin(radians(2*LR_L))
#     LR_O = 9.2*cos(radians(LR_UnHealthySquid)) + 0.5*cos(radians(2*LR_L))

#     return (LR_P, LR_O)

# def removeAberation():

# def removeRefraction():

planetary_data = [ # from J2000, supplied from the Jet Propultion Laboratory
    ["Name", "Semi-Major Axis", "Eccentricity", "Inclination", "LongitudeAscNode", "LongitudePerihelion", "MeanLongitude"],
    ["Mercury", 0.38709893, 0.20563069, 7.00487, 48.33167, 77.45645, 252.25084],
    ["Jupiter", 5.20336301, 0.04839266, 1.30530, 100.55615, 14.75385, 34.40438],
    ["Earth", 1.00000011, 0.01671022, 0.00005, -11.26064, 102.94719, 100.46435],
    ["Uranus", 19.19126393, 0.04716771, 0.76986, 74.22988, 170.96424, 313.23218],
    ]


def calculatePlanetPos(LR_julianDate, LL_Data, LL_EarthData):

    #Days since epoch
    LR_daysBetween = LR_julianDate - getJD(2000, 1, 1)
    

    # Primary orbital elements
    LS_NamePlanet, LS_NameEarth = LL_Data[0], LL_EarthData[0]
    LR_SemiMajorAxisEarth, LR_SemiMajorAxisPlanet = LL_Data[1], LL_EarthData[1]
    LR_EccentricityEarth, LR_EccentricityPlanet = LL_Data[2], LL_EarthData[2]
    LR_InclinationEarth, LR_InclinationPlanet = LL_Data[3], LL_EarthData[3]
    LR_AscNodeLongitudeEarth, LR_AscNodeLongitudePlanet = LL_Data[4], LL_EarthData[4]
    LR_PeriLongitudeEarth, LR_PeriLongitudePlanet = LL_Data[5], LL_EarthData[5]
    LR_MeanLongitudeEarth, LR_MeanLongitudePlanet = LL_Data[6], LL_EarthData[6]

    # Calculating period using kepler's third law
    LR_PeriodPlanet, LR_PeriodEarth = (LR_SemiMajorAxisPlanet)**(3/2), (LR_SemiMajorAxisEarth)**(3/2)
    LR_e_Planet = LR_EccentricityPlanet
    LR_daysBetween = LR_julianDate - getJD(1990, 1, 0)
    
    LR_N = ((360/365.242191)*LR_daysBetween)%360
    LR_MeanAnomalyPlanet = LR_N + LR_MeanLongitudePlanet - LR_PeriLongitudePlanet

    return LR_MeanAnomalyPlanet

# print(calculatePlanetPos(getJD(1988, 11, 22.75), planetary_data[2], planetary_data[3]))






# Database connection

import sqlite3

db = "Data.db"
conn = sqlite3.connect(db)
cursor = conn.cursor()
commands = []

print(f"Opened connection to {db}")

# Enter command
sqlCommand = '''
-- Enter command below here



'''
cursor.execute(sqlCommand)
commands.append(sqlCommand)

# Checks if you wish to commit changes to db
try:
    print(f"\nHere are commands you have run since last commit:
          \n{commands}")
    if bool(input("\nWould you like to commit changes? (True/False) ")) == True:
        print("Commiting changes")
        # Commit the changes
        conn.commit()
except TypeError:
    print("Must enter True/False")

print(f"Closing connection to {db}")