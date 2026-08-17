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
import json
import time
import os

app = FastAPI()

frontend_origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:3000"
).split(",")

frontend_origins = [
    origin.strip()
    for origin in frontend_origins
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


if os.name == "nt":
    default_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
else:
    default_tesseract = "/usr/bin/tesseract"

pytesseract.pytesseract.tesseract_cmd = os.getenv(
    "TESSERACT_CMD",
    default_tesseract
)

USE_LOCAL_OCR = os.getenv(
    "USE_LOCAL_OCR",
    "true"
).lower() == "true"

client = OpenAI()

@app.get("/")
def home():
    return {"message": "TTB Label Verifier backend is running"}

@app.get("/debug-cors")
def debug_cors():
    return {
        "frontend_origins": frontend_origins
    }

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


def run_ocr(image: Image.Image):
    score, confidence, word_count, text = get_ocr_score(image)

    return (
        0,
        confidence,
        word_count,
        text
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
    normalized_detected = normalize_text(extracted_text)

    # Exact normalized match
    if normalized_expected == normalized_detected:
        return {
            "status": "pass",
            "expected": expected_class_type,
            "score": 100,
            "message": "Class/type designation matches."
        }

    # Full-string similarity instead of substring similarity
    score = fuzz.ratio(
        normalized_expected,
        normalized_detected
    )

    if score >= 85:
        return {
            "status": "pass",
            "expected": expected_class_type,
            "score": round(score, 1),
            "message": "Class/type detected with minor text differences."
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
        "message": "Class/type could not be confidently matched."
    }

def extract_fields_with_ai(
    image_bytes: bytes,
    content_type: str
):
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Examine this alcohol beverage label image. "
                            "Extract only information visibly present in the image. "
                            "Do not infer missing information from product knowledge."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            f"data:{content_type};base64,{encoded_image}"
                        ),
                        "detail": "high",
                    },
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "alcohol_label_fields",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "brand_name": {
                            "type": ["string", "null"]
                        },
                        "class_type": {
                            "type": ["string", "null"]
                        },
                        "abv": {
                            "type": ["number", "null"]
                        },
                        "net_contents": {
                            "type": ["string", "null"]
                        },
                        "government_warning_visible": {
                            "type": "boolean"
                        }
                    },
                    "required": [
                        "brand_name",
                        "class_type",
                        "abv",
                        "net_contents",
                        "government_warning_visible"
                    ],
                    "additionalProperties": False
                }
            }
        }
    )

    text = response.output_text

    if not text:
        raise ValueError("AI returned no text output.")

    return json.loads(text)

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
        request_start = time.perf_counter()

        ai_fields = None
        ai_time = 0

        if USE_LOCAL_OCR:
                ocr_start = time.perf_counter()

                processed_image = preprocess_image(image)

                rotation, confidence, word_count, extracted_text = run_ocr(
                 processed_image
                )

                ocr_time = time.perf_counter() - ocr_start

        else:
            rotation = 0
            confidence = 0
            word_count = 0
            extracted_text = ""
            ocr_time = 0

        # --------------------------------------------------
        # First attempt: local OCR
        # --------------------------------------------------

        ai_fields = None
        ai_time = 0

        # ABV from OCR
        abv = extract_abv(extracted_text)
        abv_source = "ocr"

        # Brand from OCR
        brand_result = verify_brand(
            expected_brand,
            extracted_text
        )

        # Class/type from OCR
        class_type_result = verify_class_type(
            expected_class_type,
            extracted_text
        )

        # Net contents from OCR
        net_contents = extract_net_contents(extracted_text)
        net_contents_source = "ocr"

        # Government warning stays rule-based
        government_warning = verify_government_warning(extracted_text)

        

        # --------------------------------------------------
        # Decide whether AI assistance is actually needed
        # --------------------------------------------------

        needs_ai = (
            confidence < 50
            or brand_result["status"] == "needs_review"
            or class_type_result["status"] == "needs_review"
        )


        # --------------------------------------------------
        # One AI vision call, only when needed
        # --------------------------------------------------

        if needs_ai:
            ai_start = time.perf_counter()

            try:
                ai_fields = extract_fields_with_ai(
                    contents,
                    label.content_type
                )

            except Exception as e:
                print(f"AI extraction failed: {e}")

            finally:
                ai_time = time.perf_counter() - ai_start

        # --------------------------------------------------
        # Use AI as supporting evidence for warning presence
        # --------------------------------------------------

        if (
            not government_warning["detected"]
            and ai_fields
            and ai_fields.get("government_warning_visible") is True
        ):
            government_warning = {
                "status": "needs_review",
                "detected": True,
                "matched_indicators": government_warning.get(
                    "matched_indicators",
                    []
                ),
                "source": "ai",
                "message": (
                    "Government warning is visibly present, "
                    "but exact wording and formatting require review."
                )
            }

        elif government_warning["detected"]:
            government_warning["source"] = "ocr"


        # --------------------------------------------------
        # Use AI to rescue ABV only if OCR missed it
        # --------------------------------------------------

        if abv is None and ai_fields:
            ai_abv = ai_fields.get("abv")

            if ai_abv is not None:
                try:
                    abv = float(ai_abv)
                    abv_source = "ai"
                except (ValueError, TypeError):
                    pass


        # --------------------------------------------------
        # Final ABV comparison
        # --------------------------------------------------

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

        abv_result["source"] = abv_source


        # --------------------------------------------------
        # Use AI to rescue brand if OCR was uncertain
        # --------------------------------------------------

        if (
            brand_result["status"] == "needs_review"
            and ai_fields
            and ai_fields.get("brand_name")
        ):
            ai_brand = ai_fields["brand_name"]

            ai_brand_result = verify_brand(
                expected_brand,
                ai_brand
            )

            if ai_brand_result["status"] == "pass":
                brand_result = {
                    **ai_brand_result,
                    "detected": ai_brand,
                    "source": "ai",
                    "message": "Brand verified using AI-assisted extraction."
                }


        # If OCR passed brand without AI
        if (
            brand_result["status"] == "pass"
            and "source" not in brand_result
        ):
            brand_result["source"] = "ocr"


        # --------------------------------------------------
        # Use AI to rescue class/type if OCR was uncertain
        # --------------------------------------------------

        if (
            class_type_result["status"] == "needs_review"
            and ai_fields
            and ai_fields.get("class_type")
        ):
            ai_class_type = ai_fields["class_type"]

            ai_result = verify_class_type(
                expected_class_type,
                ai_class_type
            )

            if ai_result["status"] == "pass":
                class_type_result = {
                    **ai_result,
                    "detected": ai_class_type,
                    "source": "ai",
                    "message": "Class/type verified using AI-assisted extraction."
                }


        # If OCR passed class/type without AI
        if (
            class_type_result["status"] == "pass"
            and "source" not in class_type_result
        ):
            class_type_result["source"] = "ocr"


        # --------------------------------------------------
        # Use AI to rescue net contents if OCR missed it
        # --------------------------------------------------

        if net_contents is None and ai_fields:
            ai_net_contents = ai_fields.get("net_contents")

            if ai_net_contents:
                net_contents = ai_net_contents
                net_contents_source = "ai"

        # Calculate total backend processing time
        total_time = time.perf_counter() - request_start

        return {
            "filename": label.filename,
            "rotation_used": rotation,
            "ocr_confidence": round(confidence, 2),
            "readable_words": word_count,
            "extracted_fields": {
                "abv": abv,
                "net_contents": {
                    "value": net_contents,
                    "source": net_contents_source
                },
                "government_warning": government_warning
            },
            "verification": {
                "abv": abv_result,
                "brand": brand_result,
                "class_type": class_type_result
            },
            "extracted_text": extracted_text,
            "timing": {
                "ocr_seconds": round(ocr_time, 2),
                "ai_seconds": round(ai_time, 2),
                "total_backend_seconds": round(total_time, 2)
            },
            "status": "OCR completed successfully"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not process label: {str(e)}"
        )
    