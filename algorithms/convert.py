from math import sin, cos, asin, atan2, degrees, radians

class convert:

    @staticmethod
    def _apply_matrix_3x3(M, v):
        return (
            M[0][0] * v[0] + M[0][1] * v[1] + M[0][2] * v[2],
            M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2],
            M[2][0] * v[0] + M[2][1] * v[1] + M[2][2] * v[2],
        )

    @staticmethod
    def _rotate_x(v, angle_rad):
        c = cos(angle_rad)
        s = sin(angle_rad)
        R = (
            (1.0, 0.0, 0.0),
            (0.0, c, -s),
            (0.0, s, c),
        )
        return convert._apply_matrix_3x3(R, v)

    @staticmethod
    def _spherical_to_cartesian(lon_rad, lat_rad):
        clat = cos(lat_rad)
        return (
            clat * cos(lon_rad),
            clat * sin(lon_rad),
            sin(lat_rad),
        )

    @staticmethod
    def _cartesian_to_spherical(v):
        x, y, z = v
        lat = asin(max(-1.0, min(1.0, z)))
        lon = atan2(y, x)
        return lon, lat
    
    @staticmethod
    def HorizonToEquatorial(LL_AZ, LL_ELV, LR_latitude, LR_LST):
        LR_latitudeRAD = radians(LR_latitude)
        LR_AZ = radians(convert.HrMinSecToDegrees(LL_AZ[0], LL_AZ[1], LL_AZ[2]))
        LR_ELV = radians(convert.HrMinSecToDegrees(LL_ELV[0], LL_ELV[1], LL_ELV[2]))

        # Horizon vector (north, east, up), with azimuth measured from north toward east.
        v_hor = (
            cos(LR_ELV) * cos(LR_AZ),
            cos(LR_ELV) * sin(LR_AZ),
            sin(LR_ELV),
        )

        sphi = sin(LR_latitudeRAD)
        cphi = cos(LR_latitudeRAD)
        # Inverse of equatorial->horizon rotation.
        R_hor_to_eq = (
            (-sphi, 0.0, cphi),
            (0.0, -1.0, 0.0),
            (cphi, 0.0, sphi),
        )
        x_eq, y_eq, z_eq = convert._apply_matrix_3x3(R_hor_to_eq, v_hor)

        LR_DEC_RAD = asin(max(-1.0, min(1.0, z_eq)))
        LR_H_RAD = atan2(y_eq, x_eq)
        LR_H_HOURS = (degrees(LR_H_RAD) / 15.0) % 24.0
        LR_RA_HOURS = (LR_LST - LR_H_HOURS) % 24.0

        return (
            convert.DecimalToHrMinSec(LR_RA_HOURS),
            convert.DecimalToHrMinSec(degrees(LR_DEC_RAD)),
        )

    @staticmethod
    def EquatorialToHorizon(LL_RA, LL_DEC, LR_latitude, LR_LST):
        LR_latitude_RAD = radians(LR_latitude)

        LR_RA_HOURS = convert.HrMinSecToDegrees(LL_RA[0], LL_RA[1], LL_RA[2])
        LR_DEC_RAD = radians(convert.HrMinSecToDegrees(LL_DEC[0], LL_DEC[1], LL_DEC[2]))
        LR_H_RAD = radians(((LR_LST - LR_RA_HOURS) % 24.0) * 15.0)

        # Equatorial unit vector in (x, y, z) = (cos(dec)cos(H), cos(dec)sin(H), sin(dec)).
        v_eq = (
            cos(LR_DEC_RAD) * cos(LR_H_RAD),
            cos(LR_DEC_RAD) * sin(LR_H_RAD),
            sin(LR_DEC_RAD),
        )

        sphi = sin(LR_latitude_RAD)
        cphi = cos(LR_latitude_RAD)
        R_eq_to_hor = (
            (-sphi, 0.0, cphi),
            (0.0, -1.0, 0.0),
            (cphi, 0.0, sphi),
        )
        n, e, u = convert._apply_matrix_3x3(R_eq_to_hor, v_eq)

        LR_AZ_DEG = (degrees(atan2(e, n)) + 360.0) % 360.0
        LR_ELV_DEG = degrees(asin(max(-1.0, min(1.0, u))))

        return (
            convert.DecimalToHrMinSec(LR_AZ_DEG),
            convert.DecimalToHrMinSec(LR_ELV_DEG),
        )

    @staticmethod
    def EclipticToEquatorial(LL_EclLat, LL_EclLong, LR_AxialTiltDeg):
        LR_EclLong = radians(convert.HrMinSecToDegrees(*LL_EclLong))
        LR_EclLat = radians(convert.HrMinSecToDegrees(*LL_EclLat))
        LR_AxialTiltRad = radians(LR_AxialTiltDeg)

        v_ecl = convert._spherical_to_cartesian(LR_EclLong, LR_EclLat)
        v_eq = convert._rotate_x(v_ecl, LR_AxialTiltRad)
        LR_RA_RAD, LR_DEC_RAD = convert._cartesian_to_spherical(v_eq)

        LR_RA = (degrees(LR_RA_RAD) / 15.0) % 24.0
        LR_DEC = degrees(LR_DEC_RAD)

        return convert.DecimalToHrMinSec(LR_RA), convert.DecimalToHrMinSec(LR_DEC)

    
    @staticmethod
    def EquatorialToEcliptic(LL_RA, LL_DEC, LR_AxialTilt):
        LR_AxialTiltRad = radians(LR_AxialTilt)

        LR_RA = convert.HrMinSecToDegrees(LL_RA[0], LL_RA[1], LL_RA[2])
        LR_DEC = convert.HrMinSecToDegrees(LL_DEC[0], LL_DEC[1], LL_DEC[2])

        LR_RA = radians(LR_RA*15)
        LR_DEC = radians(LR_DEC)

        v_eq = convert._spherical_to_cartesian(LR_RA, LR_DEC)
        v_ecl = convert._rotate_x(v_eq, -LR_AxialTiltRad)
        LR_EclLong, LR_EclLat = convert._cartesian_to_spherical(v_ecl)

        LR_EclLong = convert.DecimalToHrMinSec((degrees(LR_EclLong) + 360.0) % 360.0)
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
    def DegreesToHMS(LR_degrees):
        """Convert decimal degrees to [hour, minute, second] with rollover handling."""
        LR_hours = (LR_degrees / 15.0) % 24.0
        LI_hours = int(LR_hours)
        LR_minutes = (LR_hours - LI_hours) * 60.0
        LI_minutes = int(LR_minutes)
        LR_seconds = round((LR_minutes - LI_minutes) * 60.0, 2)

        if LR_seconds >= 60:
            LR_seconds = 0
            LI_minutes += 1
        if LI_minutes >= 60:
            LI_minutes = 0
            LI_hours = (LI_hours + 1) % 24

        return [LI_hours, LI_minutes, LR_seconds]

    @staticmethod
    def DegreesToDMS(LR_degrees):
        """Convert signed decimal degrees to [degree, minute, second] with rollover handling."""
        LI_sign = -1 if LR_degrees < 0 else 1
        LR_absDegrees = abs(LR_degrees)
        LI_degrees = int(LR_absDegrees)
        LR_minutes = (LR_absDegrees - LI_degrees) * 60.0
        LI_minutes = int(LR_minutes)
        LR_seconds = round((LR_minutes - LI_minutes) * 60.0, 2)

        if LR_seconds >= 60:
            LR_seconds = 0
            LI_minutes += 1
        if LI_minutes >= 60:
            LI_minutes = 0
            LI_degrees += 1

        LI_degrees *= LI_sign
        return [LI_degrees, LI_minutes, LR_seconds]

    @staticmethod
    def HrMinSecToDegrees(hours, minutes, seconds):
        sign = -1 if hours < 0 or minutes < 0 or seconds < 0 else 1
        return sign * (abs(hours) + abs(minutes) / 60 + abs(seconds) / 3600)
