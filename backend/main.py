from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, ImageEnhance
from pytesseract import Output
import pytesseract
import io
import re

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


@app.get("/")
def home():
    return {"message": "TTB Label Verifier backend is running"}


def preprocess_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")

    width, height = image.size
    image = image.resize((width * 2, height * 2))

    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Sharpness(image).enhance(1.5)

    return image


def get_ocr_score(image: Image.Image):
    data = pytesseract.image_to_data(
        image,
        output_type=Output.DICT,
        config="--psm 3"
    )

    confidences = []
    readable_words = 0

    for text, confidence in zip(data["text"], data["conf"]):
        text = text.strip()

        try:
            confidence = float(confidence)
        except ValueError:
            continue

        if confidence >= 0 and text:
            confidences.append(confidence)

            # Only count text that looks somewhat word-like
            if any(char.isalpha() for char in text):
                readable_words += 1

    if not confidences:
        return 0, 0, 0

    average_confidence = sum(confidences) / len(confidences)

    # Reward both confident OCR and finding more actual words
    score = average_confidence + (readable_words * 1.5)

    return score, average_confidence, readable_words


def find_best_rotation(image: Image.Image):
    rotations = {
        0: image,
        90: image.rotate(90, expand=True),
        180: image.rotate(180, expand=True),
        270: image.rotate(270, expand=True),
    }

    best_angle = 0
    best_image = image
    best_score = -1
    best_confidence = 0
    best_word_count = 0

    for angle, rotated_image in rotations.items():
        score, confidence, word_count = get_ocr_score(rotated_image)

        if score > best_score:
            best_score = score
            best_angle = angle
            best_image = rotated_image
            best_confidence = confidence
            best_word_count = word_count

    return (
        best_image,
        best_angle,
        best_confidence,
        best_word_count
    )

def extract_abv(text: str):
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)

    if not matches:
        return None

    values = []

    for match in matches:
        try:
            value = float(match)

            # Reasonable alcohol percentage range
            if 0 < value <= 100:
                values.append(value)

        except ValueError:
            pass

    if not values:
        return None

    return values[0]


def extract_net_contents(text: str):
    pattern = r"(\d+(?:\.\d+)?)\s*(mL|ml|ML|L|l)\b"

    match = re.search(pattern, text)

    if not match:
        return None

    amount = match.group(1)
    unit = match.group(2).upper()

    return f"{amount} {unit}"


def detect_government_warning(text: str):
    normalized = text.upper()

    warning_words = [
        "GENERAL",
        "WOMEN",
        "DRINK",
        "ALCOHOLIC",
        "PREGNANCY",
        "RISK",
        "BEVERAGES"
    ]

    matches = []

    for word in warning_words:
        if word in normalized:
            matches.append(word)

    # Enough distinctive warning-language detected
    found = len(matches) >= 4

    return {
        "found": found,
        "matched_words": matches,
        "match_count": len(matches)
    }

def normalize_text(value: str):
    value = value.lower()
    value = re.sub(r"[^\w\s']", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def verify_brand(expected_brand: str, extracted_text: str):
    normalized_brand = normalize_text(expected_brand)
    normalized_ocr = normalize_text(extracted_text)

    if normalized_brand in normalized_ocr:
        return {
            "status": "pass",
            "expected": expected_brand,
            "message": "Brand name detected on the label."
        }

    return {
        "status": "needs_review",
        "expected": expected_brand,
        "message": "Brand name could not be confidently detected."
    }


@app.post("/verify")
async def verify_label(
    label: UploadFile = File(...),
    expected_abv: float = Form(...),
    expected_brand: str = Form(...)
):

    if not label.content_type or not label.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Please upload an image file."
        )

    try:
        contents = await label.read()

        image = Image.open(io.BytesIO(contents))

        processed_image = preprocess_image(image)

        best_image, rotation, confidence, word_count = find_best_rotation(
            processed_image
        )

        extracted_text = pytesseract.image_to_string(
            best_image,
            config="--psm 3"
        )

        abv = extract_abv(extracted_text)

        if abv is None:
            abv_result = {
                "status": "needs_review",
                "expected": expected_abv,
                "detected": None,
                "message": "Could not reliably detect an ABV on the label."
            }

        elif abs(abv - expected_abv) < 0.01:
            abv_result = {
                "status": "pass",
                "expected": expected_abv,
                "detected": abv,
                "message": "Alcohol content matches the application."
            }

        else:
            abv_result = {
                "status": "fail",
                "expected": expected_abv,
                "detected": abv,
                "message": "Alcohol content does not match the application."
            }
        net_contents = extract_net_contents(extracted_text)
        government_warning = detect_government_warning(extracted_text)
        brand_result = verify_brand(expected_brand, extracted_text)

        return {
            "filename": label.filename,
            "rotation_used": rotation,
            "ocr_confidence": round(confidence, 2),
            "readable_words": word_count,
            "extracted_fields": {
                "abv": abv,
                "net_contents": net_contents,
                "government_warning": government_warning
            },
            "verification": {
                "abv": abv_result,
                "brand": brand_result
            },
            "extracted_text": extracted_text,
            "status": "OCR completed successfully"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not process label: {str(e)}"
        )