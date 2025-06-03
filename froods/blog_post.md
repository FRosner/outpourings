---
title: Build Your Own Food Tracker with OpenAI Platform 
published: true
description: This blog post shows how to build your own food tracker using OpenAI's GPT-4 Vision API.
tags: genai, python, showdev, ai
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/yw7zwxkydoqv73plivwj.jpg
---

## The Benefits of Food Tracking

Whether your goal is to lose weight, gain muscle, or simply maintain a balanced diet, understanding the value of the food you consume is essential. By keeping a record of what we eat, we gain insights into our nutritional intake, allowing us to make informed decisions about our diet. Here are some of the key benefits of food tracking:

- **Awareness and Accountability**: Tracking helps us understand what we're consuming daily, shedding light on eating habits we might not even be aware of.
- **Nutritional Balance**: It enables us to monitor macronutrients like protein, fats, and carbohydrates, ensuring a balanced diet that aligns with personal goals such as weight loss, muscle gain, or overall well-being.
- **Portion Control**: With a clearer picture of portion sizes, food tracking helps prevent overeating and supports mindful eating practices.
- **Customizable Goals**: By recording meals, we can set specific goals, such as reducing sugar intake, increasing fiber consumption, or staying within a calorie limit.
- **Long-term Insights**: Over time, food tracking can reveal patterns, helping to identify triggers for overeating, nutrient deficiencies, or correlations between diet and mood.

