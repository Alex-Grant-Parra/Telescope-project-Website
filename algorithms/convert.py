from math import sin, cos, tan, asin, acos, atan, atan2, degrees, radians, pi, floor, sqrt

class convert:
    
    @staticmethod
    def HorizonToEquatorial(LL_AZ, LL_ELV, LR_latitude, LR_LST):

        LR_latitudeRAD = radians(LR_latitude)
        LR_LSTRAD = radians(LR_LST)

        LR_AZ = radians(convert.HrMinSecToDegrees(LL_AZ[0], LL_AZ[1], LL_AZ[2])) # Input Azimith
        LR_ELV = radians(convert.HrMinSecToDegrees(LL_ELV[0], LL_ELV[1], LL_ELV[2])) # Input Elevation

        # Finds the declination
        LR_DEC = asin(sin(LR_ELV)*sin(LR_latitudeRAD) + cos(LR_ELV)*cos(LR_latitudeRAD)*cos(LR_AZ))

        # Finds the hour angle
        LR_H = acos((sin(LR_ELV)-sin(LR_latitudeRAD)*sin(LR_DEC)) / (cos(LR_latitudeRAD)*cos(LR_DEC)))/15

        if degrees(sin(LR_AZ)) > 0:
            LR_H = 360 - LR_H

        # Finds right ascension
        LR_RA = (LR_LSTRAD - LR_H)%radians(24) # Calculates the right ascention
        return(convert.DecimalToHrMinSec(degrees(LR_RA)), convert.DecimalToHrMinSec(degrees(LR_DEC))) # Returns a tuple of (Right Ascention, Declination)

    @staticmethod
    def EquatorialToHorizon(LL_RA, LL_DEC, LR_latitude, LR_LST):

        def getHourAngle(LL_RA, LR_LST): # Getting hour angle, all units in degrees
            LR_RA = convert.HrMinSecToDegrees(LL_RA[0], LL_RA[1], LL_RA[2])
            LR_H = LR_LST - LR_RA

            if LR_H < 0:
                LR_H = LR_H + 24
            return LR_H
             
        LR_latitude_RAD = radians(LR_latitude)
        LR_H_RAD = radians(getHourAngle(LL_RA, LR_LST)*15)
        LR_DEC_RAD = radians(convert.HrMinSecToDegrees(LL_DEC[0], LL_DEC[1], LL_DEC[2]))
        # print(getHourAngle(LL_RA, LR_LST))
        # print(degrees(LR_H_RAD))
        LR_ELV_RAD = asin(sin(LR_DEC_RAD) * sin(LR_latitude_RAD) + cos(LR_DEC_RAD) * cos(LR_latitude_RAD) * cos(LR_H_RAD))

        LR_AZ_RAD = acos((sin(LR_DEC_RAD) - sin(LR_latitude_RAD)*sin(LR_ELV_RAD)) / (cos(LR_latitude_RAD)*cos(LR_ELV_RAD)))

        if sin(LR_H_RAD) > 0:
            LR_AZ_DEG = 360 - degrees(LR_AZ_RAD)
        else:
            LR_AZ_DEG = degrees(LR_AZ_RAD)

        LR_ELV_DEG = degrees(LR_ELV_RAD)

        return(convert.DecimalToHrMinSec(LR_AZ_DEG), convert.DecimalToHrMinSec(LR_ELV_DEG)) # Returns a tuple of (Azimuth, Elevation)

    @staticmethod
    def EclipticToEquatorial(LL_EclLat, LL_EclLong, LR_AxialTiltDeg):

        LR_AxialTiltRad = radians(LR_AxialTiltDeg)
        LR_EclLong = radians(convert.HrMinSecToDegrees(LL_EclLong[0], LL_EclLong[1], LL_EclLong[2]))
        LR_EclLat = radians(convert.HrMinSecToDegrees(LL_EclLat[0], LL_EclLat[1], LL_EclLat[2]))

        LR_DEC = asin(sin(LR_EclLat)*cos(LR_AxialTiltRad)+cos(LR_EclLat)*sin(LR_AxialTiltRad)*sin(LR_EclLong))

        LR_Y = sin(LR_EclLong)*cos(LR_AxialTiltRad)-tan(LR_EclLat)*sin(LR_AxialTiltRad)
        LR_X = cos(LR_EclLong)

        LR_RA = atan2(LR_Y, LR_X)

        LR_RA = (degrees(LR_RA)/15)%24
        LR_DEC = degrees(LR_DEC)%360
        # print(f"LR_DEC = {LR_DEC}")

        LR_RA = convert.DecimalToHrMinSec(LR_RA%24)

        # print(LR_DEC)
        LR_DEC = LR_DEC%360
        if LR_DEC > 180:
            LR_DEC = LR_DEC - 360
        elif LR_DEC > 90:
            LR_DEC = 180 - LR_DEC

        LR_DEC = convert.DecimalToHrMinSec(LR_DEC)

        return(LR_RA, LR_DEC)
    
    @staticmethod
    def EquatorialToEcliptic(LL_RA, LL_DEC, LR_AxialTilt):
        LR_AxialTiltRad = radians(LR_AxialTilt)

        LR_RA = convert.HrMinSecToDegrees(LL_RA[0], LL_RA[1], LL_RA[2])
        LR_DEC = convert.HrMinSecToDegrees(LL_DEC[0], LL_DEC[1], LL_DEC[2])

        LR_RA = radians(LR_RA*15)
        LR_DEC = radians(LR_DEC)

        LR_EclLat = asin(sin(LR_DEC)*cos(LR_AxialTiltRad) - cos(LR_DEC)*sin(LR_AxialTiltRad)*sin(LR_RA))

        LR_Y = sin(LR_RA)*cos(LR_AxialTiltRad) + tan(LR_DEC)*sin(LR_AxialTiltRad)
        LR_X = cos(LR_RA)

        LR_EclLong = atan2(LR_Y, LR_X)

        LR_EclLong = convert.DecimalToHrMinSec(degrees(LR_EclLong))
        LR_EclLat = convert.DecimalToHrMinSec(degrees(LR_EclLat))

        return (LR_EclLat, LR_EclLong)
  
    @staticmethod
    def DecimalToHrMinSec(LR_hoursSigned):
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

    @staticmethod
    def HrMinSecToDegrees(LI_hour, LI_minute, LR_second):
        return LI_hour + LI_minute / 60 + LR_second / 3600