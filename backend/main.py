from turtle import width
from rapidfuzz import fuzz
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, ImageEnhance
from pytesseract import Output
from openai import OpenAI
import base64
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

client = OpenAI()

@app.get("/")
def home():
    return {"message": "TTB Label Verifier backend is running"}


def preprocess_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")

    width, height = image.size

    max_dimension = 2000

    if max(width, height) > max_dimension:
        scale = max_dimension / max(width, height)

        image = image.resize(
            (
                int(width * scale),
                int(height * scale)
            )
        )
    
    elif max(width, height) < 1200:
        scale = 1200 / max(width, height)

        image = image.resize(
            (
                int(width * scale),
                int(height * scale)
            )
        )

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
    words = []

    for text, confidence in zip(data["text"], data["conf"]):
        text = text.strip()

        try:
            confidence = float(confidence)
        except ValueError:
            continue

        if confidence >= 0 and text:
            confidences.append(confidence)
            words.append(text)

            if any(char.isalpha() for char in text):
                readable_words += 1

    if not confidences:
        return 0, 0, 0, ""

    average_confidence = sum(confidences) / len(confidences)

    score = average_confidence + (readable_words * 1.5)

    extracted_text = " ".join(words)

    return (
        score,
        average_confidence,
        readable_words,
        extracted_text
    )


def find_best_rotation(image: Image.Image):
    rotations = {
        0: image,
        90: image.rotate(90, expand=True),
        180: image.rotate(180, expand=True),
        270: image.rotate(270, expand=True),
    }

    best_angle = 0
    best_score = -1
    best_confidence = 0
    best_word_count = 0
    best_text = ""

    for angle, rotated_image in rotations.items():
        score, confidence, word_count, text = get_ocr_score(
            rotated_image
        )

        if score > best_score:
            best_score = score
            best_angle = angle
            best_confidence = confidence
            best_word_count = word_count
            best_text = text

    return (
        best_angle,
        best_confidence,
        best_word_count,
        best_text
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


def verify_government_warning(text: str):
    normalized = normalize_text(text).upper()

    indicators = [
        "ACCORDING TO THE",
        "ALCOHOLIC",
        "PREGNANCY",
        "DRIVE A CAR",
        "DRIVEACAR",
        "HEALTH PROBLEMS",
        "CONSUMPTION",
        "WOMEN",
        "DRINK",
    ]

    matched = [
        indicator
        for indicator in indicators
        if indicator in normalized
    ]

    detected = len(matched) >= 3

    if not detected:
        return {
            "status": "needs_review",
            "detected": False,
            "matched_indicators": matched,
            "message": "Government warning could not be confidently detected."
        }

    return {
        "status": "needs_review",
        "detected": True,
        "matched_indicators": matched,
        "message": (
            "Government warning language detected, but exact wording "
            "and formatting require review."
        )
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
            "score": 100,
            "message": "Brand name detected on the label."
        }

    score = fuzz.partial_ratio(
        normalized_brand,
        normalized_ocr
    )

    if score >= 85:
        return {
            "status": "pass",
            "expected": expected_brand,
            "score": round(score, 1),
            "message": "Brand name detected with minor OCR differences."
        }

    if score >= 65:
        return {
            "status": "needs_review",
            "expected": expected_brand,
            "score": round(score, 1),
            "message": "Possible brand name match. Human review recommended."
        }

    return {
        "status": "needs_review",
        "expected": expected_brand,
        "score": round(score, 1),
        "message": "Brand name could not be confidently detected."
    }

def verify_class_type(expected_class_type: str, extracted_text: str):
    normalized_expected = normalize_text(expected_class_type)
    normalized_ocr = normalize_text(extracted_text)

    if normalized_expected in normalized_ocr:
        return {
            "status": "pass",
            "expected": expected_class_type,
            "score": 100,
            "message": "Class/type designation detected on the label."
        }

    score = fuzz.partial_ratio(
        normalized_expected,
        normalized_ocr
    )

    if score >= 85:
        return {
            "status": "pass",
            "expected": expected_class_type,
            "score": round(score, 1),
            "message": "Class/type detected with minor OCR differences."
        }

    if score >= 65:
        return {
            "status": "needs_review",
            "expected": expected_class_type,
            "score": round(score, 1),
            "message": "Possible class/type match. Human review recommended."
        }

    return {
        "status": "needs_review",
        "expected": expected_class_type,
        "score": round(score, 1),
        "message": "Class/type could not be confidently detected."
    }

def extract_class_type_with_ai(
    image_bytes: bytes,
    content_type: str
):
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.responses.create(
        model="gpt-5-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Examine this alcohol beverage label. "
                            "Extract only the class or type designation "
                            "of the beverage, such as 'French Vermouth', "
                            "'Kentucky Straight Bourbon Whiskey', "
                            "'Cabernet Sauvignon', or 'India Pale Ale'. "
                            "Return only the designation. "
                            "If you cannot determine it confidently, "
                            "return exactly: UNKNOWN"
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            f"data:{content_type};base64,{encoded_image}"
                        ),
                    },
                ],
            }
        ],
    )

    result = response.output_text.strip()

    if result.upper() == "UNKNOWN":
        return None

    return result

@app.post("/verify")
async def verify_label(
    label: UploadFile = File(...),
    expected_abv: float = Form(...),
    expected_brand: str = Form(...),
    expected_class_type: str = Form(...)
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

        rotation, confidence, word_count, extracted_text = find_best_rotation(
            processed_image
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
        government_warning = verify_government_warning(extracted_text)
        brand_result = verify_brand(expected_brand, extracted_text)
        class_type_result = verify_class_type(expected_class_type, extracted_text)
        ai_class_type = None

        if class_type_result["status"] == "needs_review":
            try:
                ai_class_type = extract_class_type_with_ai(
                    contents,
                    label.content_type
                )           

                if ai_class_type:
                    ai_result = verify_class_type(
                        expected_class_type,
                        ai_class_type
                    )

                if ai_result["status"] == "pass":
                    class_type_result = {
                        **ai_result,
                        "detected": ai_class_type,
                        "source": "ai",
                        "message": (
                            "Class/type verified using AI-assisted "
                            "label extraction."
                        )
                    }
            except Exception as e:
                print(f"AI fallback failed: {e}")
        if (
            class_type_result["status"] == "pass"
            and "source" not in class_type_result
        ):
            class_type_result["source"] = "ocr"

        
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
                "brand": brand_result,
                "class_type": class_type_result
            },
            "extracted_text": extracted_text,
            "status": "OCR completed successfully"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not process label: {str(e)}"
        )
    