In this blog post, I want to share how easy it is to build your own food tracker using a GenAI platform like OpenAI. The tool analyzes images of meals from my Google Photos library and provides a nutritional breakdown using AI. You can find the [source code](https://github.com/FRosner/photos-calory-tracker) over on GitHub.

## Architecture

The architecture consists of three main components that work together to analyze your food photos: Your (Python) application, the Google Photos API, and the OpenAI API.

![architecture](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/rgkqu31c2vjbws531rg5.png)

The Python application uses the Google Photos Library API to fetch your food photos. It requires:

- OAuth 2.0 authentication for secure access to your photos
- Search capabilities to find photos tagged as "food" from a specific date
- The ability to download the actual image content for analysis

It then uses the OpenAI's GPT-4 Vision API to analyze these images. This entails:

- Name the dish
- Estimate nutritional content (calories, protein, carbs, fat, fiber, etc.)
- Assess the health score and processing degree and break down meal components

## Implementation

### Google Photos API Authentication

Let's jump into the code. To access your Google photos, you need some initial setup. Note that the API I am using to access all my Google Photos has been deprecated and was removed on March 31, 2025. From now on, apps can only access Photos that they have created or that the user picks.

To generate credentials your app can use, run the following code:

```python
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle

SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']

CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", ".secrets/client_secret.json")
AUTH_PORT = int(os.getenv("GOOGLE_AUTH_PORT", "8080"))
TOKEN_PICKLE_FILE = os.getenv("GOOGLE_TOKEN_PICKLE_FILE", ".secrets/token.pickle")

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
creds = flow.run_local_server(port=AUTH_PORT, access_type='offline', include_granted_scopes='true')
with open(TOKEN_PICKLE_FILE, 'wb') as token:
    pickle.dump(creds, token)
```

This will open a browser window where you can authenticate your app and store the credentials in a pickle file. The pickle module is used to serialize and deserialize Python objects. Our app can then unpickle the credentials and use them to access the Google Photos API.

```python
def google_authenticate():
    creds = None
    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise ValueError("Invalid credentials. Please run google_photos_init.py to authenticate.")

    return creds
```

This approach is only working for prototypes like these. In a production scenario you would use a more secure way to store and manage user credentials.

### Searching Food Photos

Now that we have valid credentials to access the Google Photos API, let's use them to search for food photos in our library. First, we create a photos API object:

```python
from googleapiclient import discovery

creds = google_authenticate()
photos_api = discovery.build("photoslibrary", "v1", credentials=creds, static_discovery=False)
```

Then, we write a function that uses the photos API to search for photos that match a specific search term and date filter:

```python
def google_search_photos(api, search_term=None, date_filter=None):
    filters = {}
    if date_filter:
        filters["dateFilter"] = {"dates": [date_filter]}
    if search_term:
        filters["contentFilter"] = {"includedContentCategories": [search_term]}

    search_body = {
        "pageSize": 50,
        "filters": filters,
    }

    results = api.mediaItems().search(body=search_body).execute()
    return results.get('mediaItems', [])
```

The search term we are using is "food". We are using a [content category filter](https://developers.google.com/photos/library/guides/apply-filters#content-categories) for this. The [date filter](https://developers.google.com/photos/library/guides/apply-filters#dates-date-ranges) will make sure we only get the recent photos, e.g. from yesterday. The call could look like this:

```python
photos = google_search_photos(photos_api, search_term="food", date_filter={"day": 1, "month": 1, "year": 2023})
```

Now let's look at an example photo returned by the API:

```json
{
  "id": "ANNz-AhcvptH<redacted>",
  "productUrl": "https://photos.google.com/lr/photo/<redacted>",
  "baseUrl": "https://lh3.googleusercontent.com/lr/<redacted>",
  "mimeType": "image/jpeg",
  "mediaMetadata": {
    "creationTime": "2025-03-18T10:36:20.790Z",
    "width": "4080",
    "height": "3072",
    "photo": {
      "cameraMake": "Google",
      "cameraModel": "Pixel 6",
      "focalLength": 6.81,
      "apertureFNumber": 1.85,
      "isoEquivalent": 103,
      "exposureTime": "0.005034999s"
    }
  },
  "filename": "PXL_20250318_103620790.jpg"
}
```

Next, let's look into analyzing the image using the OpenAI API.

### Photo Download and Analysis

First, let's define some helper functions to work with the image data. We need to be able to download an image and encode it for the OpenAI API.

```python
import requests
import base64

def download_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"Failed to download image. Status code: {response.status_code}")

def encode_image(image):
    return base64.b64encode(image).decode('utf-8')
```

Next, let's define the data model for the food analysis that we can use as [structured output](https://platform.openai.com/docs/guides/structured-outputs) for the OpenAI API. Structured outputs allow you to obtain machine-readable output from the OpenAI API. It also implicitly tells the AI what information you are expecting. We define `FoodAnalysis` for a single dish and `FoodAnalysisResponse` for a list of dishes so we can pass multiples images at once with a common prompt.

```python
from pydantic import BaseModel

class FoodAnalysis(BaseModel):
    readable_name: str
    protein_g: int
    fat_g: int
    carbohydrate_g: int
    fibre_g: int
    total_mass_g: int
    total_kcal: int
    total_health_score: int
    processing_degree: str
    components: list[str]

class FoodAnalysisResponse(BaseModel):
    foods: list[FoodAnalysis]
```

Finally, we can write the function that uses the OpenAI API to analyze the images. We are giving a system prompt to prime the LLM on the task:

> You are a nutrition and health expert. You are helping a user understand the nutritional value of their food to help them eat healthier. For each image, estimate the protein, fat, fibre, and carbohydrate content in grams, the total mass in grams, the total calories, the total health score (1-10, 10 being super healthy, 1 being heart-attack-unhealthy), the processing degree ('low', 'medium', 'high'), and the components that are in the dish. If you are unsure, please provide an estimate. Only refuse the query if the image does not contain any food. Please also provide a readable name of the dish. If this looks like a well-known dish, you can use that name. Otherwise, you can describe it in a few words that are helpful to understand the dish.

The actual images will be uploaded as a list of user messages with image URL attachments containing the base64 encoded image. If the image is accessible via a URL directly, you don't need to download and encode it.

```python
def analyze_images(images):
    client = OpenAI()

    image_messages = []
    for image in images:
        encoded_image = encode_image(image)
        image_messages.append({
            "role": "user",
            "content": [{
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_image}"
                }
            }]
        })

    try:
        response = client.beta.chat.completions.parse(
            messages=[
                {
                    "role": "system",
                    "content": "You are a nutrition and health expert. [...]"
                },
                *image_messages,
            ],
            model="gpt-4o-mini",
            response_format=FoodAnalysisResponse,
        )

        food_analysis = response.choices[0].message
        if food_analysis.parsed:
            return food_analysis.parsed
        elif food_analysis.refusal:
            print(food_analysis.refusal)
            return None
    except Exception as e:
        if type(e) == openai.LengthFinishReasonError:
            print("Too many tokens: ", e)
            return None
        else:
            print(e)
            return None
```

Let's put it all together, downloading all images and analyzing them. Here's the code with an example output:

```python
images = []
for image in photos:
    images.append(download_image(image['baseUrl']))
analysis = analyze_images(images)
```

```
foods:
- carbohydrate_g: 15
  components:
  - arugula
  - roasted tomatoes
  - parmesan cheese
  - lemon
  - olive oil
  - seasonings
  fat_g: 10
  fibre_g: 5
  processing_degree: low
  protein_g: 8
  readable_name: Arugula Salad with Roasted Tomatoes and Cheese
  total_health_score: 8
  total_kcal: 150
  total_mass_g: 200
```

## Assessing Accuracy

To assess the accuracy of the solution I developed a small [validation script](https://github.com/FRosner/photos-calory-tracker/blob/main/validate.py) that analyzes given images and compares the results to expected values. Take a banana, for example:

![Banana](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/si9dk7a7ouhgp5vx9n70.jpg)

```json
{
  "foods": [
    {
      "readable_name": "Banana",
      "protein_g": 1,
      "fat_g": 0,
      "fibre_g": 2,
      "carbohydrate_g": 19,
      "total_mass_g": 71,
      "total_kcal": 72,
      "total_health_score": 8,
      "processing_degree": "low",
      "components": [
        "banana"
      ]
    }
  ]
}
```

The validation script outputs the differences between the actual and expected values. The main challenge turns out to be estimating the mass of the dish.

```json
{
  "carbohydrate_g": {
    "actual": 27,
    "expected": 19,
    "difference": 8
  },
  "total_mass_g": {
    "actual": 118,
    "expected": 71,
    "difference": 47
  },
  "fibre_g": {
    "actual": 3,
    "expected": 2,
    "difference": 1
  },
  "total_kcal": {
    "actual": 105,
    "expected": 72,
    "difference": 33
  },
  "total_health_score": {
    "actual": 9,
    "expected": 8,
    "difference": 1
  }
}
```

Here are some more examples (differences shown as predicted / actual / % difference):

| Name      | Photo                                                                                                    | Mass (g)        | KCal            | Carbohydrates (g) | Fat (g)        | Protein (g)    | Health Score  |
|-----------|----------------------------------------------------------------------------------------------------------|-----------------|-----------------|-------------------|----------------|----------------|---------------|
| Banana    | ![Banana](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/si9dk7a7ouhgp5vx9n70.jpg)             | 118 / 71 / +66% | 105 / 72 / +46% | 27 / 19 / +42%    | 0 / 0 / 0%     | 1 / 1 / 0%     | 8 / 8 / 0%    |
| Pear      | ![Pear](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/3trdm9nvy7yic3lus6t2.jpg)               | 178 / 192 / -7% | 102 / 109 / -6% | 28 / 28 / 0%      | 0 / 0 / 0%     | 0 / 0 / 0%     | 9 / 10 / -10% |
| Dates     | ![Dates](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/afwly3sz2t6l3q8xawud.jpg)              | 100 / 100 / 0%  | 277 / 296 / -6% | 75 / 65 / +15%    | 0 / 0.5 / -100%| 1 / 2 / -50%   | 8 / 8 / 0%    |
| Yoghurt   | ![Yoghurt](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/x9ftc2221fy0fcrvov1m.jpg)            | 100 / 152 / -34%| 61 / 106 / -42% | 6 / 5 / +20%      | 4 / 6 / -33%   | 3 / 7 / -57%   | 8 / 8 / 0%    |
| Pudding   | ![Unpackaged pudding](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/8f73d44m6or8ayitpbyl.jpg) | 100 / 150 / -33%| 180 / 165 / +9% | 30 / 25 / +20%    | 7 / 5 / +40%   | 3 / 4 / -25%   | 5 / 3 / +66%  |
| Salad     | ![Salad](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/j5d8op16i32jp1jf3qb8.jpg)              | 200 / 300 / -33%| 90 / 232 / -61% | 10 / 6 / +67%     | 7 / 17 / -59%  | 5 / 14 / -64%  | 9 / 10 / -10% |
| Dumplings | ![Dumplings](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/yw7zwxkydoqv73plivwj.jpg)          | 200 / 350 / -43%| 320 / 595 / -46%| 40 / 70 / -43%    | 8 / 23 / -65%  | 14 / 17 / -18% | 7 / 8 / -13%  |

We can see that the estimates are not always accurate, with deviations of up to 66%. A big challenge appears to be estimating the mass of the dish, as well as seeing hidden ingredients in layered dishes.

The health score is pretty accurate, and on average, the deviation of the calorie intake appears to be acceptable. If the goal is to support healthy eating habits, I believe the agent is more than useful.

Interestingly, when analyzing photos of packaged food, the tool is able to accurately extract the nutritional information from the packaging.

![Packaged pudding](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/ih0tv79yj572gqchdovm.jpg)

## Cost

Analyzing 1 image requires ~20k tokens. As of April 2025, when using `gpt-4o-mini` ($0.15 / 1 million tokens), this costs $0.003. Assuming you analyze 10 photos a day, this would cost less than $1 per month.

## Summary

In this blog post, I have shown how easy it is to build your own food tracker using a GenAI platform like OpenAI. The tool analyzes images of meals from your Google Photos library and provides a nutritional breakdown using AI.

While the results are not perfect, I feel like the added value is pretty high if you are not willing to count all your calories and keep track of everything you eat manually.

---

If you liked this post, you can [support me on ko-fi](https://ko-fi.com/frosnerd).
