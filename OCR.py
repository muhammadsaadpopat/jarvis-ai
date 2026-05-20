import os
from config import Config
from logger import logger

# Initialize pytesseract command path from configuration
tesseract_path = Config.get("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
except ImportError:
    pytesseract = None
    logger.error("pytesseract package is not installed. OCR capabilities will be disabled.")

try:
    import cv2
except ImportError:
    cv2 = None
    logger.error("OpenCV (cv2) package is not installed. Camera capabilities will be disabled.")


def OCR():
    if cv2 is None or pytesseract is None:
        logger.error("OCR dependencies are missing. Cannot start OCR scan.")
        print("Error: Missing OCR dependencies. Ensure cv2 and pytesseract are installed.")
        return

    # Verify tesseract path exists
    if not os.path.exists(tesseract_path):
        logger.error(f"Tesseract executable not found at specified path: '{tesseract_path}'")
        print(f"Error: Tesseract not found at '{tesseract_path}'. Please configure TESSERACT_PATH.")
        return

    frame_width = int(Config.get("OCR_FRAME_WIDTH", 640))
    frame_height = int(Config.get("OCR_FRAME_HEIGHT", 480))
    brightness = int(Config.get("OCR_BRIGHTNESS", 180))

    logger.info("Initializing camera for OCR processing...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Failed to open video capture device 0 for OCR.")
        print("Error: Camera device not accessible.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
    cap.set(cv2.CAP_PROP_BRIGHTNESS, brightness)

    print("OCR Active. Press 'q' in the camera window to exit.")
    
    try:
        while True:
            success, img = cap.read()
            if not success:
                logger.warning("Failed to grab camera frame.")
                break
                
            img_display = img.copy()
            try:
                text_recognized = pytesseract.image_to_string(img, lang='eng')
                text_recognized = text_recognized.replace("\n\x0c", "").strip()
                if text_recognized:
                    print(f"[OCR Result] {text_recognized}")
                    # Draw text overlay if it exists
                    cv2.putText(
                        img_display, 
                        text_recognized[:50],  # display start of text
                        (10, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.8, 
                        (0, 255, 0), 
                        2, 
                        cv2.LINE_AA
                    )
            except Exception as ocr_err:
                logger.error(f"pytesseract extraction error: {ocr_err}")
                
            cv2.imshow("J.A.R.V.I.S. OCR Camera Feed", img_display)
            
            # Use standard waitKey check
            if cv2.waitKey(1) & 0xFF == ord('q'):    
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        logger.info("OCR Camera Feed released and windows closed.")

if __name__ == '__main__':
    OCR()