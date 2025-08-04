from db import db
from models.tables import HDSTARtable
from Server import app
import cv2
import math


class plateSolver:

    @staticmethod
    def getFaintStars(magnitudeLimit=1.0):
        with app.app_context():
            faintStars = db.session.query(HDSTARtable).filter(
                getattr(HDSTARtable, "V-Mag") < magnitudeLimit
            ).all()
            return faintStars

    @staticmethod
    def processImageForView(
        imagePath="C:\\Users\\alexg\\Documents\\telescope Project\\Canary\\Canary\plateSolver\\test.jpeg",
        blurKernel=(3, 3),
        useCLAHE=True,
        clipLimit=2.0,
        tileGridSize=(8, 8),
        minArea=5,
        useAdaptive=False,
        thresholdValue=40,
        annotate=True,
        saveAs=None,
        rejectArtifacts=True
    ):
        # Load original image
        original = cv2.imread(imagePath, cv2.IMREAD_GRAYSCALE)
        if original is None:
            raise ValueError(f"Could not read image from: {imagePath}")
        img = original.copy()

        # Blur image
        blurred = cv2.GaussianBlur(img, blurKernel, 0)

        # Enhance contrast
        if useCLAHE:
            clahe = cv2.createCLAHE(clipLimit=clipLimit, tileGridSize=tileGridSize)
            enhanced = clahe.apply(blurred)
        else:
            enhanced = cv2.equalizeHist(blurred)

        # Flatten background (nebulosity suppression)
        background = cv2.medianBlur(enhanced, 21)
        flattened = cv2.subtract(enhanced, background)

        # Threshold
        if useAdaptive:
            thresholded = cv2.adaptiveThreshold(
                flattened, 255,
                cv2.ADAPTIVE_THRESH_MEAN_C,
                cv2.THRESH_BINARY,
                31, 2
            )
        else:
            _, thresholded = cv2.threshold(flattened, thresholdValue, 255, cv2.THRESH_BINARY)

        # Find contours
        contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        starPositions = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < minArea:
                continue

            perimeter = cv2.arcLength(contour, True)
            circularity = 4 * math.pi * (area / (perimeter * perimeter)) if perimeter > 0 else 0
            moments = cv2.moments(contour)
            if moments["m00"] != 0:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])

                if rejectArtifacts:
                    if circularity < 0.5:
                        continue
                    if flattened[cy, cx] < 100:
                        continue

                starPositions.append((cx, cy))
                if annotate:
                    cv2.circle(flattened, (cx, cy), 1, 255, -1)

        if saveAs:
            cv2.imwrite(saveAs, flattened)

        return {
            "count": len(starPositions),
            "centroids": starPositions,
            "enhancedImage": flattened
        }

    @staticmethod
    def displayImage():
        result = plateSolver.processImageForView(
            "C:\\Users\\alexg\\Documents\\telescope Project\\Canary\\Canary\\plateSolver\\photo.jpeg",
            saveAs="C:\\Users\\alexg\\Documents\\telescope Project\\Canary\\Canary\\plateSolver\\output.jpeg",
            useAdaptive=False,
            thresholdValue=40,
            rejectArtifacts=True
        )

        print(f"Saved enhanced image as output.jpeg")
        print(f"Detected {result['count']} stars")
        for i, (x, y) in enumerate(result["centroids"]):
            print(f"{i+1}. Star at ({x}, {y})")

    @staticmethod
    def identifyStars(detectedCentroids, tolerance=3):
        # Image metadata for coordinate transform
        center_ra = 45.0       # degrees
        center_dec = 1.0       # degrees
        fov_ra = 2.0
        fov_dec = 2.0
        img_width = 800
        img_height = 800

        # Degrees per pixel
        scale_x = fov_ra / img_width
        scale_y = fov_dec / img_height

        print(f"\n🔍 Using image scale: {scale_x:.4f}°/px X, {scale_y:.4f}°/px Y")

        catalogStars = plateSolver.getFaintStars(9.5)
        print(f"📚 Retrieved {len(catalogStars)} stars for matching")

        matchedStars = []
        unmatchedCentroids = []

        for i, (dx, dy) in enumerate(detectedCentroids):
            print(f"\n🔎 Centroid {i+1}: ({dx}, {dy})")
            foundMatch = False

            for star in catalogStars:
                try:
                    ra = float(getattr(star, "RA"))
                    dec = float(getattr(star, "DEC"))
                except (AttributeError, ValueError):
                    continue

                # Transform RA/DEC to pixel positions
                px = int((ra - center_ra) / scale_x + img_width / 2)
                py = int(-(dec - center_dec) / scale_y + img_height / 2)

                distance = math.hypot(dx - px, dy - py)
                if distance <= tolerance:
                    matchedStars.append({
                        "Name": getattr(star, "Name", "Unknown"),
                        "Magnitude": getattr(star, "V-Mag", "?"),
                        "RA": ra,
                        "DEC": dec,
                        "DetectedPosition": (dx, dy),
                        "ProjectedPosition": (px, py),
                        "Distance": round(distance, 2)
                    })
                    print(f"✅ Matched {star.Name} at ({px}, {py}) — Δ={round(distance,2)}px")
                    foundMatch = True
                    break

            if not foundMatch:
                unmatchedCentroids.append((dx, dy))
                print("❌ No match found")

        print(f"\n🔧 Summary:")
        print(f"✔️ Matched {len(matchedStars)} stars")
        print(f"❌ Unmatched: {len(unmatchedCentroids)}")

        return matchedStars
