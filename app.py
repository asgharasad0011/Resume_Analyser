from flask import Flask, render_template, request, redirect, url_for, session
import os
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import google.generativeai as genai
from dotenv import load_dotenv
import markdown
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for session storage

# Load environment variables
load_dotenv()

# Configure Google Gemini AI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text

        if text.strip():
            return text.strip()
    except Exception as e:
        print(f"Direct text extraction failed: {e}")
    
    try:
        images = convert_from_path(pdf_path)
        for image in images:
            text += pytesseract.image_to_string(image) + "\n"
    except Exception as e:
        print(f"OCR failed: {e}")
    
    return text.strip()

# Function to extract job description from LinkedIn URL
def extract_job_description_from_url(job_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(job_url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract job description (adjust based on LinkedIn page structure)
        job_description = soup.find("div", class_="description__text")  # Adjust if needed
        
        if job_description:
            return job_description.get_text(separator=" ").strip()
        else:
            return None
    except Exception as e:
        print(f"Failed to extract job description: {e}")
        return None

# Function to analyze resume
def analyze_resume(resume_text, job_description=None):
    if not resume_text:
        return "<p>Resume text is required for analysis.</p>"
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    base_prompt = f"""
    You are an experienced HR professional specializing in resume evaluation and career guidance. 
    Your task is to analyze the following resume, identify key strengths and weaknesses, and provide detailed feedback. 

    1. Resume Evaluation:  
    - Identify strong points in the candidate's profile.  
    - Highlight weak areas or missing information that could be improved.  
    - List all key skills mentioned in the resume.  
    - Suggest ways to improve the resume in terms of content, structure, and formatting.  
    - Recommend relevant courses, certifications, or skills that can enhance the candidate’s profile.  

    Resume:
    {resume_text}
    """
    
    if job_description:
        base_prompt += f"""
    2. Job Compatibility Analysis:  
    Compare the given resume against the provided job description.  
    - List the skills required for this job.  
    - Compare them with the skills found in the resume.  
    - Identify any missing or weak areas that need improvement.  
    - Provide a percentage match score (0-100%) indicating how well the resume aligns with the job.  

        Job Description:
        {job_description}
        """
    
    response = model.generate_content(base_prompt)
    return markdown.markdown(response.text.strip())

@app.route("/", methods=["GET", "POST"])
def index():
    analysis = None
    success_message = session.pop("success_message", "")

    if request.method == "POST":
        uploaded_file = request.files["resume"]
        job_description = request.form.get("job_description", "")
        job_url = request.form.get("job_url", "").strip()

        if job_url:
            extracted_description = extract_job_description_from_url(job_url)
            if extracted_description:
                job_description = extracted_description
            else:
                session["error_message"] = "Failed to extract job description from the given URL."

        if uploaded_file:
            file_path = os.path.join("uploads", uploaded_file.filename)
            uploaded_file.save(file_path)
            session["success_message"] = "File Successfully Uploaded!"
            
            resume_text = extract_text_from_pdf(file_path)
            session["analysis"] = analyze_resume(resume_text, job_description)
            os.remove(file_path)
            
            return redirect(url_for("index"))

    analysis = session.pop("analysis", None)
    error_message = session.pop("error_message", None)

    return render_template("index.html", analysis=analysis, success_message=success_message, error_message=error_message)

if __name__ == "__main__":
    app.run(debug=True)
