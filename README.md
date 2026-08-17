# TTB Label Verifier

A prototype decision-support tool for verifying information on alcohol beverage labels against expected application data.

The application accepts an image of a beverage label along with expected application values and attempts to verify key label information including:

- Brand name
- Class / type designation
- Alcohol by volume (ABV)
- Government warning presence
- Net contents

The system combines deterministic verification logic with OCR and AI-assisted image extraction. When the available evidence is insufficient to make a reliable determination, the application returns **Needs Review** rather than automatically treating the label as compliant or noncompliant.

## Live Demo

**Application:** https://ttb-label-verifier-black.vercel.app

The Next.js frontend is deployed on Vercel and communicates with a FastAPI backend deployed on Render.

---

## Features

The verifier currently evaluates five label elements:

### Brand Name

The detected brand is compared against the brand entered from the application.

Normalized text and fuzzy matching are used to tolerate minor OCR differences.

### Class / Type

The detected beverage class or type is compared against the expected designation.

Examples include:

- Ale
- Cognac
- French Vermouth

Full-string similarity is preferred over simple substring matching to avoid incorrectly treating a partial designation as a perfect match.

### Alcohol Content

The detected alcohol percentage is converted to a numeric value and compared directly against the expected ABV.

For example:

```text
Expected: 40%
Detected: 40%
Result: Pass
```

### Government Warning

The application looks for evidence that the required government warning is visibly present.

Because confirming exact regulatory wording and formatting from image extraction alone can be unreliable, warning detection does not automatically certify full compliance.

When warning language is detected, the system can return:

```text
Government Warning
Warning visibly detected
Needs Review
```

This intentionally leaves exact wording and formatting verification to a human reviewer.

### Net Contents

The system attempts to identify quantities such as:

```text
750 mL
12 FL. OZ.
```

If net contents cannot be reliably identified, the field is routed to **Needs Review**.

---

## Verification Results

Each field receives one of three statuses:

### Pass

The detected value sufficiently matches the expected application value.

### Fail

A confidently detected value conflicts with the expected value.

### Needs Review

The system cannot make a sufficiently reliable determination.

This conservative behavior is intentional. The prototype is designed to assist a reviewer rather than replace regulatory judgment.

---

## Architecture

The application consists of:

```text
ttb-label-verifier/
│
├── frontend/
│   └── Next.js / React / TypeScript / Tailwind CSS
│
└── backend/
    └── FastAPI / Python / Tesseract / OpenAI API
```

The backend supports two extraction configurations.

---

## Local / OCR-First Mode

When running locally or in an environment with sufficient CPU resources, the application uses an OCR-first pipeline.

```text
Uploaded Label
      |
      v
Image Preprocessing
      |
      v
Tesseract OCR
      |
      v
Rule-Based / Fuzzy Verification
      |
      +---------------------------+
      |                           |
      | confident                 | uncertain
      v                           v
Local Verification          AI Vision Fallback
      |                           |
      +-------------+-------------+
                    |
                    v
             Verification Results
                    |
                    v
          Pass / Fail / Needs Review
```

Tesseract performs the initial extraction.

If OCR produces sufficient evidence, verification can be completed without an external AI request.

If OCR quality is poor or important fields such as brand name or class/type remain unresolved, the application makes one structured AI vision request to recover uncertain fields.

Already reliable OCR results are preserved rather than unnecessarily overwritten by AI results.

---

## Hosted Demo Mode

The deployed demonstration uses a vision-first configuration.

```text
Uploaded Label
      |
      v
AI-Assisted Field Extraction
      |
      v
Deterministic Comparison
      |
      v
Pass / Fail / Needs Review
```

During deployment testing, Tesseract performed well locally but was significantly slower on the CPU-constrained free hosting environment.

For example, a representative image required approximately:

```text
Local OCR:       < 1 second
Hosted OCR:      ~46 seconds
```

The hosted backend therefore sets:

```text
USE_LOCAL_OCR=false
```

This skips the expensive Tesseract stage on the hosted instance and sends the label directly to structured vision extraction.

Local development defaults to:

```text
USE_LOCAL_OCR=true
```

This allows the same application to adapt its extraction strategy to the available infrastructure without maintaining separate implementations.

---

## Image Preprocessing

When local OCR is enabled, uploaded images are prepared for Tesseract using Pillow.

Processing includes:

1. EXIF orientation correction
2. Grayscale conversion
3. Image resizing
4. Automatic contrast adjustment
5. Sharpening

The goal is to improve OCR readability while avoiding unnecessary processing of extremely large images.

---

## OCR

Tesseract is used as the local OCR engine.

The backend records:

- OCR confidence
- Number of readable words
- Extracted text
- OCR processing time

For example:

```json
{
  "ocr_confidence": 69.03,
  "readable_words": 89,
  "timing": {
    "ocr_seconds": 0.73
  }
}
```

OCR works particularly well when text is clearly separated from artwork.

Performance may decrease with:

- Decorative typography
- Small text
- Curved containers
- Perspective distortion
- Low contrast
- Artwork behind text
- Unusual text orientation

---

## AI-Assisted Extraction

AI vision is used as an extraction tool rather than as the final compliance authority.

The model receives the submitted label image and returns structured information such as:

```json
{
  "brand_name": "Hennessy",
  "class_type": "Cognac",
  "abv": 40,
  "net_contents": "750ml",
  "government_warning_visible": true
}
```

The model is instructed to extract only information visibly present in the submitted image and not infer missing information from outside knowledge about the product.

The application then evaluates those extracted values.

Conceptually:

```text
OCR / AI
extracts evidence
      |
      v
Application logic
compares evidence
      |
      v
Pass / Fail / Needs Review
```

This separation is intentional.

The AI model assists with reading difficult labels, while deterministic application logic remains responsible for comparisons such as:

```text
Detected ABV == Expected ABV
```

---

## AI Fallback

When OCR-first mode is enabled, AI is not automatically called for every label.

The application first attempts local extraction and verification.

AI assistance can be triggered when:

- Overall OCR quality is poor
- Brand name cannot be confidently verified
- Class/type cannot be confidently verified

A single vision request extracts multiple fields at once.

AI can also provide supporting evidence that a government warning is visibly present.

However, AI detection of a warning does not automatically result in a regulatory Pass because exact wording and formatting may still require human inspection.

---

## Input Assumptions

The primary intended input is a clear digital image of beverage label artwork, such as:

- PNG
- JPEG
- WebP

The prototype can also process photographs of labels on physical containers.

Photographed containers are a more difficult input because of:

- Label curvature
- Glare
- Perspective
- Small text
- Decorative artwork
- Incomplete views of the package

Testing included both relatively flat digital label artwork and photographs of physical beverage containers.

A single image may also not contain every required marking.

For example, information may appear:

- On the back label
- On a side panel
- On another part of the package
- Etched or embossed directly into the container

In those situations, the prototype intentionally routes unresolved fields to **Needs Review** rather than assuming the information is absent.

---

## Example Results

A representative digital label test produced results similar to:

```text
Brand Name
Hennessy
Source: OCR
Pass

Class / Type
Cognac
Source: AI-assisted extraction
Pass

Alcohol Content
40%
Source: AI-assisted extraction
Pass

Government Warning
Warning visibly detected
Source: AI-assisted detection
Needs Review

Net Contents
750ml
Source: AI-assisted extraction
Pass
```

The prototype was also tested against more difficult photographed beverage packaging where conventional OCR returned little usable text.

In those cases, AI-assisted extraction was still able to recover several visible fields.

---

## Performance

The backend records processing time separately for OCR and AI extraction.

Example response:

```json
{
  "timing": {
    "ocr_seconds": 0,
    "ai_seconds": 1.99,
    "total_backend_seconds": 1.99
  }
}
```

### Local Testing

OCR-only processing commonly completed in under one second on the development machine.

Representative OCR time:

```text
~0.7 seconds
```

Requests requiring AI assistance commonly completed in approximately 3–5 seconds during local testing.

### Hosted Testing

The free hosted environment introduced substantial CPU latency when executing Tesseract.

One deployed test required approximately:

```text
OCR:   46.53 seconds
AI:     2.87 seconds
Total: 49.40 seconds
```

This led to the deployment-specific decision to disable local OCR on the hosted demo.

With OCR disabled, subsequent representative hosted requests completed in:

```text
Run 1: 2.44 seconds
Run 2: 1.99 seconds
Run 3: 1.63 seconds
```

An earlier request took approximately 7.9 seconds, demonstrating that external API/model latency can vary.

The deployed configuration therefore provides substantially better typical response time while preserving the OCR-first implementation for environments where sufficient CPU resources are available.

---

## Backend

The backend is implemented with:

- Python
- FastAPI
- Pillow
- Tesseract OCR / pytesseract
- RapidFuzz
- OpenAI API

The primary verification endpoint is:

```text
POST /verify
```

It accepts a multipart form containing:

```text
label
expected_brand
expected_class_type
expected_abv
```

The response includes:

- Extracted fields
- Verification results
- Evidence source
- OCR metadata
- Processing timing
- Raw OCR output when OCR is enabled

---

## Frontend

The frontend is implemented with:

- Next.js
- React
- TypeScript
- Tailwind CSS

The interface allows a reviewer to:

1. Enter expected application information
2. Upload a label image
3. Submit the label for verification
4. Review individual field results
5. See whether evidence came from OCR or AI-assisted extraction
6. Inspect OCR details when available

The frontend communicates with the FastAPI backend using an environment-configured API URL.

---

## Running Locally

### Prerequisites

Install:

- Python 3
- Node.js / npm
- Tesseract OCR
- Git

An OpenAI API key is required for AI-assisted extraction.

---

## Backend Setup

From the project root:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

### Activate on Windows

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Make sure Tesseract OCR is installed.

The default Windows development path is:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Start FastAPI:

```bash
uvicorn main:app --reload
```

The backend will be available at:

```text
http://127.0.0.1:8000
```

FastAPI's interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

---

## Frontend Setup

Open another terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Then open:

```text
http://localhost:3000
```

---

## Environment Variables

### Backend

#### `OPENAI_API_KEY`

Required for AI-assisted extraction.

```text
OPENAI_API_KEY=your_api_key
```

The API key must remain server-side and should never be placed in frontend code or committed to source control.

---

#### `USE_LOCAL_OCR`

Controls whether the backend executes Tesseract before AI-assisted extraction.

```text
USE_LOCAL_OCR=true
```

enables OCR-first mode.

```text
USE_LOCAL_OCR=false
```

uses vision-first extraction.

The application defaults to `true` when the variable is not specified.

---

#### `FRONTEND_ORIGINS`

Defines which frontend origins are permitted to access the FastAPI backend.

Multiple origins can be provided as a comma-separated list.

Example:

```text
FRONTEND_ORIGINS=https://example.vercel.app,http://localhost:3000
```

Origins should not include a trailing slash.

---

#### `TESSERACT_CMD`

Optionally overrides the Tesseract executable location.

The application uses platform-specific defaults when this variable is not supplied.

---

### Frontend

#### `NEXT_PUBLIC_API_URL`

Specifies the backend used by the Next.js frontend.

For local development:

```text
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

For deployment, this points to the hosted FastAPI service.

This variable contains a public API address and does not contain an API secret.

---

## Deployment

The prototype uses two hosting services:

```text
GitHub
   |
   +---- frontend/
   |        |
   |        v
   |      Vercel
   |
   +---- backend/
            |
            v
          Render
```

### Frontend

The Next.js application is deployed using Vercel.

### Backend

The FastAPI application is deployed as a Docker-based Render web service.

The Docker image installs both:

- Python dependencies
- Tesseract OCR

Containerization is used because pytesseract is only a Python interface; the actual Tesseract executable must also exist in the operating system.

The hosted demo currently sets:

```text
USE_LOCAL_OCR=false
```

because Tesseract performance on the free hosted CPU was substantially slower than local execution.

---

## Government Warning Handling

Government-warning verification is intentionally conservative.

OCR and AI can provide evidence that warning language is present, but reliably certifying exact regulatory compliance can involve more than detecting a few words.

For example, a complete review may need to consider:

- Exact wording
- Capitalization
- Typography
- Placement
- Legibility
- Whether the entire warning is visible

The prototype therefore distinguishes between:

```text
Warning appears to be present
```

and:

```text
Warning has been conclusively verified as compliant
```

The first can be assisted by automation.

The second remains a human-review task in this prototype.

---

## Limitations

This project is a prototype and is not intended to make authoritative regulatory determinations.

### Single-image submissions

A single image may not show every required package marking.

A production implementation should support multiple images representing front, back, side, and container markings.

### Government warning verification

Warning presence can be detected, but exact regulatory wording and formatting are intentionally left for human review.

### OCR quality

Traditional OCR performance varies substantially depending on typography, image quality, contrast, orientation, and packaging design.

### AI extraction

AI vision improves extraction from difficult labels but introduces:

- API cost
- Network dependency
- Variable latency
- Possible service failures

When evidence remains uncertain, the system returns **Needs Review**.

### Container markings

Information etched, embossed, or otherwise marked directly on a physical container may not be visible in submitted label artwork.

### PDF support

The current prototype focuses primarily on image uploads. Direct processing of multi-page or vector PDF label submissions would be a useful production enhancement.

---

## Future Improvements

Given additional development time, useful improvements would include:

- Multiple image uploads for front, back, and side panels
- PDF label-artwork support
- Region-of-interest OCR
- Field-level confidence scoring
- More robust net-content parsing
- Improved government-warning verification
- Container marking detection
- Image-quality feedback before verification
- Persistent verification and audit history
- Automated test fixtures using representative label designs
- Additional deterministic compliance rules
- Production infrastructure capable of running OCR efficiently
- More granular AI escalation based on individual field uncertainty

---

## Security

The OpenAI API key is stored as a backend environment variable and is never exposed to the browser.

Secrets should never be committed to GitHub.

The backend uses CORS restrictions to limit browser access to approved frontend origins.

Production deployments should use appropriate secret management, authentication, authorization, logging, and rate limiting before processing sensitive or regulated application data.

---

## Design Philosophy

The prototype follows a simple principle:

> Automation should surface evidence and uncertainty rather than hide uncertainty behind a confident answer.

For straightforward labels, the system can quickly verify matching information.

For difficult or incomplete labels, AI-assisted extraction can recover information that conventional OCR misses.

When neither approach provides enough evidence, the application routes the field to **Needs Review**.

This keeps the human reviewer in the decision-making loop while reducing the amount of manual label comparison required.

---

## Disclaimer

This application is a prototype decision-support tool.

A **Pass** means the submitted image and expected application data matched according to the implemented verification logic. It does not represent official TTB approval or a definitive determination of regulatory compliance.

Fields marked **Needs Review** are intentionally surfaced for human evaluation.